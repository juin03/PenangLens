""""
Test script to reproduce the "contents are required" error.
"""

from dotenv import load_dotenv
load_dotenv()

from agent import run_agent

# Test with a simple message
print("Testing agent with simple message...")
result = run_agent("Find Malay restaurants near Fort Cornwallis", verbose=True)

print("\n\n✅ Test completed successfully!")
print(f"Final message: {result['messages'][-1].content[:200]}")
