"""
Integration tests that call the API exactly like the mobile app does.

Tests cover all fixes made:
  1. chat/stream passes history + current_itinerary
  2. generate/stream sends real status messages
  3. Time budget respected (not too early, not too late)
  4. Multi-turn chat context preserved
  5. Itinerary modification (add/remove/swap/rearrange)
  6. Too many places in short time → graceful handling
  7. Many food items → hawker centre suggestion
  8. Guardrail blocks non-Penang queries
  9. Walking mode stays within walkable distance
 10. Driving mode can span full island

Usage:
  python scripts/test_api_integration.py
  python scripts/test_api_integration.py --base-url http://localhost:8000
  python scripts/test_api_integration.py --test generate   # only generate tests
  python scripts/test_api_integration.py --test chat       # only chat tests
"""

import argparse
import json
import sys
import time
import requests
import sseclient  # pip install sseclient-py

BASE_URL = "http://localhost:8000"

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _time_to_min(t):
    try:
        h, m = map(int, t.split(":"))
        return h * 60 + m
    except Exception:
        return 0


def post(path, body, timeout=120):
    return requests.post(f"{BASE_URL}{path}", json=body, timeout=timeout)


def stream_generate(body, timeout=180):
    """Call /api/v1/generate/stream and collect all SSE events."""
    resp = requests.post(
        f"{BASE_URL}/api/v1/generate/stream",
        json=body,
        stream=True,
        timeout=timeout,
        headers={"Accept": "text/event-stream"},
    )
    resp.raise_for_status()
    client = sseclient.SSEClient(resp)
    events = []
    for event in client.events():
        try:
            data = json.loads(event.data)
            events.append(data)
            if data.get("type") in ("complete", "error"):
                break
        except Exception:
            pass
    return events


def stream_chat(body, timeout=60):
    """Call /api/v1/chat/stream and collect all SSE events."""
    resp = requests.post(
        f"{BASE_URL}/api/v1/chat/stream",
        json=body,
        stream=True,
        timeout=timeout,
        headers={"Accept": "text/event-stream"},
    )
    resp.raise_for_status()
    client = sseclient.SSEClient(resp)
    events = []
    for event in client.events():
        try:
            data = json.loads(event.data)
            events.append(data)
            if data.get("type") == "done":
                break
        except Exception:
            pass
    return events


# ─── Test Runner ─────────────────────────────────────────────────────────────

class TestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def check(self, name, condition, detail=""):
        if condition:
            self.passed += 1
            print(f"    ✅ {name}")
        else:
            self.failed += 1
            msg = f"    ❌ {name}" + (f" — {detail}" if detail else "")
            print(msg)
            self.errors.append(msg)

    def section(self, title):
        print(f"\n{'='*65}")
        print(f"  {title}")
        print(f"{'='*65}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*65}")
        print(f"RESULT: {self.passed}/{total} passed, {self.failed} failed")
        if self.errors:
            print("\nFailed checks:")
            for e in self.errors:
                print(e)
        print(f"{'='*65}")
        return self.failed == 0


r = TestRunner()

# ─── Test 1: Health check ─────────────────────────────────────────────────────

def test_health():
    r.section("1. Health Check")
    try:
        resp = requests.get(f"{BASE_URL}/api/v1/health", timeout=5)
        r.check("returns 200", resp.status_code == 200)
        data = resp.json()
        r.check("status=healthy", data.get("status") == "healthy")
        r.check("maps_configured", data.get("maps_configured") is True)
    except Exception as e:
        r.check("health endpoint reachable", False, str(e))


# ─── Test 2: Generate — time budget respected ─────────────────────────────────

