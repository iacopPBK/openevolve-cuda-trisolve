#!/usr/bin/env python3
"""
Bridge that interacts with Claude Code CLI subprocess
Uses pexpect to automate the interactive CLI session
"""

import os
import re
import time
import pexpect
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from typing import Optional, List

app = FastAPI(title="Claude Code CLI Bridge")

# Global Claude Code CLI process
claude_process = None


class Message(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[Message]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 8192


def start_claude_cli():
    """Start Claude Code CLI as a subprocess"""
    global claude_process

    if claude_process is not None:
        return

    print("🚀 Starting Claude Code CLI subprocess...")

    # Start Claude Code CLI
    # Adjust the command based on how you normally start Claude Code
    claude_process = pexpect.spawn('claude-code', encoding='utf-8', timeout=600)

    # Wait for initial prompt
    # The CLI typically shows a prompt like "You:" or similar
    try:
        claude_process.expect(['You:', 'claude>', '>>>', r'\$'], timeout=30)
        print("✅ Claude Code CLI ready")
    except pexpect.TIMEOUT:
        print("⚠️  Warning: Couldn't detect prompt, continuing anyway")


def send_prompt_to_claude(prompt: str, timeout: int = 600) -> str:
    """
    Send a prompt to Claude Code CLI and capture response

    This is the tricky part - we need to:
    1. Send the prompt
    2. Wait for Claude's full response
    3. Detect when the response is complete
    """
    global claude_process

    if claude_process is None:
        start_claude_cli()

    # Send the prompt
    claude_process.sendline(prompt)

    # Wait for response to complete
    # This is challenging because we need to detect when Claude is done

    # Strategy: Look for the next prompt (indicating Claude finished)
    # Typical patterns: "You:", "claude>", or similar

    response_lines = []
    start_time = time.time()

    try:
        # Read until we see the next prompt
        while time.time() - start_time < timeout:
            try:
                # Read a line
                line = claude_process.readline()

                if not line:
                    time.sleep(0.1)
                    continue

                # Check if this is the prompt (response is done)
                if re.match(r'^(You:|claude>|>>>|\$)\s*$', line.strip()):
                    break

                # Accumulate response
                response_lines.append(line)

            except pexpect.TIMEOUT:
                # No more output for a bit, might be done
                if response_lines:
                    break

    except Exception as e:
        print(f"Error reading response: {e}")

    # Join all response lines
    response = ''.join(response_lines).strip()

    return response


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """OpenAI-compatible chat completions endpoint"""

    try:
        # Build a single prompt from messages
        # Combine system message and user message
        full_prompt = ""

        for msg in request.messages:
            if msg.role == "system":
                full_prompt += f"[SYSTEM INSTRUCTIONS]\n{msg.content}\n\n"
            elif msg.role == "user":
                full_prompt += msg.content

        print(f"\n📤 Sending to Claude CLI ({len(full_prompt)} chars):")
        print(f"   {full_prompt[:100]}...")

        # Send to Claude Code CLI subprocess
        response_text = send_prompt_to_claude(full_prompt, timeout=600)

        print(f"📥 Received from Claude ({len(response_text)} chars):")
        print(f"   {response_text[:100]}...")

        # Return in OpenAI format
        return {
            "id": f"cli-{int(time.time())}",
            "object": "chat.completion",
            "model": "claude-code-cli",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_text
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": len(full_prompt.split()),
                "completion_tokens": len(response_text.split()),
                "total_tokens": len(full_prompt.split()) + len(response_text.split())
            }
        }

    except Exception as e:
        print(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/models")
async def list_models():
    """List available models"""
    return {
        "object": "list",
        "data": [
            {"id": "claude-code-cli", "object": "model", "owned_by": "anthropic"}
        ]
    }


@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "ok",
        "bridge": "claude-cli",
        "cli_running": claude_process is not None
    }


@app.on_event("shutdown")
async def shutdown():
    """Clean up Claude CLI process on shutdown"""
    global claude_process
    if claude_process:
        print("🛑 Shutting down Claude CLI subprocess...")
        claude_process.close()


if __name__ == "__main__":
    print("🌉 Claude Code CLI Bridge")
    print("=" * 60)
    print("⚠️  WARNING: This is experimental!")
    print("⚠️  This approach automates the Claude Code CLI interface")
    print("=" * 60)
    print()

    # Start Claude CLI
    start_claude_cli()

    print("\n💡 Configure OpenEvolve to use:")
    print("   api_base: http://localhost:8000/v1")
    print("\n🛑 Press Ctrl+C to stop\n")

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
