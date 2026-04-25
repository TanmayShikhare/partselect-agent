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

async def close_agent_http_client() -> None:
    try:
        await _http_client.aclose()
    except Exception:
        pass

SYSTEM_PROMPT = """You are a helpful customer service assistant for PartSelect, an e-commerce website that sells appliance parts. You specialize exclusively in Refrigerator and Dishwasher parts.

Your primary functions are:
1. Help customers find the right parts for their refrigerator or dishwasher
2. Provide detailed product information including price, stock status, and compatibility
3. Guide customers through the repair process with step-by-step instructions
4. Assist customers with their purchasing journey - from finding the right part to completing their order on PartSelect
5. Help with post-purchase support - order tracking, returns, and customer service

OPERATING MODE (CURRENT — READ CAREFULLY):
- This assistant is powered by an indexed PartSelect parts + help/guides dataset. Prefer the `knowledge_search` tool for reliable model context, repair guidance, and part mentions.
- You may use other tools as optional enrichment, but do not frame the experience around "live scraping" or "real-time lookups".

IMPORTANT RULES:
- You ONLY help with refrigerator and dishwasher parts. If asked about any other appliance (washer, dryer, oven, microwave, etc.), politely decline and redirect to your area of expertise.
- Tool discipline:
  1) Use `knowledge_search` first on repair/symptom/model/part questions (use a rich query; use `page_kind: "model"` when the user gave a model number). Cite returned `url` values.
  2) Use live tools only if `knowledge_search` did not surface enough, or the user explicitly needs something only a live API page would have. Prefer one targeted call; if it fails, proceed with best-effort guidance + links to verify.
- If you mention price/stock, tell the customer to confirm on PartSelect before buying. If `get_part_details` succeeds, you may use its price/stock for that call only.
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
- After you receive tool results: write for the customer in normal language. Never paste raw JSON, tool payloads, or internal field names into the reply.
- When discussing price/stock/compatibility, avoid negative framing. Present best-effort guidance confidently, and always include the PartSelect link(s) so the customer can verify current price, fit, and stock.
- If tool data is missing/ambiguous, say what you could not verify and ask the minimum next question (usually model number or appliance type).
- If you cannot answer a very specific question from indexed pages, say: "I don't have that exact detail available right now due to operational constraints." Then give best-effort guidance plus the most relevant PartSelect link(s) to verify.

CRITICAL CUSTOMER-FACING WORDING:
- Do NOT mention internal implementation details like "RAG", "vector index", "embeddings", "knowledge base", or "KB".
- Never say "my local knowledge base didn't return a match" or anything similar.
- Avoid self-undermining "failure narration". Do not dwell on what you couldn't do.
- If you don't have specific details, use neutral phrasing ("not available right now due to operational constraints") and then give best-effort guidance + the most relevant PartSelect link(s) and ask for the model number to tailor next steps.

TONE / FRAMING (VERY IMPORTANT):
- Lead with confident framing and give an actual answer first.
- IMPORTANT: Links are supporting evidence, not the answer. Never respond with only links.

PART INSTALLATION ANSWERS (TEMPLATE):
- When asked "How do I install PSxxxx?":
  - Start with a 1-sentence summary: "Here’s the safest way to install **PSxxxx**."
  - Give 4-7 concrete steps (power off, access panel, photo wiring, remove, install, test).
  - Include the part page URL as a reference (do not say you couldn't look anything up).
  - Ask ONE follow-up to tailor: refrigerator vs dishwasher + model number.

MODEL PARTS REQUESTS (IMPORTANT):
- If the user asks: "Find parts for model X" (or similar), respond with actual part suggestions.
- Use `knowledge_search` with `page_kind: "model"` for that model number.
- Then list 5-8 commonly replaced parts for that model (or closest matches from indexed pages). Include **name + part number (PS...) + URL** when available.
- End with ONE follow-up question about symptom to narrow down.

ANSWER QUALITY (NON-NEGOTIABLE):
- Always provide a real, helpful answer that summarizes what you found and what it means.
- Minimum content for most replies:
  1) 1-sentence summary
  2) 2-5 concrete troubleshooting steps or part recommendations (as applicable)
  3) 1-2 PartSelect URLs as references (when available)
- If `knowledge_search` returns weak/empty results, still give high-quality general guidance and ask for the model number to tailor it.

PART NUMBER + LINK PREFERENCE:
- When recommending a part, include the PartSelect part number (PS...) and a direct PartSelect URL when that information is available from the indexed pages or tool outputs.
- If you do not have a reliable part number, do not guess one. Describe the part clearly and ask for the appliance model number (or the part label) to confirm.

INSTALLATION QUESTIONS (PART NUMBER):
- If the user asks how to install a part (e.g. "How can I install PS11752778?"), first use `knowledge_search` with the part number + "installation" / "repair story".
- If you still can't retrieve the instructions, give safe, general steps and direct them to the part page's "Installation Instructions" / "Repair Story" section, plus ask for the appliance model number to tailor steps.

MODEL / APPLIANCE DISAMBIGUATION:
- Never guess refrigerator vs dishwasher from thin air. **Prefer** `knowledge_search` (model pages / help text) for evidence first.
- Call `validate_model_number` **only when** you still need a live page signal after KB, or session_data lacks a stable `validated_model` for that exact model string—and **if it fails**, continue with KB + ask the customer to confirm appliance type in plain language.
- If the user says "fridge" but KB/live evidence suggests dishwasher (or vice versa), call it out politely and ask them to confirm the appliance type.

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


async def run_agent(messages: list, session_data: dict | None = None) -> dict:
    """
    Run the PartSelect agent with conversation history.
    Returns the agent's response and any parts data found.
    """
    response_text = ""
    parts_data: list = []
    kb_sources: list[dict] = []
    kb_seen: set[str] = set()
    tool_call_trace: list[dict] = []
    session_data = session_data or {}

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

        if not (os.getenv("ANTHROPIC_API_KEY") or "").strip():
            msg = (
                "Service is missing a required API key configuration. "
                "Please set ANTHROPIC_API_KEY and try again."
            )
            return {
                "response": msg,
                "parts": [],
                "sources": [],
                "messages": messages + [{"role": "assistant", "content": msg}],
                "debug": {},
            }

        response = await client.messages.create(
            model=os.getenv("PARTSELECT_CHAT_MODEL", "claude-sonnet-4-6"),
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=working_messages,
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
                    if os.getenv("PARTSELECT_DEBUG", "").lower() in {"1", "true", "yes"}:
                        print(f"Tool called: {block.name} with {block.input}")
                    tool_call_trace.append(
                        {
                            "name": str(block.name),
                            "input_keys": sorted(list(block.input.keys()))
                            if isinstance(block.input, dict)
                            else [],
                        }
                    )
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

        elif response.stop_reason == "max_tokens":
            text_chunks = []
            for block in response.content:
                if getattr(block, "type", None) == "text" and getattr(block, "text", None):
                    text_chunks.append(block.text)
            base = "\n".join(text_chunks).strip()
            response_text = (
                (base + "\n\n") if base else ""
            ) + "Reply hit a length limit. Ask a shorter follow-up if you need more detail."
            break

        else:
            text_chunks = []
            for block in response.content:
                if getattr(block, "type", None) == "text" and getattr(block, "text", None):
                    text_chunks.append(block.text)
            response_text = "\n".join(text_chunks).strip()
            if response_text:
                break
            response_text = (
                "The assistant could not finish this turn. Please try again, "
                "ideally with your model number or PS part number."
            )
            break

    return {
        "response": response_text,
        "parts": parts_data,
        "sources": kb_sources,
        "messages": output_messages,
        "debug": (
            {
                "tool_calls": tool_call_trace,
                "used_live_tools": any(
                    tc.get("name") not in {"knowledge_search"} for tc in tool_call_trace
                ),
            }
            if os.getenv("PARTSELECT_DEBUG", "").lower() in {"1", "true", "yes"}
            else {}
        ),
    }