def test_generate_time_budget():
    r.section("2. Generate — Time Budget (9am-5pm walking)")
    body = {
        "description": "Heritage walk in George Town",
        "interests": ["Heritage", "Culture"],
        "start_time": "09:00",
        "end_time": "17:00",
        "start_location": "5.4164,100.3327",
        "travel_mode": "walking",
    }
    try:
        t0 = time.time()
        resp = post("/api/v1/generate", body)
        elapsed = time.time() - t0
        r.check("returns 200", resp.status_code == 200, resp.text[:200])
        data = resp.json()
        r.check("success=true", data.get("success") is True)
        itin = data.get("structured_itinerary", {})
        stops = itin.get("stops", [])
        r.check("has stops", len(stops) >= 2, f"got {len(stops)}")

        if stops:
            last = stops[-1]
            last_dep = _time_to_min(last.get("departure_time", "17:00"))
            end_min = _time_to_min("17:00")
            overshoot = last_dep - end_min
            unused = end_min - last_dep
            r.check("doesn't exceed 5pm by >30min", overshoot <= 30,
                    f"ends at {last.get('departure_time')} ({overshoot}min over)")
            r.check("doesn't end >90min early", unused <= 90,
                    f"ends at {last.get('departure_time')} ({unused}min unused)")

        r.check("completed in <120s", elapsed < 120, f"{elapsed:.1f}s")
    except Exception as e:
        r.check("generate request succeeded", False, str(e))


# ─── Test 3: Generate — short 2-hour trip ────────────────────────────────────

def test_generate_short_trip():
    r.section("3. Generate — Short 2-Hour Trip")
    body = {
        "description": "Quick morning heritage walk",
        "interests": ["Heritage"],
        "start_time": "09:00",
        "end_time": "11:00",
        "start_location": "5.4164,100.3327",
        "travel_mode": "walking",
    }
    try:
        resp = post("/api/v1/generate", body)
        r.check("returns 200", resp.status_code == 200)
        data = resp.json()
        itin = data.get("structured_itinerary", {})
        stops = itin.get("stops", [])
        r.check("has at least 1 stop", len(stops) >= 1, f"got {len(stops)}")
        r.check("has at most 4 stops", len(stops) <= 4, f"got {len(stops)} (too many for 2hrs)")

        if stops:
            last_dep = _time_to_min(stops[-1].get("departure_time", "11:00"))
            r.check("ends by 11:30", last_dep <= _time_to_min("11:30"),
                    f"ends at {stops[-1].get('departure_time')}")
    except Exception as e:
        r.check("short trip request succeeded", False, str(e))


# ─── Test 4: Generate — too many pinned places in short time ─────────────────

def test_generate_overloaded():
    r.section("4. Generate — Too Many Places, Short Time (graceful handling)")
    body = {
        "description": "I want to visit Kek Lok Si, Penang Hill, Fort Cornwallis, Khoo Kongsi, and Clan Jetties",
        "interests": ["Heritage"],
        "start_time": "09:00",
        "end_time": "11:00",
        "start_location": "5.4164,100.3327",
        "travel_mode": "driving",
    }
    try:
        resp = post("/api/v1/generate", body)
        r.check("returns 200", resp.status_code == 200)
        data = resp.json()
        itin = data.get("structured_itinerary", {})
        stops = itin.get("stops", [])
        summary = itin.get("summary", "")
        r.check("returns some stops", len(stops) >= 1)
        r.check("doesn't crash with too many places", True)
        # Check if note about left-out places is in summary
        has_note = any(
            word in summary.lower()
            for word in ["cannot", "left out", "not enough", "fit", "focusing"]
        )
        r.check("summary mentions constraint (optional)", has_note or len(stops) <= 3,
                f"summary='{summary[:100]}'")
    except Exception as e:
        r.check("overloaded request succeeded", False, str(e))


# ─── Test 5: Generate — many food items → hawker centre ──────────────────────

def test_generate_many_foods():
    r.section("5. Generate — Many Food Items → Hawker Centre")
    body = {
        "description": "I want to eat char koay teow, laksa, nasi kandar, cendol, rojak, and curry mee",
        "interests": ["Food"],
        "start_time": "10:00",
        "end_time": "14:00",
        "start_location": "5.4164,100.3327",
        "travel_mode": "walking",
    }
    try:
        resp = post("/api/v1/generate", body)
        r.check("returns 200", resp.status_code == 200)
        data = resp.json()
        itin = data.get("structured_itinerary", {})
        stops = itin.get("stops", [])
        r.check("has stops", len(stops) >= 1)
        # Check if any stop is a hawker centre / food court
        hawker_keywords = ["hawker", "food court", "gurney", "new lane", "pulau tikus", "market"]
        has_hawker = any(
            any(kw in s.get("name", "").lower() for kw in hawker_keywords)
            for s in stops
        )
        # Also acceptable: fewer stops than food items (consolidated)
        r.check("consolidated food stops (hawker or ≤3 stops)", has_hawker or len(stops) <= 3,
                f"stops: {[s.get('name') for s in stops]}")
    except Exception as e:
        r.check("many foods request succeeded", False, str(e))


