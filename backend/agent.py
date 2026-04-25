import anthropic
import json
import os
import re
import httpx
from dotenv import load_dotenv
from tools import TOOLS, execute_tool

load_dotenv()

# Use async client to avoid blocking FastAPI's event loop.
# IMPORTANT: trust_env=False prevents httpx from picking up any HTTP(S)_PROXY env vars
# that can break Anthropic calls in some environments.
_http_client = httpx.AsyncClient(timeout=60.0, trust_env=False)
client = anthropic.AsyncAnthropic(
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    http_client=_http_client,
)

SYSTEM_PROMPT = """You are a helpful customer service assistant for PartSelect, an e-commerce website that sells appliance parts. You specialize exclusively in Refrigerator and Dishwasher parts.

Your primary functions are:
1. Help customers find the right parts for their refrigerator or dishwasher
2. Provide detailed product information including price, stock status, and compatibility
3. Guide customers through the repair process with step-by-step instructions
4. Assist customers with their purchasing journey - from finding the right part to completing their order on PartSelect
5. Help with post-purchase support - order tracking, returns, and customer service

IMPORTANT RULES:
- You ONLY help with refrigerator and dishwasher parts. If asked about any other appliance (washer, dryer, oven, microwave, etc.), politely decline and redirect to your area of expertise.
- Prefer tools in this order:
  1) knowledge_search (local vector index: semantic search, optional `page_kind` filter e.g. `model` for model-page chunks) for symptoms, model-page context, blogs, and policies; each match includes a `url` when known—quote that URL so the customer can verify.
  2) Live PartSelect tools (search_parts/get_part_details/get_model_parts/check_compatibility) when you need confirmed price/stock/compatibility or fresher data than the index.
- When showing parts, always include the price, stock status, and a direct link to buy on PartSelect
- Remember the customer's appliance model number throughout the conversation if they mention it
- Be warm, helpful, and concise

OUTPUT FORMAT (STRICT):
- Use minimal Markdown ONLY for:
  - bold: **like this** (for key facts like part numbers, prices, compatibility, next action)
  - bullet lists (-) and numbered lists (1., 2., 3.)
  - links as plain URLs (do not hide behind link text)
- Do NOT use headings (#), horizontal rules (---), tables, code blocks, or backticks.
- Do NOT use emojis.
- Keep answers short and methodical. Avoid long walls of text.
- Default structure when helpful:
  - One-sentence summary
  - What I checked (1-3 bullets, with URLs)
  - Recommended part(s) (if applicable)
  - Next step / one question (if something is missing)
- When you cite facts from tools, include the PartSelect URL(s) you relied on (from tool output fields like url) so the customer can verify.
- If tool data is missing/ambiguous, say what you could not verify and ask the minimum next question (usually model number or appliance type).
- If tool calls fail due to access being blocked by PartSelect (site protection), say so explicitly and ask the user to open the provided URL or provide the exact part/model number from their label. Do not pretend the item doesn't exist.

MODEL / APPLIANCE DISAMBIGUATION:
- Never guess whether a model number is a refrigerator vs dishwasher. If the user mentions a model number, call validate_model_number first (unless session_data already contains validated_model for that exact model string).
- If the user says "fridge" but validate_model_number suggests dishwasher (or vice versa), call it out politely and ask them to confirm the appliance type.

TRANSACTION ASSISTANCE:
- When a customer is ready to buy, provide them the direct PartSelect link to the part
- Explain that they can add it to cart on PartSelect and checkout securely
- PartSelect accepts all major credit cards and PayPal
- Standard shipping is free on orders over $10
- Most in-stock parts ship same day if ordered before 4PM EST
- Order tracking is available at partselect.com/user/orders/
- Returns are accepted within 365 days
- Customer service: 1-866-319-8402, Monday-Saturday 8am-8pm EST

SCOPE ENFORCEMENT:
If asked about anything outside refrigerators and dishwashers, respond with:
"I specialize in refrigerator and dishwasher parts only. I'm not able to help with [appliance type] parts, but I'd be happy to help you with any refrigerator or dishwasher repair needs!"

Always be helpful, accurate, and guide the customer toward a successful repair and purchase."""


