"""
Main entry point for the PenangLens AI Agent.

This script provides:
1. Interactive CLI for testing the agent
2. Automated test scenarios
3. Environment validation
4. Web server startup
"""

import os
import sys
from dotenv import load_dotenv
from src.agent import run_agent
from src.logging_config import setup_logging, setup_langsmith, get_logger


def validate_environment():
    """
    Validate that required environment variables are set.

    Returns:
        Tuple of (missing_required, missing_optional)
    """
    required_keys = ['GOOGLE_API_KEY']
    optional_keys = ['GOOGLE_MAPS_API_KEY', 'OPENWEATHER_API_KEY']

    missing_required = []
    missing_optional = []

    for key in required_keys:
        value = os.getenv(key)
        if not value or value.startswith('your_'):
            missing_required.append(key)

    for key in optional_keys:
        value = os.getenv(key)
        if not value or value.startswith('your_'):
            missing_optional.append(key)

    return missing_required, missing_optional


def print_banner():
    """Print welcome banner."""
    print("\n" + "=" * 60)
    print("  PenangLens AI Agent v2.0 — Travel Planner")
    print("=" * 60)
    print("\nWelcome! This AI agent helps you plan travel itineraries")
    print("for Penang, Malaysia using natural language requests.")
    print("\nFeatures:")
    print("  ✅ Multi-turn conversations (memory)")
    print("  ✅ Guardrails (Penang-only)")
    print("  ✅ Self-correction (validation loop)")
    print("  ✅ Route optimization")
    print()


def run_test_scenarios():
    """Run test scenarios to validate the agent."""
    print("\n" + "=" * 60)
    print("  RUNNING TEST SCENARIOS")
    print("=" * 60 + "\n")

    test_cases = [
        {
            "name": "Test 1: Basic Planning",
            "prompt": "Plan a 2-hour history tour in George Town.",
            "expected": "Agent selects history sites and calculates travel time. Total < 2 hours."
        },
        {
            "name": "Test 2: Multi-turn (follows Test 1)",
            "prompt": "Can you add a food stop to that itinerary?",
            "expected": "Agent modifies the previous itinerary by adding a restaurant.",
            "thread_id": "test-thread-1"
        },
        {
            "name": "Test 3: Guardrail — Off-topic",
            "prompt": "Plan a trip to Tokyo.",
            "expected": "Agent politely declines and redirects to Penang."
        },
        {
            "name": "Test 4: Constraint Handling",
            "prompt": "Plan a visit to Fort Cornwallis at 3 AM.",
            "expected": "Agent checks opening hours and informs that it's closed at 3 AM."
        },
    ]

    # Use a shared thread for multi-turn test
    thread_id = "test-thread-1"

    for i, test in enumerate(test_cases, 1):
        print(f"\n{'─' * 60}")
        print(f"  {test['name']}")
        print(f"{'─' * 60}")
        print(f"Expected: {test['expected']}\n")

        try:
            tid = test.get("thread_id", thread_id if i <= 2 else None)
            result = run_agent(test['prompt'], thread_id=tid, verbose=True)

            # Print result
            messages = result["state"]["messages"]
            final = messages[-1] if messages else None
            if hasattr(final, 'content'):
                print(f"\nAgent Response:\n{final.content[:500]}")
            if result.get("blocked"):
                print("\n⚠️  Query was blocked by guardrails")

        except Exception as e:
            print(f"\n❌ ERROR: {str(e)}\n")

        if i < len(test_cases):
            input("\nPress Enter to continue to next test...")

    print("\n" + "=" * 60)
    print("  TEST SCENARIOS COMPLETED")
    print("=" * 60 + "\n")


def interactive_mode():
    """Run the agent in interactive mode with persistent session."""
    print("\n" + "=" * 60)
    print("  INTERACTIVE MODE")
    print("=" * 60)
    print("\nEnter your travel requests (or 'quit' to exit)")
    print("Your conversation will be remembered across messages.")
    print("Example: 'Plan a 3-hour heritage walk starting at 9 AM'\n")

    import uuid
    thread_id = str(uuid.uuid4())
    print(f"Session: {thread_id[:8]}...\n")

    while True:
        try:
            user_input = input("\nYou: ").strip()

            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\nGoodbye! 👋\n")
                break

            if user_input.lower() == 'new':
                thread_id = str(uuid.uuid4())
                print(f"\n🔄 New session: {thread_id[:8]}...\n")
                continue

            if not user_input:
                continue

            result = run_agent(user_input, thread_id=thread_id, verbose=True)

            # Print response
            messages = result["state"]["messages"]
            final = messages[-1] if messages else None
            if hasattr(final, 'content'):
                print(f"\nAgent: {final.content}")

        except KeyboardInterrupt:
            print("\n\nGoodbye! 👋\n")
            break
        except Exception as e:
            print(f"\n❌ ERROR: {str(e)}\n")


def main():
    """Main entry point."""
    load_dotenv()

    # Setup logging
    setup_logging(level=os.getenv("LOG_LEVEL", "INFO"))
    setup_langsmith()

    print_banner()

    # Validate environment
    missing_required, missing_optional = validate_environment()

    if missing_required:
        print("❌ ERROR: Missing required API keys:")
        for key in missing_required:
            print(f"   - {key}")
        print("\nPlease configure these in your .env file.")
        print("Get your Google Gemini API key from:")
        print("https://makersuite.google.com/app/apikey\n")
        sys.exit(1)

    if missing_optional:
        print("⚠️  WARNING: Optional API keys not configured:")
        for key in missing_optional:
            print(f"   - {key}")
        print("\nThe agent will use mock data for these features.\n")
    else:
        print("✅ All API keys configured!\n")

    # Check command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == '--test':
            run_test_scenarios()
        elif sys.argv[1] == '--web':
            print("Starting web server...")
            import uvicorn
            uvicorn.run("app:app", host="0.0.0.0", port=8000, log_level="info", reload=True)
        elif sys.argv[1] == '--help':
            print("Usage:")
            print("  python main.py           # Interactive mode")
            print("  python main.py --test    # Run test scenarios")
            print("  python main.py --web     # Start web server")
            print("  python main.py --help    # Show this help")
            print()
        else:
            # Treat the argument as a direct request
            request = ' '.join(sys.argv[1:])
            result = run_agent(request, verbose=True)
            messages = result["state"]["messages"]
            final = messages[-1] if messages else None
            if hasattr(final, 'content'):
                print(f"\n{final.content}")
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
