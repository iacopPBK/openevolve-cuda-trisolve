#!/bin/bash
# Autonomous OpenEvolve runner with Claude Code Bridge

set -e

echo "🚀 Starting Autonomous OpenEvolve Setup"
echo "========================================"

# Check if ANTHROPIC_API_KEY is set
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "❌ ERROR: ANTHROPIC_API_KEY environment variable not set"
    echo ""
    echo "Please set it:"
    echo "  export ANTHROPIC_API_KEY='sk-ant-api03-...'"
    echo ""
    echo "Get your key from: https://console.anthropic.com/settings/keys"
    exit 1
fi

echo "✅ API key found: ${ANTHROPIC_API_KEY:0:15}..."

# Install dependencies if needed
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "📦 Installing bridge dependencies..."
    pip install -q -r bridge_requirements.txt
else
    echo "✅ Dependencies already installed"
fi

# Start bridge in background
echo "🌉 Starting Claude Code Bridge..."
python3 claude_code_bridge.py > bridge.log 2>&1 &
BRIDGE_PID=$!
echo $BRIDGE_PID > bridge.pid
echo "   Bridge PID: $BRIDGE_PID"

# Wait for bridge to start
echo "⏳ Waiting for bridge to initialize..."
for i in {1..10}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ Bridge is ready!"
        break
    fi
    sleep 1
    if [ $i -eq 10 ]; then
        echo "❌ Bridge failed to start. Check bridge.log"
        kill $BRIDGE_PID 2>/dev/null || true
        exit 1
    fi
done

# Test the bridge
echo "🧪 Testing bridge..."
python3 test_bridge.py
if [ $? -ne 0 ]; then
    echo "❌ Bridge test failed"
    kill $BRIDGE_PID 2>/dev/null || true
    exit 1
fi

echo ""
echo "=" "================================================="
echo "🎉 Setup Complete! Ready to run OpenEvolve"
echo "=================================================="
echo ""
echo "Bridge is running on http://localhost:8000"
echo "Bridge PID: $BRIDGE_PID (saved to bridge.pid)"
echo "Bridge logs: bridge.log"
echo ""
echo "To run OpenEvolve:"
echo "  cd examples/cuda_solve_tri_opt"
echo "  python ../../openevolve-run.py initial_program.py evaluator.py --config config.yaml --iterations 100"
echo ""
echo "To stop the bridge:"
echo "  kill \$(cat bridge.pid)"
echo ""
echo "To run in background (autonomous):"
echo "  tmux new -s openevolve"
echo "  # Then run OpenEvolve inside tmux"
echo "  # Detach with: Ctrl+B then D"
echo ""
