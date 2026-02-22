# Google Places API Integration Summary

## What Was Added

### New Capabilities

The agent can now answer questions like:
- ✅ **"Where can I visit nearby Fort Cornwallis?"**
- ✅ **"Any restaurants near Penang Street Art?"**
- ✅ **"Find Malay food near George Town"**
- ✅ **"Chinese restaurants near Gurney Drive"**
- ✅ **"Cafes nearby Penang Hill"**

### Architecture: Hybrid Approach

```
User Query
    ↓
AI Agent Decides
    ↓
┌───────────┴───────────┐
↓                       ↓
Vector DB (JSON)    Google Places API
├─────────────┤    ├──────────────────┤
│ 10 curated  │    │ Real-time search │
│ landmarks   │    │ Restaurants      │
│ Heritage    │    │ Ratings/reviews  │
│ sites       │    │ Current hours    │
└─────────────┘    └──────────────────┘
```

**Vector DB (JSON)** - For curated tourist attractions:
- Fort Cornwallis, Kek Lok Si Temple, Penang Hill, etc.
- Pre-verified information
- Fast, no API calls needed

**Google Places API** - For real-time nearby search:
- Restaurants, cafes, museums, etc.
- Live ratings and reviews
- Current opening status
- Cuisine filtering

### New Tools Added

#### 1. `search_nearby_places(location, place_type, radius, keyword)`
General nearby search for ANY type of place.

**Example:**
```python
search_nearby_places(
    location="Fort Cornwallis",
    place_type="cafe",
    radius=2000,  # 2km
    keyword=""
)
```

**Returns:**
- Top 5 places with ratings
- Address and distance
- Open/closed status

#### 2. `search_restaurants(location, cuisine, radius)`
Specialized restaurant search with cuisine filtering.

**Example:**
```python
search_restaurants(
    location="George Town",
    cuisine="Malay",
    radius=3000  # 3km
)
```

**Returns:**
- Restaurants matching cuisine type
- Ratings and review counts
- Current status (open/closed)

#### 3. `get_place_details(place_name, location)`
Get detailed information about a specific place.

**Example:**
```python
get_place_details(
    place_name="Nasi Kandar Line Clear",
    location="Penang"
)
```

**Returns:**
- Full address
- Phone number
- Website
- Rating
- Opening hours

## Files Modified

1. **tools.py** (+186 lines)
   - Added Google Places API integration
   - Three new functions with geocoding and nearby search

2. **agent.py** (+30 lines)
   - Imported new tools
   - Added tool wrappers
   - Enhanced system prompt with usage guidelines

3. **.env.example**
   - Added GOOGLE_PLACES_API_KEY (optional)
   - Note: Can use same key as GOOGLE_MAPS_API_KEY

4. **README.md**
   - Updated features list
   - Added example queries for Places API
   - Documented new capabilities

## API Key Setup

**Important:** The same Google Maps API key works for both:
- Distance Matrix API (travel time)
- Places API (nearby search)

You only need ONE key from Google Cloud Console with both APIs enabled:
1. Distance Matrix API
2. Places API (New Search)

## How It Works

### Example Flow: "Find Malay food near Fort Cornwallis"

1. **User Request**: "Find Malay food near Fort Cornwallis"

2. **Agent Reasoning**: 
   - Detects "Malay food" → cuisine-specific
   - Detects "near Fort Cornwallis" → location-based
   - Chooses `search_restaurants_tool`

3. **Tool Execution**:
   ```
   search_restaurants(
       location="Fort Cornwallis, Penang",
       cuisine="Malay",
       radius=3000
   )
   ```

4. **API Calls**:
   - Geocode "Fort Cornwallis" → Get coordinates
   - Search nearby restaurants with keyword "Malay"
   - Return top 5 results

5. **Agent Response**:
   ```
   Found 5 Malay restaurants near Fort Cornwallis:
   
   1. Nasi Kandar Line Clear
      Rating: 4.2★ (1,234 reviews)
      Address: Penang Road, George Town
      Status: OPEN NOW
   
   2. Hameediyah Restaurant
      Rating: 4.3★ (2,100 reviews)
      Address: Campbell Street, George Town
      Status: OPEN NOW
   ...
   ```

## Testing

To test the new features, you can ask:

```bash
python main.py "Find Malay restaurants near Fort Cornwallis"
python main.py "Where can I get coffee near Penang Street Art?"
python main.py "Show me museums nearby George Town"
```

## Benefits

✅ **No more "only 10 landmarks" limitation**  
✅ **Real-time restaurant discovery**  
✅ **Cuisine-specific filtering**  
✅ **Live ratings and reviews**  
✅ **Current opening status**  
✅ **Works alongside curated landmarks**

## Next Steps

1. Add your Google Maps API key to `.env`
2. Enable Places API in Google Cloud Console
3. Test with nearby search queries
4. Optionally: Add more curated landmarks to JSON for better coverage
