# Claude Code CLI Bridge - Complete Guide

This bridge enables OpenEvolve to use a **dedicated Claude Code CLI subprocess** for autonomous kernel optimization, without making direct API calls to Anthropic.

## Architecture

```
┌──────────────┐         ┌────────────────────┐         ┌─────────────────┐
│  OpenEvolve  │ HTTP    │  CLI Bridge        │ stdin/  │  Claude Code    │
│              │────────►│  (FastAPI)         │ stdout  │  CLI Subprocess │
│  Iteration   │ OpenAI  │                    │────────►│                 │
│  Loop        │ format  │  Response capture  │         │  (Dedicated)    │
│              │◄────────│  with end markers  │◄────────│                 │
└──────────────┘         └────────────────────┘         └─────────────────┘
```

## How It Works

### 1. **Subprocess Management**

The bridge spawns a dedicated `claude-code` CLI process:

```python
claude_process = pexpect.spawn('claude-code', encoding='utf-8')
```

This is a **separate instance** from any interactive Claude Code sessions you have running.

### 2. **Request Handling**

When OpenEvolve makes a request:

1. **Receive HTTP request** (OpenAI format)
2. **Convert to prompt text**
3. **Add end marker** (for response detection)
4. **Send to CLI subprocess** via stdin
5. **Capture output** in background thread
6. **Detect completion** (marker or inactivity)
7. **Return response** (OpenAI format)

### 3. **Response Detection Strategy**

The hardest part: knowing when Claude's response is complete.

**Method 1: End Marker**
```
Prompt sent to Claude:
"Optimize this kernel: [code]

IMPORTANT: When you finish, output exactly:
<<<END_OF_RESPONSE>>>"
```

When we see `<<<END_OF_RESPONSE>>>`, we know the response is complete.

**Method 2: Inactivity Timeout**
- If no new output for 10 seconds → assume done
- Fallback if marker doesn't appear

### 4. **Background Output Reader**

A dedicated thread continuously reads from the CLI:

```python
def output_reader_thread():
    while running:
        line = process.readline()
        queue.put(line)  # Send to main thread
```

This prevents blocking and allows async operation.

## Installation & Setup

### Prerequisites

1. **Claude Code CLI must be installed**

   Test it works:
   ```bash
   claude-code --version
   # or just
   claude-code
   ```

   If not installed, follow: https://claude.ai/code

2. **Python dependencies**

   ```bash
   pip install fastapi uvicorn pexpect requests
   ```

### Quick Start

```bash
# 1. Start the bridge
python claude_cli_bridge_robust.py

# Wait for:
# ✅ Claude CLI subprocess ready
# 🚀 Starting HTTP server on http://localhost:8000

# 2. In another terminal, test it
python test_cli_bridge.py

# Should show:
# 🎉 All tests passed! Bridge is working correctly.

# 3. Configure OpenEvolve
cd examples/cuda_solve_tri_opt
# Edit config.yaml (see below)

# 4. Run OpenEvolve
python ../../openevolve-run.py initial_program.py evaluator.py --config config.yaml --iterations 100
```

## Configuration

### OpenEvolve config.yaml

```yaml
llm:
  primary_model: "claude-code-cli"  # Model name (doesn't matter)
  primary_model_weight: 1.0
  api_base: "http://localhost:8000/v1"  # Bridge URL
  api_key: "not-needed"  # CLI doesn't need API key
  temperature: 0.8
  max_tokens: 8192
  timeout: 600  # 10 minutes (CLI can be slow)
```

**Important settings:**
- `timeout: 600` - CLI responses can take longer than API
- `api_base` must point to the bridge (localhost:8000)

## Autonomous Operation

### Running Overnight

Use `tmux` or `screen` to keep processes running:

```bash
# Terminal 1: Bridge (must stay running)
tmux new -s bridge
python claude_cli_bridge_robust.py
# Detach: Ctrl+B then D

# Terminal 2: OpenEvolve
tmux new -s openevolve
cd examples/cuda_solve_tri_opt
python ../../openevolve-run.py initial_program.py evaluator.py --config config.yaml --iterations 1200
# Detach: Ctrl+B then D

# Reattach later:
tmux attach -t bridge
tmux attach -t openevolve
```

### Monitoring

Check bridge status:
```bash
curl http://localhost:8000/health
```

Check OpenEvolve logs:
```bash
tail -f examples/cuda_solve_tri_opt/openevolve_output/logs/*.log
```

## Troubleshooting

### Problem: Bridge won't start

**Error:** `Failed to start Claude CLI`

**Solutions:**
1. Verify Claude Code CLI is installed:
   ```bash
   which claude-code
   claude-code --version
   ```

2. Try running manually:
   ```bash
   claude-code
   # Should start interactive session
   ```

3. Check PATH:
   ```bash
   echo $PATH
   # Should include Claude Code installation directory
   ```

### Problem: Requests timeout

**Symptom:** Bridge hangs on requests, returns 500 error

**Possible causes:**

1. **End marker not detected**
   - Claude didn't output the marker
   - Claude's response is being streamed slowly

   **Solution:** Increase `inactivity_timeout` in `claude_cli_bridge_robust.py`:
   ```python
   inactivity_timeout = 20  # Increase from 10 to 20 seconds
   ```

2. **CLI subprocess frozen**
   - Restart bridge:
     ```bash
     curl -X POST http://localhost:8000/restart
     ```

