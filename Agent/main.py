"""
Main entry point for the PenangLens AI Agent POC.

This script provides:
1. Interactive CLI for testing the agent
2. Automated test scenarios
3. Environment validation
"""

import os
import sys
from dotenv import load_dotenv
from src.agent import run_agent


def validate_environment():
    """
    Validate that required environment variables are set.
    
    Returns:
        Tuple of (is_valid, missing_keys)
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
    print("\n" + "="*60)
    print("  PenangLens AI Agent - Itinerary Planner POC")
    print("="*60)
    print("\nWelcome! This AI agent helps you plan travel itineraries")
    print("for Penang, Malaysia using natural language requests.\n")


def run_test_scenarios():
    """
    Run the three test scenarios from the guide.
    """
    print("\n" + "="*60)
    print("  RUNNING TEST SCENARIOS")
    print("="*60 + "\n")
    
    test_cases = [
        {
            "name": "Test 1: Basic Planning",
            "prompt": "Plan a 2-hour history tour in George Town.",
            "expected": "Agent selects 1-2 history sites and calculates travel time. Total < 2 hours."
        },
        {
            "name": "Test 2: Logic & Math",
            "prompt": "I want to visit Fort Cornwallis and then Penang Street Art. How long will it take?",
            "expected": "Agent calls travel time API and sums visit + travel durations correctly."
        },
        {
            "name": "Test 3: Constraint Handling",
            "prompt": "Plan a visit to Fort Cornwallis at 3 AM.",
            "expected": "Agent checks opening hours and informs that it's closed at 3 AM."
        }
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n{'─'*60}")
        print(f"  {test['name']}")
        print(f"{'─'*60}")
        print(f"Expected: {test['expected']}\n")
        
        try:
            run_agent(test['prompt'], verbose=True)
        except Exception as e:
            print(f"\n❌ ERROR: {str(e)}\n")
        
        if i < len(test_cases):
            input("\nPress Enter to continue to next test...")
    
    print("\n" + "="*60)
    print("  TEST SCENARIOS COMPLETED")
    print("="*60 + "\n")


def interactive_mode():
    """
    Run the agent in interactive mode.
    """
    print("\n" + "="*60)
    print("  INTERACTIVE MODE")
    print("="*60)
    print("\nEnter your travel requests (or 'quit' to exit)")
    print("Example: 'Plan a 3-hour heritage walk starting at 9 AM'\n")
    
    while True:
        try:
            user_input = input("\nYour request: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\nGoodbye! 👋\n")
                break
            
            if not user_input:
                continue
            
            run_agent(user_input, verbose=True)
            
        except KeyboardInterrupt:
            print("\n\nGoodbye! 👋\n")
            break
        except Exception as e:
            print(f"\n❌ ERROR: {str(e)}\n")


def main():
    """Main entry point."""
    # Load environment variables
    load_dotenv()
    
    # Print banner
    print_banner()
    
    # Validate environment
    missing_required, missing_optional = validate_environment()
    
    if missing_required:
        print("❌ ERROR: Missing required API keys:")
        for key in missing_required:
            print(f"   - {key}")
        print("\nPlease configure these in your .env file.")
        print("See .env.example for the template.\n")
        print("Get your Google Gemini API key from:")
        print("https://makersuite.google.com/app/apikey\n")
        sys.exit(1)
    
    if missing_optional:
        print("⚠️  WARNING: Optional API keys not configured:")
        for key in missing_optional:
            print(f"   - {key}")
        print("\nThe agent will use mock data for these features.")
        print("For full functionality, configure these in your .env file.\n")
    else:
        print("✅ All API keys configured!\n")
    
    # Check command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == '--test':
            run_test_scenarios()
        elif sys.argv[1] == '--help':
            print("Usage:")
            print("  python main.py           # Interactive mode")
            print("  python main.py --test    # Run test scenarios")
            print("  python main.py --help    # Show this help")
            print()
        else:
            # Treat the argument as a direct request
            request = ' '.join(sys.argv[1:])
            run_agent(request, verbose=True)
    else:
        # Interactive mode
        interactive_mode()


if __name__ == "__main__":
    main()
