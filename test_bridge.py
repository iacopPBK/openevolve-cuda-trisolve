#!/usr/bin/env python3
"""
Quick test script to verify the Claude Code Bridge is working
"""

import openai
import sys

def test_bridge():
    """Test the bridge with a simple request"""

    print("🧪 Testing Claude Code Bridge...\n")

    # Configure client to use local bridge
    client = openai.OpenAI(
        api_key="not-needed",  # Bridge doesn't validate
        base_url="http://localhost:8000/v1"
    )

    try:
        # Test 1: List models
        print("1️⃣ Testing /v1/models endpoint...")
        models = client.models.list()
        print(f"   ✅ Found {len(models.data)} models")
        for model in models.data:
            print(f"      - {model.id}")
        print()

        # Test 2: Simple completion
        print("2️⃣ Testing chat completion...")
        response = client.chat.completions.create(
            model="claude-sonnet-4.5",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'Bridge is working!' and nothing else."}
            ],
            max_tokens=50
        )

        reply = response.choices[0].message.content
        print(f"   ✅ Got response: {reply}")
        print()

        # Test 3: Code generation (like OpenEvolve will use)
        print("3️⃣ Testing code generation (OpenEvolve-style)...")
        code_response = client.chat.completions.create(
            model="claude-sonnet-4.5",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert programmer. Generate only code, no explanations."
                },
                {
                    "role": "user",
                    "content": "Write a Python function that returns 'Hello World'. Use a docstring."
                }
            ],
            max_tokens=200,
            temperature=0.7
        )

        code = code_response.choices[0].message.content
        print(f"   ✅ Generated code:")
        print("   " + "\n   ".join(code.split("\n")[:10]))  # First 10 lines
        print()

        # Summary
        print("=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        print("\nThe bridge is working correctly.")
        print("You can now configure OpenEvolve to use:")
        print("  api_base: http://localhost:8000/v1")
        print("  api_key: any-value")
        print()
        return 0

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure the bridge is running:")
        print("   python claude_code_bridge.py")
        print("\n2. Check your ANTHROPIC_API_KEY is set:")
        print("   echo $ANTHROPIC_API_KEY")
        print("\n3. Verify the bridge is accessible:")
        print("   curl http://localhost:8000/health")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(test_bridge())
