# Web UI Quick Start Guide

## 🚀 Running the Web Interface

### 1. Install FastAPI and Uvicorn (if not already installed)
```bash
pip install fastapi uvicorn python-multipart
```

Or update all dependencies:
```bash
pip install -r requirements.txt
```

### 2. Start the Web Server
```bash
python app.py
```

Or using uvicorn directly:
```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### 3. Open Your Browser
Navigate to: **http://localhost:8000**

**API Documentation:** http://localhost:8000/docs (Swagger UI)

## 💬 Using the Chat Interface

### Example Questions You Can Ask:

**Itinerary Planning:**
- "Plan a 2-hour history tour"
- "2 hours mural trip for me"
- "Create a 3-hour outdoor adventure"

**Nearby Search:**
- "Where can I visit nearby Fort Cornwallis?"
- "Find Malay restaurants near George Town"
- "Chinese food near Penang Street Art"
- "Cafes nearby Penang Hill"

**Combined Queries:**
- "Plan a heritage tour and find restaurants nearby"
- "Visit museums and show me cafes along the way"

## 🎨 Features

- **Real-time Chat**: Instant responses from the AI agent
- **Beautiful UI**: Modern gradient design with smooth animations
- **Mobile Responsive**: Works on all devices
- **Loading States**: Visual feedback while AI is thinking
- **Error Handling**: Clear error messages if something goes wrong
- **Auto-scroll**: Automatically scrolls to latest messages
- **Markdown Support**: Formats bold text, lists, and line breaks

## ⌨️ Keyboard Shortcuts

- **Enter**: Send message
- **Shift + Enter**: New line in message

## 🔧 Troubleshooting

**Server won't start:**
- Make sure FastAPI and Uvicorn are installed: `pip install fastapi uvicorn`
- Check if port 8000 is already in use

**"API key not configured" warning:**
- Make sure you've set `GOOGLE_API_KEY` in your `.env` file
- Restart the server after adding the key

**No response from agent:**
- Check the terminal for error messages
- Verify your API keys are correct
- Make sure you have internet connection

**Want to use a different port?**
```bash
uvicorn app:app --host 0.0.0.0 --port 5000
```

## 📱 Screenshots

The UI features:
- Purple gradient header with logo
- Clean white chat area
- User messages on the right (purple)
- AI messages on the left (gray)
- Smooth animations and transitions
- Loading dots while AI is thinking

## 🛑 Stopping the Server

Press **Ctrl+C** in the terminal to stop the server.