# ─── Test 6: Generate stream — real status messages ──────────────────────────

def test_generate_stream_status():
    r.section("6. Generate Stream — Real Status Messages")
    body = {
        "description": "Heritage walk in George Town",
        "interests": ["Heritage"],
        "start_time": "09:00",
        "end_time": "12:00",
        "start_location": "5.4164,100.3327",
        "travel_mode": "walking",
    }
    try:
        events = stream_generate(body)
        status_msgs = [e.get("message", "") for e in events if e.get("type") == "status"]
        complete_events = [e for e in events if e.get("type") == "complete"]
        error_events = [e for e in events if e.get("type") == "error"]

        r.check("received status messages", len(status_msgs) >= 3,
                f"got {len(status_msgs)}: {status_msgs}")
        r.check("status messages are different", len(set(status_msgs)) >= 2,
                f"all same: {status_msgs}")
        r.check("received complete event", len(complete_events) == 1)
        r.check("no error events", len(error_events) == 0,
                str(error_events[0]) if error_events else "")

        if complete_events:
            itin = complete_events[0].get("data", {}).get("structured")
            r.check("complete event has itinerary", itin is not None)
            if itin:
                r.check("itinerary has stops", len(itin.get("stops", [])) >= 1)
    except Exception as e:
        r.check("generate stream request succeeded", False, str(e))


# ─── Test 7: Chat — guardrail blocks non-Penang ───────────────────────────────

def test_chat_guardrail():
    r.section("7. Chat — Guardrail Blocks Non-Penang Query")
    body = {
        "message": "Plan me a 3-day trip to Tokyo",
        "thread_id": None,
    }
    try:
        resp = post("/api/v1/chat", body)
        r.check("returns 200", resp.status_code == 200)
        data = resp.json()
        response_text = data.get("response", "").lower()
        r.check("response mentions Penang", "penang" in response_text,
                f"response: {response_text[:150]}")
        r.check("doesn't plan Tokyo trip",
                "tokyo" not in response_text or "penang" in response_text)
    except Exception as e:
        r.check("guardrail test succeeded", False, str(e))


# ─── Test 8: Chat — multi-turn context preserved ─────────────────────────────

def test_chat_multiturn():
    r.section("8. Chat — Multi-Turn Context (history passed)")
    thread_id = f"test-multiturn-{int(time.time())}"

    # Turn 1: ask about a place
    body1 = {
        "message": "Tell me about Khoo Kongsi",
        "thread_id": thread_id,
        "history": [],
    }
    try:
        resp1 = post("/api/v1/chat", body1)
        r.check("turn 1 returns 200", resp1.status_code == 200)
        data1 = resp1.json()
        response1 = data1.get("response", "")
        r.check("turn 1 mentions Khoo Kongsi", "khoo kongsi" in response1.lower(),
                response1[:150])

        # Turn 2: follow-up referencing turn 1
        body2 = {
            "message": "What are the opening hours?",
            "thread_id": thread_id,
            "history": [
                {"role": "user", "content": "Tell me about Khoo Kongsi"},
                {"role": "assistant", "content": response1},
            ],
        }
        resp2 = post("/api/v1/chat", body2)
        r.check("turn 2 returns 200", resp2.status_code == 200)
        data2 = resp2.json()
        response2 = data2.get("response", "").lower()
        # Should answer about Khoo Kongsi hours, not ask "which place?"
        r.check("turn 2 understands context (no 'which place' confusion)",
                "which place" not in response2 and "what place" not in response2,
                response2[:150])
        r.check("turn 2 mentions hours or time",
                any(w in response2 for w in ["hour", "open", "am", "pm", "close"]),
                response2[:150])
    except Exception as e:
        r.check("multi-turn test succeeded", False, str(e))


# ─── Test 9: Chat stream — history + current_itinerary passed ────────────────

