# PenangLens POC: AI Agent Itinerary Planner

## 1. Objective
To demonstrate that an autonomous AI agent can accept a natural language travel request (e.g., *"Plan a 3-hour heritage walk starting at 9 AM"*), effectively use external tools to gather logical data, and generate a valid itinerary without "hallucinating" impossible schedules.

[cite_start]**Reference:** Maps to System Objective 3 [cite: 275] [cite_start]and the "AI-Powered Planning & Discovery" module[cite: 317].

---

## 2. Technical Prerequisites & API Requirements

[cite_start]Based on your system architecture [cite: 1327-1328], the following APIs and libraries are required for this POC.

### Required APIs
| API Name | Purpose in POC | Cost / Tier |
| :--- | :--- | :--- |
| **Google Gemini API** | [cite_start]Acts as the "Reasoning Node"[cite: 682]. It analyzes the user request and decides which tools to call. | Free tier available (Gemini Flash) |
| **Google Maps Distance Matrix API** | [cite_start]Calculates realistic travel times between two landmarks[cite: 686]. | Free tier (monthly credit) |
| **OpenWeatherMap API** | (Optional) [cite_start]Checks weather conditions to validate if an outdoor itinerary is feasible[cite: 688]. | Free tier available |

### Required Python Libraries
* [cite_start]`langgraph`: To build the cyclic state machine (The "Cognitive Loop")[cite: 1327].
* `langchain` & `langchain-google-genai`: To interface with the Gemini LLM.
* `python-dotenv`: To manage API keys securely.

---

## 3. POC Architecture

[cite_start]Instead of the full microservices architecture, this POC will run as a local Python script consisting of three main nodes, mirroring Figure 3.4 in your report[cite: 693]:

1.  **Agent Node:** The Gemini LLM that receives the state and decides the next step.
2.  **Tools Node:** Executes functions (Search, Distance Calculation).
3.  **Validation Node:** Checks if the itinerary meets constraints (e.g., "Is total time < 3 hours?").

---

## 4. Step-by-Step Implementation Plan

### Phase 1: Data Preparation (The "Vector DB" Mock)
[cite_start]Since setting up Azure AI Search is complex for a quick POC, you will simulate the "Vector Search" [cite: 687] using a local JSON file containing verified Penang landmarks.

* **Task:** Create `penang_landmarks.json`.
* **Content:**
    ```json
    [
      {
        "id": "L01",
        "name": "Fort Cornwallis",
        "tags": ["history", "heritage"],
        "location": "Jalan Tun Syed Sheh Barakbah",
        "avg_duration_min": 60,
        "opening_hours": "08:00-23:00"
      },
      {
        "id": "L02",
        "name": "Penang Street Art",
        "tags": ["art", "outdoor"],
        "location": "Armenian Street",
        "avg_duration_min": 45,
        "opening_hours": "24 hours"
      }
    ]
    ```

### Phase 2: Tool Development
Develop the Python functions that the AI will "call" as tools.

* **Tool A: `search_places(category: str)`**
    * *Logic:* Filters the `penang_landmarks.json` list by tag. Returns a list of matching places.
* **Tool B: `get_travel_time(origin: str, destination: str)`**
    * *Logic:* Calls the **Google Maps Distance Matrix API**.
    * *Input:* "Fort Cornwallis", "Armenian Street".
    * *Output:* "12 mins" (extracted from the JSON response).

### Phase 3: The Agent Construction (LangGraph)
This is the core logic implementation[cite: 694].

1.  **Define State:** Create a class `AgentState` that holds:
    * `messages`: The conversation history.
    * `itinerary`: The list of selected stops.
    * `total_duration`: Current accumulated time.
2.  **Initialize LLM:** Configure `ChatGoogleGenerativeAI` (Gemini Pro/Flash).
3.  **Bind Tools:** Use `.bind_tools()` to attach your Python functions to the LLM.
4.  **Build Graph:**
    * Add Node `agent`: Calls LLM.
    * Add Node `action`: Executes tools.
    * Add Edge: `agent` -> `action` (if tool call detected).
    * Add Edge: `action` -> `agent` (returns data to LLM).

### Phase 4: Validation Logic (Self-Correction)
[cite_start]Implement the "Validation Node" logic described in Section 3.1.1.3[cite: 713].

* **Logic:** Before showing the final answer, the code checks the generated schedule.
* **Constraint Check:** If `total_duration > user_requested_duration`, the system sends a hidden system message back to the LLM: *"Error: Plan exceeds time limit. Remove one stop and try again."*
* **Goal:** Observe the AI rewriting its own plan without user intervention.

---

## 5. Testing & Success Criteria

To verify the POC works, run these specific scenarios:

| Test Case | Input Prompt | Expected Outcome |
| :--- | :--- | :--- |
| **Basic Planning** | "Plan a 2-hour history tour." | Agent selects 1-2 "history" sites from JSON + calculates travel time. Total time is under 2 hours. |
| **Logic & Math** | "Go to Fort Cornwallis then Street Art. How long will it take?" | Agent calls `get_travel_time` API and sums up visit durations + travel time correctly. |
| **Constraint Handling** | "Plan a visit to Fort Cornwallis at 3 AM." | Agent checks `opening_hours` in JSON, sees it is closed, and replies: *"Fort Cornwallis is closed at 3 AM."* [cite: 714] |

## 6. Next Steps after POC

1.  **Migrate Data:** Replace the local JSON with **Azure AI Search** for the final system[cite: 1311].
2.  **Deploy:** Wrap the Python script in a **FastAPI** container for the Agent Microservice[cite: 1304].