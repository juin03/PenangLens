# PenangLens AI Agent - Itinerary Planner POC

An autonomous AI agent that generates travel itineraries for Penang, Malaysia using natural language requests. Built with LangGraph and Google Gemini.

## 🎯 Features

- **Natural Language Planning**: Request itineraries in plain English
- **Smart Tool Usage**: Automatically searches places and calculates travel times
- **Google Places Integration**: Find nearby restaurants, cafes, and attractions in real-time
- **Cuisine Filtering**: Search for specific food types (Malay, Chinese, Indian, seafood, etc.)
- **Constraint Validation**: Checks time limits and opening hours
- **Self-Correction**: Adjusts plans when constraints are violated
- **Real-World Data**: Integrates with Google Maps and Places APIs for accurate information

## 📋 Prerequisites

- Python 3.10 or higher
- Google Gemini API key (required)
- Google Maps Distance Matrix API key (optional, uses mock data if not provided)
- OpenWeatherMap API key (optional)

## 🚀 Quick Start

### 1. Clone or Navigate to the Project

```bash
cd c:\Users\User\Desktop\USM\Y4\FYP\PenangLens\Agent
```

### 2. Install Dependencies

Using pip:
```bash
pip install -r requirements.txt
```

Or using uv (recommended):
```bash
uv pip install -r requirements.txt
```

### 3. Configure API Keys

Copy the example environment file:
```bash
copy .env.example .env
```

Edit `.env` and add your API keys:
```env
GOOGLE_API_KEY=your_actual_google_gemini_api_key
GOOGLE_MAPS_API_KEY=your_actual_google_maps_api_key
OPENWEATHER_API_KEY=your_actual_openweather_api_key
```

**Get API Keys:**
- Google Gemini: https://makersuite.google.com/app/apikey
- Google Maps: https://console.cloud.google.com/
- OpenWeatherMap: https://openweathermap.org/api

### 4. Run the Agent

**Web UI (Recommended):**
```bash
python app.py
```
Then open: http://localhost:8000

**Interactive CLI Mode:**
```bash
python main.py
```

**Run Test Scenarios:**
```bash
python main.py --test
```

**Direct Request:**
```bash
python main.py "Plan a 3-hour heritage walk starting at 9 AM"
```

## 📝 Example Requests

**Curated Landmarks (from JSON database):**
- `"Plan a 2-hour history tour in George Town"`
- `"Create a 4-hour outdoor adventure itinerary"`
- `"Visit Kek Lok Si Temple at 7 AM"` (tests opening hours validation)

**Nearby Search (Google Places API):**
- `"Where can I visit nearby Fort Cornwallis?"`
- `"Any restaurants near Penang Street Art?"`
- `"Find Malay food near George Town"`
- `"Chinese restaurants near Gurney Drive"`
- `"Cafes nearby Penang Hill"`
- `"Museums near Fort Cornwallis"`

**Combined Queries:**
- `"Plan a history tour and then find Malay restaurants nearby"`
- `"Visit heritage sites and show me cafes along the way"`

## 🧪 Test Scenarios

The POC includes three test scenarios from the guide:

1. **Basic Planning**: 2-hour history tour
2. **Logic & Math**: Calculate total time for specific route
3. **Constraint Handling**: Validate opening hours

Run all tests with:
```bash
python main.py --test
```

## 🏗️ Architecture

```
┌─────────────────┐
│  User Request   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Agent Node     │ ◄─────┐
│  (Gemini LLM)   │       │
└────────┬────────┘       │
         │                │
         ▼                │
┌─────────────────┐       │
│  Tools Node     │───────┘
│  - Search       │
│  - Travel Time  │
│  - Weather      │
│  - Hours Check  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Validation Node │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Final Answer   │
└─────────────────┘
```

## 📁 Project Structure

```
Agent/
├── agent.py                 # Core LangGraph agent
├── tools.py                 # Tool functions (search, travel time, etc.)
├── validator.py             # Validation logic
├── main.py                  # Entry point & CLI
├── penang_landmarks.json    # Mock vector database
├── requirements.txt         # Python dependencies
├── pyproject.toml          # Modern Python config
├── .env.example            # Environment template
├── .env                    # Your API keys (not in git)
└── README.md               # This file
```

## 🔧 How It Works

1. **User Request**: Natural language travel request
2. **Agent Reasoning**: Gemini LLM analyzes request and decides which tools to call
3. **Tool Execution**: 
   - `search_places`: Filters landmarks by category from JSON
   - `get_travel_time`: Calls Google Maps API for realistic travel times
   - `check_opening_hours`: Validates if locations are open
4. **Validation**: Checks time constraints and opening hours
5. **Self-Correction**: If validation fails, agent revises the plan
6. **Final Itinerary**: Returns valid, time-efficient itinerary

## 🎓 Learning Outcomes

This POC demonstrates:
- ✅ Autonomous tool usage without hallucination
- ✅ Real-world API integration (Google Maps)
- ✅ Constraint validation and self-correction
- ✅ LangGraph state machine implementation
- ✅ Gemini LLM reasoning capabilities

## 🚀 Next Steps

After validating this POC:

1. **Migrate Data**: Replace JSON with Azure AI Search vector database
2. **Deploy**: Wrap in FastAPI container for microservice architecture
3. **Enhance**: Add more tools (restaurant search, booking, etc.)
4. **Scale**: Implement full system architecture from project scope

## 📄 License

Part of the PenangLens FYP project.

## 🤝 Support

For issues or questions, refer to the project documentation or contact the development team.