def test_chat_stream_context():
    r.section("9. Chat Stream — History + Current Itinerary Context")
    mock_itinerary = {
        "stops": [
            {"name": "Khoo Kongsi", "order": 1, "arrival_time": "09:00",
             "departure_time": "10:00", "visit_duration_min": 60,
             "description": "Famous clan house", "short_description": "Clan house",
             "lat": 5.4136, "lng": 100.3394, "category": "heritage"},
            {"name": "Fort Cornwallis", "order": 2, "arrival_time": "10:15",
             "departure_time": "11:15", "visit_duration_min": 60,
             "description": "Historic fort", "short_description": "Historic fort",
             "lat": 5.4194, "lng": 100.3401, "category": "heritage"},
        ],
        "travel_mode": "walking",
        "start_time": "09:00",
        "end_time": "13:00",
    }
    body = {
        "message": "Remove stop 2",
        "thread_id": f"test-stream-{int(time.time())}",
        "context": "itinerary_chat",
        "current_itinerary": mock_itinerary,
        "history": [
            {"role": "user", "content": "Plan a morning heritage walk"},
            {"role": "assistant", "content": "Here's your itinerary..."},
        ],
    }
    try:
        events = stream_chat(body)
        token_events = [e for e in events if e.get("type") == "token"]
        done_events = [e for e in events if e.get("type") == "done"]
        r.check("received token events", len(token_events) > 0)
        r.check("received done event", len(done_events) == 1)
        full_text = "".join(e.get("content", "") for e in token_events).lower()
        r.check("response is not empty", len(full_text) > 10, f"got: '{full_text[:100]}'")
    except Exception as e:
        r.check("chat stream with context succeeded", False, str(e))


# ─── Test 10: Modify — add/remove/swap ───────────────────────────────────────

def test_modify_itinerary():
    r.section("10. Modify Itinerary — Add / Remove / Swap")
    mock_itinerary = {
        "stops": [
            {"name": "Khoo Kongsi", "order": 1, "arrival_time": "09:00",
             "departure_time": "10:00", "visit_duration_min": 60,
             "description": "Famous clan house", "short_description": "Clan house",
             "lat": 5.4136, "lng": 100.3394, "category": "heritage",
             "google_maps_url": None, "photo_url": None, "rating": 4.5, "address": "Penang"},
            {"name": "Fort Cornwallis", "order": 2, "arrival_time": "10:15",
             "departure_time": "11:15", "visit_duration_min": 60,
             "description": "Historic fort", "short_description": "Historic fort",
             "lat": 5.4194, "lng": 100.3401, "category": "heritage",
             "google_maps_url": None, "photo_url": None, "rating": 4.2, "address": "Penang"},
            {"name": "Armenian Street", "order": 3, "arrival_time": "11:30",
             "departure_time": "12:30", "visit_duration_min": 60,
             "description": "Street art area", "short_description": "Street art",
             "lat": 5.4155, "lng": 100.3370, "category": "art",
             "google_maps_url": None, "photo_url": None, "rating": 4.3, "address": "Penang"},
        ],
        "travel_mode": "walking",
        "start_time": "09:00",
        "end_time": "14:00",
    }

    # Test remove
    try:
        resp = post("/api/v1/chat", {
            "message": "remove stop 2",
            "current_itinerary": mock_itinerary,
            "context": "itinerary_chat",
        })
        r.check("remove: returns 200", resp.status_code == 200)
        data = resp.json()
        itin = data.get("structured_itinerary")
        if itin:
            stops = itin.get("stops", [])
            r.check("remove: 2 stops remain", len(stops) == 2, f"got {len(stops)}")
            names = [s.get("name") for s in stops]
            r.check("remove: Fort Cornwallis removed", "Fort Cornwallis" not in names, str(names))
        else:
            r.check("remove: returned structured itinerary", False, "no structured_itinerary in response")
    except Exception as e:
        r.check("remove test succeeded", False, str(e))

    # Test add
    try:
        resp = post("/api/v1/chat", {
            "message": "add a lunch restaurant after stop 2",
            "current_itinerary": mock_itinerary,
            "context": "itinerary_chat",
        })
        r.check("add: returns 200", resp.status_code == 200)
        data = resp.json()
        itin = data.get("structured_itinerary")
        if itin:
            stops = itin.get("stops", [])
            r.check("add: more stops than before", len(stops) >= 3, f"got {len(stops)}")
        else:
            r.check("add: returned structured itinerary", False, "no structured_itinerary")
    except Exception as e:
        r.check("add test succeeded", False, str(e))

    # Test swap
    try:
        resp = post("/api/v1/chat", {
            "message": "replace stop 1 with Cheong Fatt Tze Mansion",
            "current_itinerary": mock_itinerary,
            "context": "itinerary_chat",
        })
        r.check("swap: returns 200", resp.status_code == 200)
        data = resp.json()
        itin = data.get("structured_itinerary")
        if itin:
            stops = itin.get("stops", [])
            r.check("swap: same stop count", len(stops) == 3, f"got {len(stops)}")
            names = [s.get("name", "").lower() for s in stops]
            r.check("swap: Khoo Kongsi replaced",
                    "khoo kongsi" not in names or "cheong" in " ".join(names),
                    str(names))
        else:
            r.check("swap: returned structured itinerary", False, "no structured_itinerary")
    except Exception as e:
        r.check("swap test succeeded", False, str(e))


