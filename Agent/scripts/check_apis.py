"""
API Test Script for PenangLens AI Agent

This script tests all required API keys to ensure they are properly configured:
1. Google Gemini API (for AI agent)
2. Google Maps Distance Matrix API (for travel times)
3. Google Places API (for nearby search)
4. Google Geocoding API (for location lookup)

Run this script after setting up your .env file to verify everything works.
"""

import os
import sys
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_header(text):
    """Print a formatted header."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{text.center(60)}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")

def print_success(text):
    """Print success message."""
    print(f"{GREEN}✅ {text}{RESET}")

def print_error(text):
    """Print error message."""
    print(f"{RED}❌ {text}{RESET}")

def print_warning(text):
    """Print warning message."""
    print(f"{YELLOW}⚠️  {text}{RESET}")

def print_info(text):
    """Print info message."""
    print(f"{BLUE}ℹ️  {text}{RESET}")


def test_gemini_api():
    """Test Google Gemini API."""
    print_header("Testing Google Gemini API")
    
    api_key = os.getenv('GOOGLE_API_KEY')
    
    if not api_key or api_key == 'your_google_gemini_api_key_here':
        print_error("GOOGLE_API_KEY not configured in .env file")
        return False
    
    print_info(f"API Key found: {api_key[:10]}...{api_key[-4:]}")
    
    try:
        # Test with a simple request
        from langchain_google_genai import ChatGoogleGenerativeAI
        
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash-lite",
            google_api_key=api_key,
            temperature=0.7,
        )
        
        # Simple test message
        response = llm.invoke("Say 'Hello from Gemini!'")
        
        print_success("Gemini API is working!")
        print_info(f"Response: {response.content}")
        return True
        
    except Exception as e:
        print_error(f"Gemini API test failed: {str(e)}")
        print_info("Make sure you have the correct API key from: https://makersuite.google.com/app/apikey")
        return False


def test_distance_matrix_api():
    """Test Google Maps Distance Matrix API."""
    print_header("Testing Distance Matrix API")
    
    api_key = os.getenv('GOOGLE_MAPS_API_KEY')
    
    if not api_key or api_key == 'your_google_maps_api_key_here':
        print_error("GOOGLE_MAPS_API_KEY not configured in .env file")
        return False
    
    print_info(f"API Key found: {api_key[:10]}...{api_key[-4:]}")
    
    try:
        url = "https://maps.googleapis.com/maps/api/distancematrix/json"
        params = {
            'origins': 'Fort Cornwallis, Penang, Malaysia',
            'destinations': 'Penang Street Art, Armenian Street, Penang, Malaysia',
            'mode': 'driving',
            'key': api_key
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data['status'] == 'OK':
            element = data['rows'][0]['elements'][0]
            if element['status'] == 'OK':
                duration = element['duration']['text']
                distance = element['distance']['text']
                print_success("Distance Matrix API is working!")
                print_info(f"Test route: Fort Cornwallis → Penang Street Art")
                print_info(f"Travel time: {duration} ({distance})")
                return True
            else:
                print_error(f"Route calculation failed: {element['status']}")
                return False
        else:
            print_error(f"API Error: {data['status']}")
            if data['status'] == 'REQUEST_DENIED':
                print_warning("Distance Matrix API is not enabled in your Google Cloud project")
                print_info("Enable it at: https://console.cloud.google.com/apis/library/distance-matrix-backend.googleapis.com")
            return False
            
    except Exception as e:
        print_error(f"Distance Matrix API test failed: {str(e)}")
        return False


def test_geocoding_api():
    """Test Google Geocoding API."""
    print_header("Testing Geocoding API")
    
    api_key = os.getenv('GOOGLE_MAPS_API_KEY')
    
    if not api_key or api_key == 'your_google_maps_api_key_here':
        print_error("GOOGLE_MAPS_API_KEY not configured")
        return False
    
    try:
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            'address': 'Fort Cornwallis, Penang, Malaysia',
            'key': api_key
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data['status'] == 'OK':
            location = data['results'][0]['geometry']['location']
            print_success("Geocoding API is working!")
            print_info(f"Test location: Fort Cornwallis")
            print_info(f"Coordinates: {location['lat']}, {location['lng']}")
            return True
        else:
            print_error(f"API Error: {data['status']}")
            if data['status'] == 'REQUEST_DENIED':
                print_warning("Geocoding API is not enabled in your Google Cloud project")
                print_info("Enable it at: https://console.cloud.google.com/apis/library/geocoding-backend.googleapis.com")
            return False
            
    except Exception as e:
        print_error(f"Geocoding API test failed: {str(e)}")
        return False


def test_places_api():
    """Test Google Places API."""
    print_header("Testing Places API (Nearby Search)")
    
    api_key = os.getenv('GOOGLE_MAPS_API_KEY')
    
    if not api_key or api_key == 'your_google_maps_api_key_here':
        print_error("GOOGLE_MAPS_API_KEY not configured")
        return False
    
    try:
        # First geocode to get coordinates
        geocode_url = "https://maps.googleapis.com/maps/api/geocode/json"
        geocode_params = {
            'address': 'George Town, Penang, Malaysia',
            'key': api_key
        }
        
        geocode_response = requests.get(geocode_url, params=geocode_params, timeout=10)
        geocode_data = geocode_response.json()
        
        if geocode_data['status'] != 'OK':
            print_error("Could not geocode location for Places API test")
            return False
        
        location = geocode_data['results'][0]['geometry']['location']
        lat = location['lat']
        lng = location['lng']
        
        # Now test Places API
        places_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        places_params = {
            'location': f"{lat},{lng}",
            'radius': 2000,
            'type': 'restaurant',
            'key': api_key
        }
        
        places_response = requests.get(places_url, params=places_params, timeout=10)
        places_data = places_response.json()
        
        if places_data['status'] == 'OK':
            results = places_data.get('results', [])
            print_success("Places API is working!")
            print_info(f"Found {len(results)} restaurants near George Town")
            if results:
                print_info(f"Example: {results[0]['name']} ({results[0].get('rating', 'N/A')}★)")
            return True
        else:
            print_error(f"API Error: {places_data['status']}")
            if places_data['status'] == 'REQUEST_DENIED':
                print_warning("Places API is not enabled in your Google Cloud project")
                print_info("Enable it at: https://console.cloud.google.com/apis/library/places-backend.googleapis.com")
            return False
            
    except Exception as e:
        print_error(f"Places API test failed: {str(e)}")
        return False


def main():
    """Run all API tests."""
    print_header("PenangLens API Configuration Test")
    print_info("This script will test all required API keys")
    print_info("Make sure you have configured your .env file\n")
    
    results = {
        'Gemini API': test_gemini_api(),
        'Distance Matrix API': test_distance_matrix_api(),
        'Geocoding API': test_geocoding_api(),
        'Places API': test_places_api()
    }
    
    # Summary
    print_header("Test Summary")
    
    all_passed = True
    for api_name, passed in results.items():
        if passed:
            print_success(f"{api_name}: PASSED")
        else:
            print_error(f"{api_name}: FAILED")
            all_passed = False
    
    print()
    
    if all_passed:
        print_success("🎉 All APIs are configured correctly!")
        print_info("You're ready to run the PenangLens AI agent!")
        print_info("Start the web UI with: python app.py")
        return 0
    else:
        print_error("⚠️  Some APIs are not configured correctly")
        print_info("Please check the errors above and:")
        print_info("1. Verify your API keys in .env file")
        print_info("2. Enable required APIs in Google Cloud Console")
        print_info("3. Make sure billing is set up (for Maps APIs)")
        return 1


if __name__ == '__main__':
    sys.exit(main())
