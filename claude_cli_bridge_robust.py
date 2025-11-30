#!/usr/bin/env python3
"""
Robust Claude Code CLI Bridge for OpenEvolve
Interacts with a dedicated Claude Code CLI subprocess
"""

import os
import sys
import time
import threading
import queue
import re
from typing import Optional, List
import pexpect
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Claude Code CLI Bridge (Robust)")

# Global Claude CLI process
claude_process = None
response_queue = queue.Queue()
output_thread = None
shutdown_event = threading.Event()


class Message(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[Message]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 8192


def output_reader_thread(process, q, shutdown):
    """
    Background thread that continuously reads from Claude CLI
    and puts output lines into a queue
    """
    logger.info("Output reader thread started")

    while not shutdown.is_set():
        try:
            if process.isalive():
                try:
                    # Read with timeout so we can check shutdown event
                    line = process.readline()
                    if line:
                        q.put(('line', line))
                except pexpect.TIMEOUT:
                    # No output right now, continue
                    pass
                except pexpect.EOF:
                    logger.warning("Claude CLI process ended")
                    q.put(('eof', None))
                    break
            else:
                logger.warning("Claude CLI process is not alive")
                break

            time.sleep(0.01)  # Small delay to prevent CPU spinning

        except Exception as e:
            logger.error(f"Error in output reader: {e}")
            q.put(('error', str(e)))
            break

    logger.info("Output reader thread stopped")


def start_claude_cli():
    """Start Claude Code CLI as a subprocess with output monitoring"""
    global claude_process, output_thread, shutdown_event

    if claude_process is not None and claude_process.isalive():
        logger.info("Claude CLI already running")
        return True

    logger.info("Starting Claude Code CLI subprocess...")

    # Find claude-code command
    claude_cmd = 'claude-code'

    # Check if command exists
    try:
        # Try to find claude-code in PATH
        import shutil
        if not shutil.which(claude_cmd):
            logger.error(f"'{claude_cmd}' not found in PATH")
            logger.info("Please ensure Claude Code CLI is installed")
            return False
    except Exception as e:
        logger.warning(f"Could not verify claude-code command: {e}")

    try:
        # Start Claude Code CLI
        # Use a large buffer to prevent blocking
        claude_process = pexpect.spawn(
            claude_cmd,
            encoding='utf-8',
            timeout=None,  # We'll handle timeouts ourselves
            maxread=65536,  # Large read buffer
            searchwindowsize=None  # Search entire buffer
        )

        logger.info("Claude CLI process started (PID: %s)", claude_process.pid)

        # Start background thread to read output
        shutdown_event.clear()
        response_queue.queue.clear()  # Clear any old data

        output_thread = threading.Thread(
            target=output_reader_thread,
            args=(claude_process, response_queue, shutdown_event),
            daemon=True
        )
        output_thread.start()

        # Wait for initial startup (Claude might print banner)
        logger.info("Waiting for Claude CLI to initialize...")
        time.sleep(2)

        # Drain any startup messages
        startup_lines = []
        while not response_queue.empty():
            msg_type, data = response_queue.get_nowait()
            if msg_type == 'line':
                startup_lines.append(data)

        if startup_lines:
            logger.info("Claude CLI startup output (%d lines)", len(startup_lines))

        logger.info("Claude CLI ready")
        return True

    except Exception as e:
        logger.error(f"Failed to start Claude CLI: {e}")
        return False


def send_prompt_to_claude(prompt: str, timeout: int = 600) -> str:
    """
    Send a prompt to Claude CLI and capture the complete response

    Strategy:
    1. Send prompt with a special END marker
    2. Read output until we see the marker or timeout
    3. Use inactivity detection (no output for N seconds = done)
    """
    global claude_process, response_queue

    if claude_process is None or not claude_process.isalive():
        if not start_claude_cli():
            raise Exception("Failed to start Claude CLI")

    # Clear the queue before sending new prompt
    while not response_queue.empty():
        try:
            response_queue.get_nowait()
        except queue.Empty:
            break

    # Prepare prompt with instructions and marker
    # Ask Claude to end with a specific marker so we know when response is complete
    end_marker = "<<<END_OF_RESPONSE>>>"

    enhanced_prompt = f"""{prompt}

IMPORTANT: When you finish your response, output exactly this marker on a new line:
{end_marker}

This marker is essential for the system to know you've completed your response."""

    logger.info("Sending prompt to Claude (%d chars)", len(prompt))

    # Send the prompt
    try:
        claude_process.sendline(enhanced_prompt)
    except Exception as e:
        logger.error(f"Failed to send prompt: {e}")
        raise Exception(f"Failed to send prompt: {e}")

    # Collect response
    response_lines = []
    last_output_time = time.time()
    start_time = time.time()
    inactivity_timeout = 10  # If no output for 10 seconds, consider done
    marker_seen = False

    logger.info("Waiting for Claude's response (timeout: %ds)...", timeout)

    while time.time() - start_time < timeout:
        try:
            # Check for new output with a short timeout
            msg_type, data = response_queue.get(timeout=0.5)

            if msg_type == 'line':
                last_output_time = time.time()

                # Check if this line contains the end marker
                if end_marker in data:
                    logger.info("End marker detected - response complete")
                    marker_seen = True
                    # Don't include the marker in the response
                    # But include everything before it
                    parts = data.split(end_marker)
                    if parts[0].strip():
                        response_lines.append(parts[0])
                    break

                # Accumulate response
                response_lines.append(data)

            elif msg_type == 'eof':
                logger.warning("Claude CLI process ended unexpectedly")
                break

            elif msg_type == 'error':
                logger.error(f"Error reading from Claude: {data}")
                break

        except queue.Empty:
            # No new output - check if we've been inactive too long
            if response_lines and (time.time() - last_output_time) > inactivity_timeout:
                logger.info("No output for %ds - assuming response complete", inactivity_timeout)
                break

    # Check if we got a response
    if not response_lines:
        raise Exception("No response received from Claude CLI")

    # Join all response lines
    response = ''.join(response_lines)

    # Remove the instruction we added about the marker
    # (Claude might have acknowledged it)
    response = re.sub(
        r'\n*IMPORTANT: When you finish your response.*?END_OF_RESPONSE>>>\s*\n*',
        '',
        response,
        flags=re.DOTALL
    )

    logger.info("Received response from Claude (%d chars, %d lines)",
                len(response), len(response_lines))

    if not marker_seen:
        logger.warning("End marker not detected - response may be incomplete")

    return response.strip()


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """OpenAI-compatible chat completions endpoint"""

    logger.info("=" * 80)
    logger.info("New request from OpenEvolve")

    try:
        # Build full prompt from messages
        full_prompt = ""

        for msg in request.messages:
            if msg.role == "system":
                full_prompt += f"[SYSTEM INSTRUCTIONS]\n{msg.content}\n\n"
            elif msg.role == "user":
                full_prompt += msg.content

        logger.info("Prompt size: %d characters", len(full_prompt))

        # Send to Claude CLI
        response_text = send_prompt_to_claude(full_prompt, timeout=600)

        logger.info("Response size: %d characters", len(response_text))
        logger.info("=" * 80)

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
        logger.error(f"Error processing request: {e}", exc_info=True)
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
    is_alive = claude_process is not None and claude_process.isalive()
    return {
        "status": "ok" if is_alive else "degraded",
        "bridge": "claude-cli-robust",
        "cli_running": is_alive,
        "cli_pid": claude_process.pid if is_alive else None
    }


@app.post("/restart")
async def restart_cli():
    """Restart Claude CLI subprocess (for debugging)"""
    global claude_process, shutdown_event

    logger.info("Restarting Claude CLI...")

    # Stop current process
    if claude_process and claude_process.isalive():
        shutdown_event.set()
        claude_process.close()
        time.sleep(1)

    # Start new process
    if start_claude_cli():
        return {"status": "restarted", "pid": claude_process.pid}
    else:
        raise HTTPException(status_code=500, detail="Failed to restart CLI")


@app.on_event("shutdown")
async def shutdown():
    """Clean up on shutdown"""
    global claude_process, shutdown_event

    logger.info("Shutting down bridge...")

    # Signal output thread to stop
    shutdown_event.set()

    # Close Claude CLI process
    if claude_process and claude_process.isalive():
        logger.info("Closing Claude CLI process...")
        claude_process.close()

    logger.info("Shutdown complete")


if __name__ == "__main__":
    print("=" * 80)
    print("🌉 Claude Code CLI Bridge (Robust)")
    print("=" * 80)
    print()
    print("⚠️  This bridge interacts with a dedicated Claude Code CLI subprocess")
    print("📋 Requirements:")
    print("   - Claude Code CLI must be installed and in PATH")
    print("   - Command: 'claude-code' must work in terminal")
    print()
    print("🔧 How it works:")
    print("   1. Spawns a Claude Code CLI subprocess")
    print("   2. Sends OpenEvolve prompts to it")
    print("   3. Captures responses using end markers and inactivity detection")
    print("   4. Returns responses in OpenAI-compatible format")
    print()
    print("💡 Configure OpenEvolve:")
    print("   api_base: http://localhost:8000/v1")
    print("   api_key: not-needed")
    print()
    print("🔍 Endpoints:")
    print("   POST /v1/chat/completions - Main API")
    print("   GET  /health              - Health check")
    print("   POST /restart             - Restart CLI subprocess")
    print()
    print("🛑 Press Ctrl+C to stop")
    print("=" * 80)
    print()

    # Start Claude CLI before starting server
    if not start_claude_cli():
        print("❌ Failed to start Claude CLI. Please check:")
        print("   1. Is 'claude-code' installed?")
        print("   2. Does 'claude-code' work in your terminal?")
        print("   3. Are there any error messages above?")
        sys.exit(1)

    print("✅ Claude CLI subprocess ready")
    print("🚀 Starting HTTP server on http://localhost:8000")
    print()

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