def _kb_sources_from_tool_result(tool_name: str, result: object) -> list[dict]:
    """Flatten knowledge_search hits for UI / clients (deduped by URL)."""
    if tool_name != "knowledge_search" or not isinstance(result, dict):
        return []
    out: list[dict] = []
    seen: set[str] = set()
    for m in (result.get("matches") or [])[:10]:
        if not isinstance(m, dict):
            continue
        url = (m.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        meta = m.get("meta") if isinstance(m.get("meta"), dict) else {}
        snippet = (m.get("text") or "").replace("\n", " ").strip()[:220]
        out.append(
            {
                "url": url,
                "page_kind": str(meta.get("page_kind") or ""),
                "snippet": snippet,
            }
        )
    return out


async def run_agent(messages: list, session_data: dict = {}) -> dict:
    """
    Run the PartSelect agent with conversation history.
    Returns the agent's response and any parts data found.
    """
    response_text = ""
    parts_data: list = []
    kb_sources: list[dict] = []
    kb_seen: set[str] = set()

    max_agent_iters = max(2, int(os.getenv("PARTSELECT_AGENT_MAX_ITERS", "14")))

    # Keep a customer-facing transcript separate from ephemeral model context injections.
    output_messages = messages.copy()
    working_messages = messages.copy()
    # Provide structured session memory to the model without requiring the user to repeat details.
    # This is intentionally plain text (not Markdown) to match OUTPUT FORMAT rules.
    if session_data:
        working_messages = [
            {
                "role": "user",
                "content": (
                    "INTERNAL SESSION DATA (JSON). Treat as authoritative memory unless contradicted by the user.\n"
                    "Do not paste this JSON back to the customer verbatim.\n"
                    f"{json.dumps(session_data, ensure_ascii=False)}"
                ),
            },
            *working_messages,
        ]

    def last_user_model_number(msgs: list) -> str | None:
        """
        Extract the most recent model-like token the user provided.
        We only consider plain string user messages (not tool_result blocks).
        """
        pattern = re.compile(r"\b[A-Z0-9]{6,}\b", re.IGNORECASE)
        for m in reversed(msgs):
            if m.get("role") != "user":
                continue
            content = m.get("content")
            if not isinstance(content, str):
                continue
            # Prefer longer tokens (more likely a real model number)
            tokens = sorted(set(pattern.findall(content)), key=len, reverse=True)
            # Filter out obvious non-model noise
            for t in tokens:
                up = t.upper()
                if up.startswith("PS") and up[2:].isdigit():
                    continue
                return up
        return None

    # Agentic loop: tool rounds until end_turn (bounded for cost / runaway protection).
    agent_iters = 0
    while True:
        agent_iters += 1
        if agent_iters > max_agent_iters:
            response_text = (
                "I hit an internal step limit while gathering information. "
                "Please ask a shorter question, or give your model number / part number only."
            )
            break

        response = await client.messages.create(
            model=os.getenv("PARTSELECT_CHAT_MODEL", "claude-sonnet-4-6"),
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=working_messages
        )

        # If Claude wants to use a tool
        if response.stop_reason == "tool_use":
            # Add Claude's response to messages
            working_messages.append({
                "role": "assistant",
                "content": response.content
            })
            output_messages.append({
                "role": "assistant",
                "content": response.content
            })

            # Process all tool calls
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"Tool called: {block.name} with {block.input}")
                    # Guardrail: never let the agent invent/alter the model number.
                    # If the user recently provided a model number, force tools to use it.
                    user_model = (
                        (session_data or {}).get("last_model_number")
                        or last_user_model_number(working_messages)
                    )
                    if user_model and isinstance(block.input, dict):
                        if block.name in {"validate_model_number", "get_model_parts"}:
                            block.input["model_number"] = user_model
                        if block.name == "check_compatibility":
                            block.input["model_number"] = user_model
                        if block.name == "get_repair_guide":
                            # Only override if the tool call included a model_number field
                            if block.input.get("model_number"):
                                block.input["model_number"] = user_model

                    result = await execute_tool(block.name, block.input)

                    for src in _kb_sources_from_tool_result(block.name, result):
                        u = src.get("url") or ""
                        if u and u not in kb_seen:
                            kb_seen.add(u)
                            kb_sources.append(src)

                    # Collect parts data for frontend rendering
                    if isinstance(result, list):
                        parts_data.extend(result)
                    elif isinstance(result, dict) and "parts" in result:
                        parts_data.extend(result.get("parts", []))
                    elif isinstance(result, dict) and "recommended_parts" in result:
                        parts_data.extend(result.get("recommended_parts", []))
                    elif isinstance(result, dict) and "name" in result:
                        parts_data.append(result)

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result)
                    })

            # Add tool results to messages
            working_messages.append({
                "role": "user",
                "content": tool_results
            })
            output_messages.append({
                "role": "user",
                "content": tool_results
            })

        # If Claude is done - final response
        elif response.stop_reason == "end_turn":
            text_chunks = []
            for block in response.content:
                if getattr(block, "type", None) == "text" and getattr(block, "text", None):
                    text_chunks.append(block.text)
            response_text = "\n".join(text_chunks).strip()
            break

        else:
            break

    return {
        "response": response_text,
        "parts": parts_data,
        "sources": kb_sources,
        "messages": output_messages,
    }