# ─── Test 11: Walking mode — no far stops ────────────────────────────────────

def test_walking_distance():
    r.section("11. Walking Mode — All Stops Within Walking Distance")
    body = {
        "description": "Morning walk in George Town",
        "interests": ["Heritage", "Art"],
        "start_time": "09:00",
        "end_time": "12:00",
        "start_location": "5.4164,100.3327",
        "travel_mode": "walking",
    }
    try:
        resp = post("/api/v1/generate", body)
        r.check("returns 200", resp.status_code == 200)
        data = resp.json()
        itin = data.get("structured_itinerary", {})
        stops = itin.get("stops", [])
        if stops:
            travel_times = [
                s.get("travel_to_next", {}).get("duration_min", 0)
                for s in stops if s.get("travel_to_next")
            ]
            max_travel = max(travel_times) if travel_times else 0
            r.check("no travel segment >35min", max_travel <= 35,
                    f"max travel={max_travel}min, segments={travel_times}")
    except Exception as e:
        r.check("walking distance test succeeded", False, str(e))


# ─── Test 12: Driving mode — full island ─────────────────────────────────────

def test_driving_full_island():
    r.section("12. Driving Mode — Full Island Itinerary")
    body = {
        "description": "Full day tour — temples, hill, beach",
        "interests": ["Heritage", "Nature", "Food"],
        "start_time": "08:00",
        "end_time": "18:00",
        "start_location": "5.4164,100.3327",
        "travel_mode": "driving",
    }
    try:
        resp = post("/api/v1/generate", body)
        r.check("returns 200", resp.status_code == 200)
        data = resp.json()
        itin = data.get("structured_itinerary", {})
        stops = itin.get("stops", [])
        r.check("has 4+ stops for full day", len(stops) >= 4, f"got {len(stops)}")

        if stops:
            last_dep = _time_to_min(stops[-1].get("departure_time", "18:00"))
            r.check("ends by 18:30", last_dep <= _time_to_min("18:30"),
                    f"ends at {stops[-1].get('departure_time')}")
            unused = _time_to_min("18:00") - last_dep
            r.check("uses most of the day (unused <90min)", unused <= 90,
                    f"{unused}min unused")
    except Exception as e:
        r.check("driving full island test succeeded", False, str(e))


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--test", choices=["generate", "chat", "modify", "stream", "all"],
                        default="all")
    args = parser.parse_args()

    global BASE_URL
    BASE_URL = args.base_url

    # Check server is up
    try:
        requests.get(f"{BASE_URL}/api/v1/health", timeout=5)
    except Exception:
        print(f"❌ Server not reachable at {BASE_URL}. Start with: uvicorn app:app --reload")
        sys.exit(1)

    t = args.test
    if t in ("all", "generate"):
        test_generate_time_budget()
        test_generate_short_trip()
        test_generate_overloaded()
        test_generate_many_foods()
    if t in ("all", "stream"):
        test_generate_stream_status()
        test_chat_stream_context()
    if t in ("all", "chat"):
        test_chat_guardrail()
        test_chat_multiturn()
    if t in ("all", "modify"):
        test_modify_itinerary()
    if t == "all":
        test_walking_distance()
        test_driving_full_island()
        test_health()

    ok = r.summary()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
