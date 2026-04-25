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

# These are the tool definitions we pass to Claude API
TOOLS = [
    {
        "name": "knowledge_search",
        "description": "PRIMARY source: local vector index over ingested PartSelect pages. Use first for symptoms, models, repair text, blogs. Hits include `url`—cite them. Optional `page_kind` (e.g. `model`). Live PartSelect fetches are often blocked; do not assume live tools will work.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to search for, e.g. 'WRS325SDHZ ice maker not making ice', 'PS11752778', 'returns policy'"
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of matches to return (max 8).",
                    "default": 5
                },
                "page_kind": {
                    "type": "string",
                    "description": "Optional Chroma metadata filter: only these indexed page kinds.",
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
            "required": ["query"]
        }
    },
    {
        "name": "search_parts",
        "description": "OPTIONAL live PartSelect parts search (API). Often blocked; prefer knowledge_search first. Use only if KB insufficient and you accept fetch may fail.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query - can be a part name, symptom, or description e.g. 'ice maker', 'door shelf bin', 'not draining'"
                },
                "appliance_type": {
                    "type": "string",
                    "description": "Type of appliance - either 'refrigerator' or 'dishwasher'",
                    "enum": ["refrigerator", "dishwasher", ""]
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_part_details",
        "description": "OPTIONAL live part detail page (PS number). Often blocked; prefer knowledge_search for part context first. Use sparingly for price/stock when KB lacks it.",
        "input_schema": {
            "type": "object",
            "properties": {
                "part_number": {
                    "type": "string",
                    "description": "The PartSelect part number, e.g. 'PS11752778' or just '11752778'"
                }
            },
            "required": ["part_number"]
        }
    },
    {
        "name": "get_model_parts",
        "description": "OPTIONAL live model parts list. Often blocked; prefer knowledge_search with page_kind model first. Use if KB has no part list for that model.",
        "input_schema": {
            "type": "object",
            "properties": {
                "model_number": {
                    "type": "string",
                    "description": "The appliance model number e.g. 'WDT780SAEM1'"
                }
            },
            "required": ["model_number"]
        }
    },
    {
        "name": "validate_model_number",
        "description": "OPTIONAL live model page validation. Often blocked; prefer knowledge_search (model pages) first. Use only if KB did not clarify fridge vs dishwasher.",
        "input_schema": {
            "type": "object",
            "properties": {
                "model_number": {
                    "type": "string",
                    "description": "The appliance model number e.g. 'WDT780SAEM1'"
                }
            },
            "required": ["model_number"]
        }
    },
    {
        "name": "get_repair_guide",
        "description": "OPTIONAL live repair/symptom page. Often blocked; prefer knowledge_search for symptom + model first. Use if KB returned nothing useful.",
        "input_schema": {
            "type": "object",
            "properties": {
                "model_number": {
                    "type": "string",
                    "description": "The appliance model number if known, otherwise leave empty"
                },
                "symptom": {
                    "type": "string",
                    "description": "The symptom or problem description e.g. 'ice maker not working', 'not draining', 'not cooling'"
                }
            },
            "required": ["symptom"]
        }
    },
    {
        "name": "check_compatibility",
        "description": "OPTIONAL live compatibility page. Often blocked; prefer knowledge_search for fit clues first. Use if user needs explicit fit check and KB insufficient.",
        "input_schema": {
            "type": "object",
            "properties": {
                "part_number": {
                    "type": "string",
                    "description": "The PartSelect part number e.g. 'PS11752778'"
                },
                "model_number": {
                    "type": "string",
                    "description": "The appliance model number e.g. 'WDT780SAEM1'"
                }
            },
            "required": ["part_number", "model_number"]
        }
    }
]

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