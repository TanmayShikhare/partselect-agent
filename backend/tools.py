import os

from scraper import (
    get_part_details,
    search_parts,
    get_model_parts,
    get_repair_guide,
    check_compatibility,
    validate_model_number,
)
from knowledge_retrieval import retrieve

# Live tools are disabled by default for the case-study demo.
# Enable explicitly by setting PARTSELECT_ENABLE_LIVE_TOOLS=true.
ENABLE_LIVE_TOOLS = os.getenv("PARTSELECT_ENABLE_LIVE_TOOLS", "").lower() in {
    "1",
    "true",
    "yes",
}

# Frontend expects a consistent schema for product cards.
def normalize_part(part: dict) -> dict:
    return {
        "name": part.get("name", "") or "",
        "part_number": part.get("part_number", "") or "",
        "price": part.get("price", "") or "",
        "stock": part.get("stock", "") or "",
        "url": part.get("url", "") or "",
        "image": part.get("image", "") or "",
    }

# Normalize compatibility tool output for frontend/LLM consumption.
def normalize_compatibility(result: dict) -> dict:
    if not isinstance(result, dict):
        return {"error": "invalid compatibility result"}
    out = dict(result)
    # Ensure compatible is one of: True, False, None
    if out.get("compatible") not in (True, False, None):
        out["compatible"] = None
    return out

KNOWLEDGE_SEARCH_TOOL = {
    "name": "knowledge_search",
    "description": "Primary source: indexed PartSelect pages (models, repair guidance, help text). Use first and cite returned URLs.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What to search for, e.g. 'WRS325SDHZ ice maker not making ice', 'PS11752778 installation', 'returns policy'",
            },
            "top_k": {
                "type": "integer",
                "description": "Number of matches to return (max 8).",
                "default": 5,
            },
            "page_kind": {
                "type": "string",
                "description": "Optional metadata filter: only these indexed page kinds.",
                "enum": [
                    "model",
                    "part",
                    "blog",
                    "repair",
                    "category",
                    "ptl",
                    "other",
                ],
            },
        },
        "required": ["query"],
    },
}

LIVE_TOOLS = [
    {
        "name": "search_parts",
        "description": "Live PartSelect parts search (API).",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "appliance_type": {
                    "type": "string",
                    "enum": ["refrigerator", "dishwasher", ""],
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_part_details",
        "description": "Live part detail page (PS number).",
        "input_schema": {
            "type": "object",
            "properties": {"part_number": {"type": "string"}},
            "required": ["part_number"],
        },
    },
    {
        "name": "get_model_parts",
        "description": "Live model parts list.",
        "input_schema": {
            "type": "object",
            "properties": {"model_number": {"type": "string"}},
            "required": ["model_number"],
        },
    },
    {
        "name": "validate_model_number",
        "description": "Live model page validation.",
        "input_schema": {
            "type": "object",
            "properties": {"model_number": {"type": "string"}},
            "required": ["model_number"],
        },
    },
    {
        "name": "get_repair_guide",
        "description": "Live repair/symptom page.",
        "input_schema": {
            "type": "object",
            "properties": {
                "model_number": {"type": "string"},
                "symptom": {"type": "string"},
            },
            "required": ["symptom"],
        },
    },
    {
        "name": "check_compatibility",
        "description": "Live compatibility page.",
        "input_schema": {
            "type": "object",
            "properties": {
                "part_number": {"type": "string"},
                "model_number": {"type": "string"},
            },
            "required": ["part_number", "model_number"],
        },
    },
]

# These are the tool definitions we pass to Claude API
TOOLS = [KNOWLEDGE_SEARCH_TOOL] + (LIVE_TOOLS if ENABLE_LIVE_TOOLS else [])

async def execute_tool(tool_name: str, tool_input: dict) -> dict:
    """Execute a tool by name with given inputs"""
    try:
        if tool_name == "knowledge_search":
            q = tool_input.get("query", "")
            top_k = min(int(tool_input.get("top_k", 5) or 5), 8)
            pk = tool_input.get("page_kind")
            if isinstance(pk, str):
                pk = pk.strip() or None
            else:
                pk = None
            return retrieve(
                q,
                top_k=top_k,
                page_kind=pk,
                oversample=int(os.environ.get("PARTSELECT_RETRIEVAL_OVERSAMPLE", "2")),
                rerank_lexical=os.environ.get(
                    "PARTSELECT_RETRIEVAL_LEXICAL_RERANK", ""
                ).lower()
                in ("1", "true", "yes"),
            )
        if not ENABLE_LIVE_TOOLS:
            return {"error": "live tools disabled"}
        if tool_name == "search_parts":
            results = await search_parts(
                query=tool_input["query"],
                appliance_type=tool_input.get("appliance_type", "")
            )
            return [normalize_part(p) for p in results]
        elif tool_name == "get_part_details":
            part = await get_part_details(
                part_number=tool_input["part_number"]
            )
            # Keep extra fields for the LLM, but ensure card fields exist.
            part.update(normalize_part(part))
            return part
        elif tool_name == "get_model_parts":
            data = await get_model_parts(
                model_number=tool_input["model_number"]
            )
            if isinstance(data, dict) and "parts" in data and isinstance(data["parts"], list):
                data["parts"] = [normalize_part(p) for p in data["parts"]]
            return data
        elif tool_name == "validate_model_number":
            return await validate_model_number(model_number=tool_input["model_number"])
        elif tool_name == "get_repair_guide":
            data = await get_repair_guide(
                model_number=tool_input.get("model_number", ""),
                symptom=tool_input["symptom"]
            )
            if isinstance(data, dict) and "recommended_parts" in data and isinstance(data["recommended_parts"], list):
                data["recommended_parts"] = [normalize_part(p) for p in data["recommended_parts"]]
            return data
        elif tool_name == "check_compatibility":
            return normalize_compatibility(await check_compatibility(
                part_number=tool_input["part_number"],
                model_number=tool_input["model_number"]
            ))
        else:
            return {"error": f"Unknown tool: {tool_name}"}
    except Exception as e:
        return {"error": f"Tool execution error: {str(e)}"}