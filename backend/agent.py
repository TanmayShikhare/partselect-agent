import anthropic
import json
import os
from dotenv import load_dotenv
from tools import TOOLS, execute_tool

load_dotenv()

# Use async client to avoid blocking FastAPI's event loop.
client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """You are a helpful customer service assistant for PartSelect, an e-commerce website that sells appliance parts. You specialize exclusively in Refrigerator and Dishwasher parts.

Your primary functions are:
1. Help customers find the right parts for their refrigerator or dishwasher
2. Provide detailed product information including price, stock status, and compatibility
3. Guide customers through the repair process with step-by-step instructions
4. Assist customers with their purchasing journey - from finding the right part to completing their order on PartSelect
5. Help with post-purchase support - order tracking, returns, and customer service

IMPORTANT RULES:
- You ONLY help with refrigerator and dishwasher parts. If asked about any other appliance (washer, dryer, oven, microwave, etc.), politely decline and redirect to your area of expertise.
- Always use your tools to fetch real, live data from PartSelect before answering product questions
- When showing parts, always include the price, stock status, and a direct link to buy on PartSelect
- Remember the customer's appliance model number throughout the conversation if they mention it
- Be warm, helpful, and concise

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


async def run_agent(messages: list, session_data: dict = {}) -> dict:
    """
    Run the PartSelect agent with conversation history.
    Returns the agent's response and any parts data found.
    """
    response_text = ""
    parts_data = []

    # Agentic loop - keep going until we get a final response
    while True:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages
        )

        # If Claude wants to use a tool
        if response.stop_reason == "tool_use":
            # Add Claude's response to messages
            messages.append({
                "role": "assistant",
                "content": response.content
            })

            # Process all tool calls
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"Tool called: {block.name} with {block.input}")
                    result = await execute_tool(block.name, block.input)

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
            messages.append({
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
        "messages": messages
    }