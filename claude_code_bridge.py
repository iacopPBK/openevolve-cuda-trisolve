#!/usr/bin/env python3
"""
OpenAI-compatible API bridge for Claude Code CLI
Routes OpenEvolve LLM requests to Claude via Anthropic API
"""

import os
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import anthropic
import uvicorn

app = FastAPI(title="Claude Code Bridge")

# Initialize Anthropic client
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY environment variable must be set")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


class Message(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[Message]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 8192
    top_p: Optional[float] = 1.0


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """OpenAI-compatible chat completions endpoint"""

    try:
        # Convert OpenAI format to Anthropic format
        anthropic_messages = []
        system_message = None

        for msg in request.messages:
            if msg.role == "system":
                system_message = msg.content
            else:
                anthropic_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })

        # Map model names (OpenEvolve might send various names)
        model_map = {
            "gpt-4": "claude-sonnet-4.5",
            "gpt-4-turbo": "claude-sonnet-4.5",
            "gpt-3.5-turbo": "claude-sonnet-4.5",
            "claude": "claude-sonnet-4.5",
        }

        claude_model = model_map.get(request.model, "claude-sonnet-4.5")

        # Call Claude API
        response = client.messages.create(
            model=claude_model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            system=system_message if system_message else "",
            messages=anthropic_messages
        )

        # Convert response to OpenAI format
        return {
            "id": response.id,
            "object": "chat.completion",
            "created": int(response.stop_reason or 0),
            "model": claude_model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response.content[0].text
                    },
                    "finish_reason": response.stop_reason
                }
            ],
            "usage": {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/models")
async def list_models():
    """List available models (OpenAI compatibility)"""
    return {
        "object": "list",
        "data": [
            {"id": "claude-sonnet-4.5", "object": "model", "owned_by": "anthropic"},
            {"id": "claude-opus-4", "object": "model", "owned_by": "anthropic"},
            {"id": "claude-sonnet-3-7", "object": "model", "owned_by": "anthropic"},
        ]
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok", "bridge": "claude-code"}


if __name__ == "__main__":
    print("🚀 Starting Claude Code Bridge on http://localhost:8000")
    print(f"📡 Using Anthropic API key: {ANTHROPIC_API_KEY[:8]}...")
    print("\n💡 Configure OpenEvolve to use:")
    print("   api_base: http://localhost:8000/v1")
    print("   api_key: any-value")
    print("\n🛑 Press Ctrl+C to stop\n")

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
