# Quick Setup Guide

## Step 1: Install Dependencies

Open PowerShell in this directory and run:

```powershell
# Using pip
pip install -r requirements.txt

# OR using uv (if you have it)
uv pip install -r requirements.txt
```

## Step 2: Configure API Keys

Edit the `.env` file in this directory and replace the placeholder values with your actual API keys:

```env
GOOGLE_API_KEY=your_actual_api_key_here
GOOGLE_MAPS_API_KEY=your_actual_api_key_here  # Optional
OPENWEATHER_API_KEY=your_actual_api_key_here  # Optional
```

**Where to get API keys:**
- **Google Gemini** (Required): https://makersuite.google.com/app/apikey
- **Google Maps** (Optional): https://console.cloud.google.com/
- **OpenWeatherMap** (Optional): https://openweathermap.org/api

> **Note:** Only the Google Gemini API key is required. The agent will use mock data for Maps and Weather if those keys are not configured.

## Step 3: Run the Agent

### Interactive Mode
```powershell
python main.py
```

### Run Test Scenarios
```powershell
python main.py --test
```

### Direct Request
```powershell
python main.py "Plan a 2-hour history tour"
```

## Troubleshooting

**Error: "GOOGLE_API_KEY not configured"**
- Make sure you've edited the `.env` file with your actual API key
- The key should NOT have quotes around it
- Make sure the `.env` file is in the same directory as `main.py`

**Import errors**
- Make sure you've installed all dependencies: `pip install -r requirements.txt`
- Check that you're using Python 3.10 or higher: `python --version`

**API errors**
- Verify your API keys are valid and active
- Check that you have API quota remaining
- For Google Maps, ensure the Distance Matrix API is enabled in your Google Cloud Console

## Next Steps

Once you've verified the POC works:
1. Review the test scenarios output
2. Try custom requests in interactive mode
3. Check the README.md for more details on architecture and next steps
