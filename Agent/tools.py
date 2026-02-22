"""
Tool functions for the PenangLens AI Agent.

These tools are called by the LLM to gather real-world data:
- search_places: Filters landmarks from the local JSON database
- get_travel_time: Calculates travel time using Google Maps API
- check_weather: (Optional) Gets weather conditions
"""

import json
import os
import requests
from typing import List, Dict, Optional
from datetime import datetime


def load_landmarks() -> List[Dict]:
    """Load landmarks from the local JSON file."""
    landmarks_path = os.path.join(os.path.dirname(__file__), 'penang_landmarks.json')
    with open(landmarks_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def search_places(category: str) -> str:
    """
    Search for places in Penang by category/tag.
    
    Args:
        category: The category to filter by (e.g., 'history', 'heritage', 'food', 'outdoor')
    
    Returns:
        A formatted string listing matching places with their details
    """
    landmarks = load_landmarks()
    category_lower = category.lower()
    
    # Filter landmarks that have the category in their tags
    matching_places = [
        place for place in landmarks 
        if category_lower in [tag.lower() for tag in place['tags']]
    ]
    
    if not matching_places:
        return f"No places found for category '{category}'. Available categories: history, heritage, art, outdoor, culture, food, nature, beach, adventure, scenic."
    
    # Format the results
    result = f"Found {len(matching_places)} place(s) for category '{category}':\n\n"
    for place in matching_places:
        # Generate Google Maps search link
        from urllib.parse import quote
        search_query = quote(f"{place['name']}, {place['location']}, Penang, Malaysia")
        maps_link = f"https://www.google.com/maps/search/?api=1&query={search_query}"
        
        result += f"**{place['name']}** ({place['id']})\n"
        result += f"  Location: {place['location']}\n"
        
        # Add rich context if available
        if 'description' in place:
            result += f"  Description: {place['description']}\n"
        
        if 'significance' in place:
            result += f"  Why Visit: {place['significance']}\n"
        
        if 'must_see' in place and isinstance(place['must_see'], list):
            result += f"  Must See:\n"
            for item in place['must_see'][:5]:  # Limit to top 5
                result += f"    - {item}\n"
        
        if 'visitor_tips' in place:
            result += f"  Tips: {place['visitor_tips']}\n"
        
        result += f"  Tags: {', '.join(place['tags'])}\n"
        result += f"  Average visit duration: {place['avg_duration_min']} minutes\n"
        result += f"  Opening hours: {place['opening_hours']}\n"
        result += f"  📍 Google Maps: {maps_link}\n\n"
    
    return result


def get_travel_time(origin: str, destination: str) -> str:
    """
    Calculate travel time between two locations using Google Maps Distance Matrix API.
    
    Args:
        origin: Starting location (landmark name or address)
        destination: Destination location (landmark name or address)
    
    Returns:
        A string describing the travel time and distance
    """
    api_key = os.getenv('GOOGLE_MAPS_API_KEY')
    
    if not api_key or api_key == 'your_google_maps_api_key_here':
        # Fallback to mock data if API key not configured
        return f"Travel time from {origin} to {destination}: approximately 15 minutes (5 km) by car. [Note: Using mock data - configure GOOGLE_MAPS_API_KEY for real data]"
    
    # Prepare the API request
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        'origins': f"{origin}, Penang, Malaysia",
        'destinations': f"{destination}, Penang, Malaysia",
        'mode': 'driving',
        'key': api_key
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data['status'] == 'OK':
            element = data['rows'][0]['elements'][0]
            
            if element['status'] == 'OK':
                duration = element['duration']['text']
                distance = element['distance']['text']
                duration_minutes = element['duration']['value'] // 60
                
                return f"Travel time from {origin} to {destination}: {duration} ({distance}) by car. Approximately {duration_minutes} minutes."
            else:
                return f"Could not calculate route between {origin} and {destination}. Status: {element['status']}"
        else:
            return f"Google Maps API error: {data['status']}"
            
    except requests.exceptions.RequestException as e:
        return f"Error calling Google Maps API: {str(e)}"


def check_weather(location: str = "George Town, Penang") -> str:
    """
    Check current weather conditions (optional feature).
    
    Args:
        location: Location to check weather for
    
    Returns:
        A string describing current weather conditions
    """
    api_key = os.getenv('OPENWEATHER_API_KEY')
    
    if not api_key or api_key == 'your_openweather_api_key_here':
        return f"Weather check for {location}: Clear skies, 28°C. [Note: Using mock data - configure OPENWEATHER_API_KEY for real data]"
    
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        'q': location,
        'appid': api_key,
        'units': 'metric'
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        weather_desc = data['weather'][0]['description']
        temp = data['main']['temp']
        feels_like = data['main']['feels_like']
        
        return f"Weather in {location}: {weather_desc.capitalize()}, {temp}°C (feels like {feels_like}°C)"
        
    except requests.exceptions.RequestException as e:
        return f"Error checking weather: {str(e)}"


def get_landmark_by_name(name: str) -> Optional[Dict]:
    """
    Get landmark details by name.
    
    Args:
        name: Name of the landmark
    
    Returns:
        Landmark dictionary or None if not found
    """
    landmarks = load_landmarks()
    name_lower = name.lower()
    
    for landmark in landmarks:
        if landmark['name'].lower() == name_lower:
            return landmark
    
    return None


def check_opening_hours(landmark_name: str, time_str: str) -> str:
    """
    Check if a landmark is open at a specific time.
    
    Args:
        landmark_name: Name of the landmark
        time_str: Time in HH:MM format (24-hour)
    
    Returns:
        A string indicating if the landmark is open or closed
    """
    landmark = get_landmark_by_name(landmark_name)
    
    if not landmark:
        return f"Landmark '{landmark_name}' not found in database."
    
    opening_hours = landmark['opening_hours']
    
    # Handle 24-hour locations
    if opening_hours == "24 hours":
        return f"{landmark_name} is open 24 hours."
    
    # Parse opening hours (format: "HH:MM-HH:MM")
    try:
        open_time, close_time = opening_hours.split('-')
        open_hour, open_min = map(int, open_time.split(':'))
        close_hour, close_min = map(int, close_time.split(':'))
        
        # Parse requested time
        req_hour, req_min = map(int, time_str.split(':'))
        
        # Convert to minutes for comparison
        open_minutes = open_hour * 60 + open_min
        close_minutes = close_hour * 60 + close_min
        req_minutes = req_hour * 60 + req_min
        
        if open_minutes <= req_minutes <= close_minutes:
            return f"{landmark_name} is OPEN at {time_str}. Opening hours: {opening_hours}"
        else:
            return f"{landmark_name} is CLOSED at {time_str}. Opening hours: {opening_hours}"
            
    except Exception as e:
        return f"Error parsing opening hours for {landmark_name}: {str(e)}"


# ============================================================================
# Google Places API Integration
# ============================================================================

def search_nearby_places(
    location: str,
    place_type: str = "tourist_attraction",
    radius: int = 5000,
    keyword: str = ""
) -> str:
    """
    Search for places near a location using Google Places API.
    
    Args:
        location: Location name (e.g., "Fort Cornwallis, Penang")
        place_type: Type of place (restaurant, tourist_attraction, cafe, etc.)
        radius: Search radius in meters (default: 5000m = 5km)
        keyword: Additional keyword to filter results (e.g., "Malay", "seafood")
    
    Returns:
        A formatted string listing nearby places with ratings and details
    """
    api_key = os.getenv('GOOGLE_PLACES_API_KEY') or os.getenv('GOOGLE_MAPS_API_KEY')
    
    if not api_key or api_key == 'your_google_maps_api_key_here':
        return f"Nearby search for {place_type} near {location}: [Mock data - configure GOOGLE_PLACES_API_KEY or GOOGLE_MAPS_API_KEY for real data]\n\nExample results:\n- Nasi Kandar Line Clear (4.2★) - 500m away\n- Hameediyah Restaurant (4.3★) - 800m away"
    
    # First, geocode the location to get coordinates
    geocode_url = "https://maps.googleapis.com/maps/api/geocode/json"
    geocode_params = {
        'address': f"{location}, Penang, Malaysia",
        'key': api_key
    }
    
    try:
        # Get coordinates
        geocode_response = requests.get(geocode_url, params=geocode_params, timeout=10)
        geocode_response.raise_for_status()
        geocode_data = geocode_response.json()
        
        if geocode_data['status'] != 'OK' or not geocode_data['results']:
            return f"Could not find location: {location}"
        
        lat = geocode_data['results'][0]['geometry']['location']['lat']
        lng = geocode_data['results'][0]['geometry']['location']['lng']
        
        # Search nearby places
        places_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        places_params = {
            'location': f"{lat},{lng}",
            'radius': radius,
            'type': place_type,
            'key': api_key
        }
        
        if keyword:
            places_params['keyword'] = keyword
        
        places_response = requests.get(places_url, params=places_params, timeout=10)
        places_response.raise_for_status()
        places_data = places_response.json()
        
        if places_data['status'] != 'OK':
            return f"Google Places API error: {places_data['status']}"
        
        results = places_data.get('results', [])
        
        if not results:
            return f"No {place_type} found near {location} within {radius}m"
        
        # Format results (limit to top 20 to give agent more options)
        result_text = f"Found {len(results)} {place_type}(s) near {location}"
        if keyword:
            result_text += f" matching '{keyword}'"
        result_text += f" (within {radius}m):\n\n"
        
        for i, place in enumerate(results[:20], 1):
            name = place.get('name', 'Unknown')
            rating = place.get('rating', 'N/A')
            user_ratings = place.get('user_ratings_total', 0)
            vicinity = place.get('vicinity', 'Address not available')
            is_open = place.get('opening_hours', {}).get('open_now', None)
            place_id = place.get('place_id', '')
            
            # Generate Google Maps link using place_id
            maps_link = f"https://www.google.com/maps/place/?q=place_id:{place_id}" if place_id else ""
            
            result_text += f"{i}. **{name}**\n"
            result_text += f"   Rating: {rating}★ ({user_ratings} reviews)\n"
            result_text += f"   Address: {vicinity}\n"
            
            if is_open is not None:
                status = "OPEN NOW" if is_open else "CLOSED"
                result_text += f"   Status: {status}\n"
            
            # Add Google Maps link
            if maps_link:
                result_text += f"   📍 Google Maps: {maps_link}\n"
            
            result_text += "\n"
        
        return result_text
        
    except requests.exceptions.RequestException as e:
        return f"Error calling Google Places API: {str(e)}"


def search_restaurants(
    location: str = "George Town, Penang",
    cuisine: str = "",
    radius: int = 3000
) -> str:
    """
    Search for restaurants near a location, optionally filtered by cuisine type.
    
    Args:
        location: Location name or landmark
        cuisine: Cuisine type (e.g., "Malay", "Chinese", "Indian", "seafood")
        radius: Search radius in meters (default: 3000m = 3km)
    
    Returns:
        A formatted string listing restaurants with ratings and details
    """
    keyword = cuisine if cuisine else ""
    return search_nearby_places(
        location=location,
        place_type="restaurant",
        radius=radius,
        keyword=keyword
    )


def get_place_details(place_name: str, location: str = "Penang, Malaysia") -> str:
    """
    Get detailed information about a specific place.
    
    Args:
        place_name: Name of the place
        location: General location context
    
    Returns:
        Detailed information including address, hours, rating, phone, etc.
    """
    api_key = os.getenv('GOOGLE_PLACES_API_KEY') or os.getenv('GOOGLE_MAPS_API_KEY')
    
    if not api_key or api_key == 'your_google_maps_api_key_here':
        return f"Details for {place_name}: [Mock data - configure GOOGLE_PLACES_API_KEY for real data]"
    
    # Search for the place
    search_url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
    search_params = {
        'input': f"{place_name}, {location}",
        'inputtype': 'textquery',
        'fields': 'place_id,name,formatted_address,rating,opening_hours,formatted_phone_number,website',
        'key': api_key
    }
    
    try:
        response = requests.get(search_url, params=search_params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data['status'] != 'OK' or not data.get('candidates'):
            return f"Could not find place: {place_name}"
        
        place = data['candidates'][0]
        place_id = place.get('place_id', '')
        
        # Generate Google Maps link
        maps_link = f"https://www.google.com/maps/place/?q=place_id:{place_id}" if place_id else ""
        
        result = f"**{place.get('name', place_name)}**\n\n"
        result += f"Address: {place.get('formatted_address', 'N/A')}\n"
        result += f"Rating: {place.get('rating', 'N/A')}★\n"
        
        if 'formatted_phone_number' in place:
            result += f"Phone: {place['formatted_phone_number']}\n"
        
        if 'website' in place:
            result += f"Website: {place['website']}\n"
        
        if 'opening_hours' in place:
            is_open = place['opening_hours'].get('open_now', None)
            if is_open is not None:
                status = "OPEN NOW" if is_open else "CLOSED"
                result += f"Status: {status}\n"
        
        # Add Google Maps link
        if maps_link:
            result += f"\n📍 Google Maps: {maps_link}\n"
        
        return result
        
    except requests.exceptions.RequestException as e:
        return f"Error getting place details: {str(e)}"


def create_route_url(locations: list) -> str:
    """
    Create a Google Maps Directions URL showing a route through multiple locations.
    
    Args:
        locations: List of location names/addresses in order of visit
    
    Returns:
        A Google Maps URL showing the complete route
    
    Example:
        locations = ["Armenian Street, George Town", "Lebuh Chulia, George Town", "Love Lane, George Town"]
        Returns URL showing walking route through all 3 locations
    """
    from urllib.parse import quote
    
    if not locations or len(locations) < 2:
        return ""
    
    # For 2 locations, simple origin to destination
    if len(locations) == 2:
        origin = quote(f"{locations[0]}, Penang, Malaysia")
        destination = quote(f"{locations[1]}, Penang, Malaysia")
        return f"https://www.google.com/maps/dir/?api=1&origin={origin}&destination={destination}&travelmode=walking"
    
    # For 3+ locations, use origin, destination, and waypoints
    origin = quote(f"{locations[0]}, Penang, Malaysia")
    destination = quote(f"{locations[-1]}, Penang, Malaysia")
    
    # Middle locations become waypoints (separated by |)
    waypoints = []
    for loc in locations[1:-1]:
        waypoints.append(quote(f"{loc}, Penang, Malaysia"))
    
    waypoints_str = "|".join(waypoints)
    
    return f"https://www.google.com/maps/dir/?api=1&origin={origin}&destination={destination}&waypoints={waypoints_str}&travelmode=walking"

