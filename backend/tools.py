from scraper import (
    get_part_details,
    search_parts,
    get_model_parts,
    get_repair_guide,
    check_compatibility,
    validate_model_number,
)

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
        "name": "search_parts",
        "description": "Search for refrigerator or dishwasher parts on PartSelect by keyword, part name, or symptom. Use this when the user is looking for a part but doesn't have a specific part number.",
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
        "description": "Get full details for a specific part by its PartSelect part number (PS number). Use this when the user provides a specific part number like PS11752778.",
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
        "description": "Get the most commonly replaced parts for a specific appliance model number. Use this when the user provides their appliance model number and wants to know what parts are available.",
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
        "description": "Validate a PartSelect model number by loading the model page and extracting basic evidence (title + best-effort appliance type inference). Use this before assuming whether a model is a refrigerator or dishwasher.",
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
        "description": "Get repair guide and recommended parts for a specific symptom or problem. Use this when the user describes a problem like 'ice maker not working', 'dishwasher not draining', 'fridge not cooling'.",
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
        "description": "Check if a specific part is compatible with a specific appliance model. Use this when the user asks if a part fits their model.",
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