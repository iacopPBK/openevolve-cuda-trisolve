#!/usr/bin/env python3
"""
Claude Bridge with Real-time Monitoring
Shows you what OpenEvolve is asking and what Claude responds
"""

import os
import anthropic
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import uvicorn
from datetime import datetime

app = FastAPI(title="Claude Bridge with Monitor")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Store conversation history for monitoring
conversation_log = []


class Message(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[Message]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 8192


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """OpenAI-compatible endpoint with monitoring"""

    # Extract messages
    system_message = None
    user_message = None

    for msg in request.messages:
        if msg.role == "system":
            system_message = msg.content
        elif msg.role == "user":
            user_message = msg.content

    # Print to console (so you can watch)
    print("\n" + "=" * 80)
    print(f"🕐 {datetime.now().strftime('%H:%M:%S')} - NEW REQUEST FROM OPENEVOLVE")
    print("=" * 80)

    if system_message:
        print(f"\n📋 SYSTEM PROMPT ({len(system_message)} chars):")
        print(f"   {system_message[:200]}...")

    if user_message:
        print(f"\n💬 USER MESSAGE ({len(user_message)} chars):")
        # Show first and last parts (code is usually in the middle)
        lines = user_message.split('\n')
        print(f"   {lines[0]}")
        if len(lines) > 10:
            print(f"   ... ({len(lines)-6} more lines) ...")
            for line in lines[-5:]:
                print(f"   {line[:100]}")

    print(f"\n⏳ Waiting for Claude's response...")

    try:
        # Call Claude API
        response = client.messages.create(
            model="claude-sonnet-4.5",
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            system=system_message or "",
            messages=[{"role": "user", "content": user_message}]
        )

        response_text = response.content[0].text

        # Show response
        print(f"\n✅ CLAUDE RESPONDED ({len(response_text)} chars):")
        response_lines = response_text.split('\n')
        for line in response_lines[:15]:  # First 15 lines
            print(f"   {line[:120]}")
        if len(response_lines) > 15:
            print(f"   ... ({len(response_lines)-15} more lines) ...")

        print(f"\n📊 TOKENS: Input={response.usage.input_tokens}, Output={response.usage.output_tokens}")
        print("=" * 80)

        # Log for history
        conversation_log.append({
            "timestamp": datetime.now().isoformat(),
            "prompt_chars": len(user_message) if user_message else 0,
            "response_chars": len(response_text),
            "tokens": {
                "input": response.usage.input_tokens,
                "output": response.usage.output_tokens
            }
        })

        # Return in OpenAI format
        return {
            "id": response.id,
            "object": "chat.completion",
            "model": "claude-sonnet-4.5",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_text
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens
            }
        }

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("=" * 80)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {"id": "claude-sonnet-4.5", "object": "model", "owned_by": "anthropic"}
        ]
    }


@app.get("/stats")
async def get_stats():
    """Get statistics about bridge usage"""
    if not conversation_log:
        return {"total_requests": 0}

    return {
        "total_requests": len(conversation_log),
        "total_input_tokens": sum(c["tokens"]["input"] for c in conversation_log),
        "total_output_tokens": sum(c["tokens"]["output"] for c in conversation_log),
        "history": conversation_log[-10:]  # Last 10 requests
    }


@app.get("/health")
async def health():
    return {"status": "ok", "bridge": "claude-monitor", "requests": len(conversation_log)}


if __name__ == "__main__":
    print("=" * 80)
    print("🌉 Claude Bridge with Real-Time Monitoring")
    print("=" * 80)
    print("\n📺 You'll see every interaction between OpenEvolve and Claude")
    print("💡 Keep this terminal visible while OpenEvolve runs")
    print("\n🔗 Stats available at: http://localhost:8000/stats")
    print("\n🛑 Press Ctrl+C to stop\n")
    print("=" * 80)

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
