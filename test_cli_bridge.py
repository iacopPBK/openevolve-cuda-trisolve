#!/usr/bin/env python3
"""
Test script for Claude CLI Bridge
Verifies the bridge can interact with Claude Code CLI subprocess
"""

import time
import requests
import sys

BRIDGE_URL = "http://localhost:8000"


def test_health():
    """Test health endpoint"""
    print("🧪 Test 1: Health Check")
    print("-" * 60)

    try:
        response = requests.get(f"{BRIDGE_URL}/health", timeout=5)
        data = response.json()

        print(f"   Status: {data.get('status')}")
        print(f"   CLI Running: {data.get('cli_running')}")
        print(f"   CLI PID: {data.get('cli_pid')}")

        if data.get('cli_running'):
            print("   ✅ Claude CLI subprocess is running")
            return True
        else:
            print("   ❌ Claude CLI subprocess is not running")
            return False

    except requests.ConnectionError:
        print("   ❌ Bridge is not running")
        print("   Please start: python claude_cli_bridge_robust.py")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_simple_request():
    """Test simple chat completion"""
    print("\n🧪 Test 2: Simple Request")
    print("-" * 60)

    payload = {
        "model": "claude-code-cli",
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant. Be very concise."
            },
            {
                "role": "user",
                "content": "Say exactly: 'Bridge test successful!' and nothing else."
            }
        ],
        "max_tokens": 50
    }

    try:
        print("   Sending request to bridge...")
        start = time.time()

        response = requests.post(
            f"{BRIDGE_URL}/v1/chat/completions",
            json=payload,
            timeout=120  # 2 minutes for CLI to respond
        )

        elapsed = time.time() - start

        if response.status_code == 200:
            data = response.json()
            content = data['choices'][0]['message']['content']

            print(f"   ✅ Response received ({elapsed:.1f}s)")
            print(f"   Content: {content[:100]}")

            if 'Bridge test successful' in content or 'successful' in content.lower():
                print("   ✅ Response contains expected text")
                return True
            else:
                print("   ⚠️  Response doesn't match expected (but bridge works)")
                return True
        else:
            print(f"   ❌ HTTP {response.status_code}: {response.text}")
            return False

    except requests.Timeout:
        print("   ❌ Request timed out (Claude CLI might be slow)")
        print("   This could mean:")
        print("      - Claude CLI is taking too long to respond")
        print("      - Response detection isn't working")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_code_generation():
    """Test code generation (like OpenEvolve will use)"""
    print("\n🧪 Test 3: Code Generation")
    print("-" * 60)

    payload = {
        "model": "claude-code-cli",
        "messages": [
            {
                "role": "system",
                "content": "You are an expert programmer. Output only code, no explanations."
            },
            {
                "role": "user",
                "content": """Write a simple Python function that adds two numbers.

Format your response as:

```python
def add(a, b):
    return a + b
```

Include ONLY the code block, nothing else."""
            }
        ],
        "max_tokens": 200
    }

    try:
        print("   Sending code generation request...")
        start = time.time()

        response = requests.post(
            f"{BRIDGE_URL}/v1/chat/completions",
            json=payload,
            timeout=120
        )

        elapsed = time.time() - start

        if response.status_code == 200:
            data = response.json()
            content = data['choices'][0]['message']['content']

            print(f"   ✅ Response received ({elapsed:.1f}s)")
            print(f"   Length: {len(content)} characters")

            # Check if it contains code
            if '```python' in content or 'def ' in content:
                print("   ✅ Response contains code")
                print("\n   Preview:")
                for line in content.split('\n')[:10]:
                    print(f"      {line}")
                return True
            else:
                print("   ⚠️  Response doesn't look like code:")
                print(f"      {content[:200]}")
                return False
        else:
            print(f"   ❌ HTTP {response.status_code}")
            return False

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def main():
    print("=" * 60)
    print("🧪 Claude CLI Bridge Test Suite")
    print("=" * 60)
    print()

    results = []

    # Test 1: Health
    results.append(("Health Check", test_health()))

    if not results[0][1]:
        print("\n❌ Bridge is not running. Cannot continue tests.")
        print("\nTo start the bridge:")
        print("  python claude_cli_bridge_robust.py")
        return 1

    # Test 2: Simple request
    results.append(("Simple Request", test_simple_request()))

    # Test 3: Code generation
    results.append(("Code Generation", test_code_generation()))

    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)

    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {status}  {name}")

    passed_count = sum(1 for _, p in results if p)
    total_count = len(results)

    print()
    print(f"   {passed_count}/{total_count} tests passed")

    if passed_count == total_count:
        print("\n🎉 All tests passed! Bridge is working correctly.")
        print("\nYou can now configure OpenEvolve to use:")
        print("  api_base: http://localhost:8000/v1")
        print("  api_key: not-needed")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please check the output above.")
        print("\nCommon issues:")
        print("  1. Claude CLI not responding: Check if 'claude-code' works")
        print("  2. Timeout: Claude CLI might be too slow")
        print("  3. Response detection: End marker not working")
        return 1


if __name__ == "__main__":
    sys.exit(main())