3. **Output reader thread crashed**
   - Check bridge logs for errors
   - Restart bridge entirely

### Problem: Incomplete responses

**Symptom:** Claude's response is cut off mid-sentence

**Cause:** Response detection triggered too early

**Solutions:**

1. **Check bridge logs** - see warning:
   ```
   WARNING: End marker not detected - response may be incomplete
   ```

2. **Increase inactivity timeout:**
   ```python
   inactivity_timeout = 30  # Give Claude more time
   ```

3. **Check if Claude is outputting the marker:**
   - The marker might be getting lost
   - Claude might be refusing to output it

### Problem: Tool usage captured in response

**Symptom:** Response includes Claude Code's file operations

**Example:**
```
<tool_use>
<name>Read</name>
...
</tool_use>

Here's the optimized kernel:
[actual code]
```

**Solution:**

Currently the bridge captures **everything** Claude outputs. You may need to:

1. **Post-process responses** to remove tool tags:
   ```python
   # Add to bridge after capturing response:
   response = re.sub(r'<tool_use>.*?</tool_use>', '', response, flags=re.DOTALL)
   ```

2. **Or** instruct Claude in the system message:
   ```
   Do not use any tools. Output only code directly.
   ```

### Problem: Bridge uses too much memory

**Symptom:** Bridge process grows to multiple GB

**Cause:** Output queue accumulating data

**Solution:** Restart bridge periodically:

```bash
# Add to cron or systemd
# Restart bridge every 100 iterations

curl -X POST http://localhost:8000/restart
```

## Performance Characteristics

### Latency Comparison

| Method | Latency per Request |
|--------|---------------------|
| Direct API | 5-15 seconds |
| CLI Bridge | 10-30 seconds |

**Why slower?**
- CLI startup overhead
- stdout buffering
- Response detection delay
- Tool initialization

### Reliability

**Stability factors:**
- ✅ Subprocess management (pexpect is mature)
- ⚠️ Response detection (heuristic-based)
- ⚠️ Long-running processes (memory leaks possible)
- ✅ Error recovery (automatic retry in OpenEvolve)

**Expected uptime:**
- Short runs (<100 iterations): Very reliable
- Long runs (1000+ iterations): May need restart

**Recommendation:** Monitor bridge health, restart if needed

## Advanced: Debugging

### Enable verbose logging

Edit `claude_cli_bridge_robust.py`:

```python
# Change:
logging.basicConfig(level=logging.INFO)
# To:
logging.basicConfig(level=logging.DEBUG)
```

### Capture CLI traffic

```python
# Add after line where response is received:
with open('/tmp/claude_cli_debug.log', 'a') as f:
    f.write(f"\n=== PROMPT ===\n{prompt}\n")
    f.write(f"\n=== RESPONSE ===\n{response}\n")
```

### Test CLI directly

```python
# Test script to verify CLI behavior
import pexpect

proc = pexpect.spawn('claude-code', encoding='utf-8')
proc.sendline("Say hello")
time.sleep(2)

output = []
while True:
    try:
        line = proc.readline()
        if not line:
            break
        output.append(line)
        print(line, end='')
    except pexpect.TIMEOUT:
        break

print(f"\nTotal lines: {len(output)}")
```

## Comparison with Direct API

| Aspect | CLI Bridge | Direct API |
|--------|-----------|------------|
| **Setup** | Complex (subprocess management) | Simple (API key) |
| **Reliability** | Good (with monitoring) | Excellent |
| **Latency** | 10-30s per request | 5-15s per request |
| **Cost** | Claude Code subscription | Pay per token |
| **Autonomy** | ✅ Fully autonomous | ✅ Fully autonomous |
| **Debugging** | Harder (subprocess issues) | Easier (HTTP logs) |
| **Policy Compliance** | ✅ No direct API calls | ❌ Direct API calls |

## When to Use CLI Bridge

**Use CLI bridge when:**
- ✅ Organization blocks direct API access
- ✅ You have Claude Code CLI but not API access
- ✅ Policy requires all LLM access through CLI
- ✅ You want to use Claude Code's tool ecosystem

**Use direct API when:**
- ✅ You have API access
- ✅ Maximum reliability needed
- ✅ Lower latency preferred
- ✅ Simpler infrastructure desired

## Support

**If bridge fails:**

1. Check logs in bridge terminal
2. Run test suite: `python test_cli_bridge.py`
3. Verify Claude CLI works: `claude-code`
4. Check GitHub issues (if available)

**Common "won't fix" issues:**
- Tool usage in output (designed behavior)
- Slower than API (inherent to CLI)
- Response detection imperfect (best effort)

## Summary

The CLI bridge provides a **working solution** for using Claude Code CLI with OpenEvolve, with these trade-offs:

**Pros:**
- ✅ No direct API calls (policy compliant)
- ✅ Uses dedicated Claude Code CLI instance
- ✅ Fully autonomous operation
- ✅ Works with existing Claude Code subscription

**Cons:**
- ⚠️ More complex than API
- ⚠️ Slower responses (10-30s vs 5-15s)
- ⚠️ Requires monitoring for long runs
- ⚠️ Response detection can be imperfect

**Bottom line:** If you **must** use CLI (no API allowed), this bridge enables autonomous OpenEvolve operation. Expect to monitor it and possibly restart for very long runs.
