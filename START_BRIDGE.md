# Claude Code Bridge Setup

This bridge allows OpenEvolve to use Claude (via Anthropic API) as its LLM backend.

## Quick Start

### 1. Install Dependencies

```bash
pip install -r bridge_requirements.txt
```

### 2. Set Your Anthropic API Key

```bash
# Get your key from: https://console.anthropic.com/settings/keys
export ANTHROPIC_API_KEY="sk-ant-api03-..."

# Or add to your shell profile for persistence:
echo 'export ANTHROPIC_API_KEY="sk-ant-api03-..."' >> ~/.bashrc
source ~/.bashrc
```

### 3. Start the Bridge Server

```bash
# In one terminal:
python claude_code_bridge.py
```

This starts a server on `http://localhost:8000` that accepts OpenAI-compatible requests and forwards them to Claude.

### 4. Configure OpenEvolve

Update your `config.yaml`:

```yaml
llm:
  primary_model: "claude-sonnet-4.5"  # Or any model name - maps to Claude
  primary_model_weight: 1.0
  api_base: "http://localhost:8000/v1"
  api_key: "not-needed"  # Bridge doesn't validate this
  temperature: 0.8
  max_tokens: 8192
  timeout: 600
```

### 5. Run OpenEvolve

```bash
# In another terminal:
cd /home/user/openevolve-cuda-trisolve/examples/cuda_solve_tri_opt

python ../../openevolve-run.py \
  initial_program.py \
  evaluator.py \
  --config config.yaml \
  --iterations 100
```

## Running Autonomously

To run overnight without terminal disconnect:

```bash
# Start bridge in background
nohup python claude_code_bridge.py > bridge.log 2>&1 &

# Save the process ID
echo $! > bridge.pid

# Run OpenEvolve in tmux/screen
tmux new -s openevolve
cd examples/cuda_solve_tri_opt
python ../../openevolve-run.py initial_program.py evaluator.py --config config.yaml --iterations 1200

# Detach: Ctrl+B then D
```

To stop the bridge later:

```bash
kill $(cat bridge.pid)
```

## Troubleshooting

### Bridge not responding

```bash
# Check if bridge is running
curl http://localhost:8000/health

# Should return: {"status":"ok","bridge":"claude-code"}
```

### API key issues

```bash
# Verify key is set
echo $ANTHROPIC_API_KEY

# Test Claude API directly
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model":"claude-sonnet-4.5","max_tokens":100,"messages":[{"role":"user","content":"Hello"}]}'
```

### OpenEvolve connection errors

Check that `api_base` in `config.yaml` points to the bridge:

```yaml
api_base: "http://localhost:8000/v1"  # NOT https://api.anthropic.com
```

## Cost Estimation

Using Claude via API:

- **Sonnet 4.5**: ~$3 per million input tokens, ~$15 per million output tokens
- **Opus 4**: ~$15 per million input tokens, ~$75 per million output tokens

For 1200 iterations of kernel optimization:
- Estimated input: ~50M tokens
- Estimated output: ~20M tokens
- **Cost with Sonnet 4.5**: ~$450
- **Cost with Opus 4**: ~$2250

## Alternative: Direct API (Simpler)

If you don't need the bridge, just use Anthropic API directly:

```yaml
llm:
  primary_model: "claude-sonnet-4.5"
  api_base: "https://api.anthropic.com/v1"
  api_key: "sk-ant-api03-..."  # Your actual key
```

This skips the bridge entirely and calls Claude directly.
