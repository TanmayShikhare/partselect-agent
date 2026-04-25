from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
import uvicorn
from agent import run_agent, close_agent_http_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_agent_http_client()

app = FastAPI(title="PartSelect Agent API", lifespan=lifespan)

# Allow frontend to talk to backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    conversation_history: Optional[List[dict]] = Field(default_factory=list)
    session_data: Optional[dict] = Field(default_factory=dict)

class ChatResponse(BaseModel):
    response: str
    parts: Optional[List[dict]] = Field(default_factory=list)
    # URLs/snippets from knowledge_search (RAG), for UI distinct from product cards.
    sources: Optional[List[dict]] = Field(default_factory=list)
    # Optional debug payload (only present when PARTSELECT_DEBUG=1)
    debug: Optional[dict] = Field(default_factory=dict)
    conversation_history: List[dict]

@app.get("/")
def root():
    return {"status": "PartSelect Agent API is running"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    # Hard scope enforcement (defense-in-depth).
    # If the user is clearly asking about a different appliance category, refuse without calling the LLM/tools.
    msg = request.message.lower()
    out_of_scope = [
        ("washer", ["washer", "washing machine"]),
        ("dryer", ["dryer"]),
        ("oven", ["oven", "range", "stove"]),
        ("microwave", ["microwave"]),
        ("air conditioner", ["air conditioner", "ac", "a/c"]),
        ("furnace", ["furnace"]),
        ("water heater", ["water heater"]),
        ("garbage disposal", ["garbage disposal", "disposal"]),
    ]
    in_scope_hints = ["dishwasher", "fridge", "refrigerator", "ice maker"]

    if any(hint in msg for hint in in_scope_hints):
        refused = False
    else:
        refused = False
        for label, keywords in out_of_scope:
            if any(k in msg for k in keywords):
                refused = True
                appliance_type = label
                break

    if refused:
        refusal = (
            f"I specialize in refrigerator and dishwasher parts only. "
            f"I'm not able to help with {appliance_type} parts, but I'd be happy to help you with any refrigerator or dishwasher repair needs!"
        )
        messages = request.conversation_history.copy()
        messages.append({"role": "user", "content": request.message})
        messages.append({"role": "assistant", "content": refusal})
        return ChatResponse(
            response=refusal, parts=[], sources=[], conversation_history=messages
        )

    # Build messages array for Claude
    messages = request.conversation_history.copy()
    
    # Add the new user message
    messages.append({
        "role": "user",
        "content": request.message
    })
    
    try:
        # Run the agent
        result = await run_agent(
            messages=messages,
            session_data=request.session_data
        )
    except Exception:
        failure = (
            "I ran into an internal error while generating a response. "
            "Please try again in a moment."
        )
        messages.append({"role": "assistant", "content": failure})
        return ChatResponse(
            response=failure,
            parts=[],
            sources=[],
            debug={},
            conversation_history=messages,
        )
    
    return ChatResponse(
        response=result["response"],
        parts=result["parts"],
        sources=result.get("sources") or [],
        debug=result.get("debug") or {},
        conversation_history=result["messages"],
    )

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)