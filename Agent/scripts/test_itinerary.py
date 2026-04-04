"""
Automated regression testing for itinerary generation + modification.

Usage:
  python scripts/test_itinerary.py              # run all tests
  python scripts/test_itinerary.py --scenario 3  # run specific scenario
  python scripts/test_itinerary.py --modify-only  # only test modifications
"""

import os, sys, json, time, argparse

# Load env
for line in open(os.path.join(os.path.dirname(__file__), '..', '.env')):
    line = line.strip()
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1)
        os.environ[k] = v

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("azure").setLevel(logging.WARNING)

from src.itinerary_workflow import run_itinerary_workflow, modify_itinerary
from src.models import ItineraryData

# ─── Test Scenarios ───────────────────────────────────────────────────────────

SCENARIOS = [
    {
        "name": "George Town Heritage Walk",
        "description": "I want to explore heritage sites in George Town on foot",
        "interests": ["Heritage", "Culture"],
        "start_time": "09:00", "end_time": "17:00",
        "start_location": "5.4164,100.3327",
        "travel_mode": "walking",
    },
    {
        "name": "Food Tour Driving",
        "description": "I want to try the best Penang food — laksa, char koay teow, nasi kandar",
        "interests": ["Food"],
        "start_time": "10:00", "end_time": "20:00",
        "start_location": "5.4164,100.3327",
        "travel_mode": "driving",
    },
    {
        "name": "Air Itam Nature + Food",
        "description": "Explore nature and food around Ayer Itam",
        "interests": ["Nature", "Food"],
        "start_time": "09:00", "end_time": "17:00",
        "start_location": "5.402693,100.2782329",
        "travel_mode": "driving",
    },
    {
        "name": "Short Morning Trip",
        "description": "Quick morning trip, just 3 hours",
        "interests": ["Heritage", "Food"],
        "start_time": "09:00", "end_time": "12:00",
        "start_location": "5.4164,100.3327",
        "travel_mode": "walking",
    },
    {
        "name": "Full Day Island Tour",
        "description": "Full day exploring Penang — temples, beaches, food",
        "interests": ["Heritage", "Nature", "Food"],
        "start_time": "08:00", "end_time": "20:00",
        "start_location": "5.4164,100.3327",
        "travel_mode": "driving",
    },
    {
        "name": "Batu Ferringhi Beach Day",
        "description": "Beach day at Batu Ferringhi with some food",
        "interests": ["Nature", "Food"],
        "start_time": "10:00", "end_time": "18:00",
        "start_location": "5.4734,100.2461",
        "travel_mode": "driving",
    },
    {
        "name": "Pinned Places",
        "description": "I must visit Kek Lok Si and Penang Hill, and try laksa",
        "interests": ["Heritage", "Nature", "Food"],
        "start_time": "09:00", "end_time": "17:00",
        "start_location": "5.3546,100.3016",
        "travel_mode": "driving",
    },
]

MODIFY_TESTS = [
    {"msg": "remove stop 3", "op": "remove"},
    {"msg": "add Tek Sen Restaurant after lunch", "op": "add"},
    {"msg": "swap stop 2 with Hameediyah Restaurant", "op": "swap"},
    {"msg": "move stop 4 to position 2", "op": "rearrange"},
]

# ─── Quality Checks ──────────────────────────────────────────────────────────

def _time_to_min(t):
    try:
        h, m = map(int, t.split(":"))
        return h * 60 + m
    except:
        return 0

def evaluate(result: ItineraryData, scenario: dict) -> dict:
    """Evaluate itinerary quality. Returns dict of checks with pass/fail."""
    checks = {}
    stops = result.stops
    start_min = _time_to_min(scenario["start_time"])
    end_min = _time_to_min(scenario["end_time"])
    budget = end_min - start_min

    # 1. Has stops
    checks["has_stops"] = len(stops) >= 2

    # 2. Reasonable stop count
    expected_min = max(2, budget // 150)
    expected_max = min(8, budget // 45)
    checks["stop_count_ok"] = expected_min <= len(stops) <= expected_max
    checks["_stop_count"] = f"{len(stops)} (expected {expected_min}-{expected_max})"

    # 3. Doesn't exceed end time too much
    if stops:
        last_dep = _time_to_min(stops[-1].departure_time or scenario["end_time"])
        overshoot = last_dep - end_min
        checks["end_time_ok"] = overshoot <= 30
        checks["_end_time"] = f"ends {stops[-1].departure_time} (overshoot={overshoot}min)"

    # 4. Has lunch if trip spans 12:00-13:30
    if start_min <= 720 and end_min >= 810:
        food_words = ["restaurant", "hawker", "cafe", "food", "nasi", "mee", "laksa",
                       "kandar", "curry", "koay", "market", "kopitiam"]
        has_lunch = any(
            any(w in s.name.lower() for w in food_words) and
            660 <= _time_to_min(s.arrival_time or "00:00") <= 870
            for s in stops
        )
        # Also check long stops at food places
        if not has_lunch:
            has_lunch = any(
                _time_to_min(s.arrival_time or "00:00") <= 810 and
                _time_to_min(s.departure_time or "00:00") >= 720 and
                (s.visit_duration_min or 0) >= 120
                for s in stops
            )
        checks["has_lunch"] = has_lunch

    # 5. Has dinner if trip goes past 18:30
    if end_min >= 1110:
        food_words = ["restaurant", "hawker", "cafe", "food", "nasi", "mee", "laksa", "kandar", "curry"]
        has_dinner = any(
            any(w in s.name.lower() for w in food_words) and
            1020 <= _time_to_min(s.arrival_time or "00:00") <= 1230
            for s in stops
        )
        checks["has_dinner"] = has_dinner

    # 6. No duplicate stops
    names = [s.name for s in stops]
    checks["no_duplicates"] = len(names) == len(set(names))

    # 7. All stops have coordinates
    checks["all_have_coords"] = all(s.lat and s.lng for s in stops)

    # 8. All stops have descriptions
    checks["all_have_desc"] = all(s.description and len(s.description) > 20 for s in stops)

    # 9. Time continuity — each stop starts after previous ends
    time_ok = True
    for i in range(1, len(stops)):
        prev_dep = _time_to_min(stops[i-1].departure_time or "00:00")
        curr_arr = _time_to_min(stops[i].arrival_time or "00:00")
        if curr_arr < prev_dep - 1:  # 1min tolerance
            time_ok = False
            break
    checks["time_continuity"] = time_ok

    # 10. Walking mode — all stops should be close (< 35min travel)
    if scenario["travel_mode"] == "walking":
        walk_ok = all(
            (s.travel_to_next.duration_min or 0) <= 35
            for s in stops if s.travel_to_next
        )
        checks["walking_distance_ok"] = walk_ok

    # 11. Min stop duration >= 30min
    checks["min_duration_ok"] = all((s.visit_duration_min or 0) >= 25 for s in stops)

    # 12. Doesn't end too early (>90min unused)
    if stops:
        last_dep = _time_to_min(stops[-1].departure_time or scenario["end_time"])
        unused = end_min - last_dep
        checks["not_too_early"] = unused <= 90
        checks["_unused_min"] = unused

    return checks


def print_result(scenario, result, checks, elapsed):
    """Pretty print test results."""
    passed = sum(1 for k, v in checks.items() if not k.startswith("_") and v is True)
    total = sum(1 for k in checks if not k.startswith("_"))
    status = "✅ PASS" if passed == total else "⚠️ PARTIAL" if passed >= total - 2 else "❌ FAIL"

    print(f"\n{'='*70}")
    print(f"{status} {scenario['name']} ({elapsed:.1f}s)")
    print(f"{'='*70}")
    print(f"  {len(result.stops)} stops | {scenario['travel_mode']} | {scenario['start_time']}-{scenario['end_time']}")
    for s in result.stops:
        travel = f" → {s.travel_to_next.duration_min}min" if s.travel_to_next else ""
        print(f"  {s.order}. {s.name} [{s.arrival_time}-{s.departure_time}] {s.visit_duration_min}min{travel}")

    print(f"\n  Checks ({passed}/{total}):")
    for k, v in checks.items():
        if k.startswith("_"):
            continue
        icon = "✅" if v else "❌"
        detail = checks.get(f"_{k}", "")
        extra = f" ({detail})" if detail else ""
        print(f"    {icon} {k}{extra}")


def run_modify_tests(result, scenario):
    """Test modification operations on the generated itinerary."""
    print(f"\n  --- Modify Tests ---")
    itinerary_dict = {
        "stops": [
            {"name": s.name, "arrival_time": s.arrival_time, "departure_time": s.departure_time,
             "visit_duration_min": s.visit_duration_min, "lat": s.lat, "lng": s.lng,
             "google_maps_url": s.google_maps_url, "photo_url": s.photo_url,
             "description": s.description, "short_description": s.short_description,
             "order": s.order, "rating": s.rating, "address": s.address}
            for s in result.stops
        ],
        "start_time": scenario["start_time"],
        "end_time": scenario["end_time"],
        "travel_mode": scenario["travel_mode"],
        "interests": scenario["interests"],
    }

    for test in MODIFY_TESTS:
        try:
            t0 = time.time()
            modified = modify_itinerary(
                user_message=test["msg"],
                current_itinerary=itinerary_dict,
                travel_mode=scenario["travel_mode"],
            )
            elapsed = time.time() - t0
            new_count = len(modified.stops) if modified else 0
            orig_count = len(result.stops)

            if test["op"] == "remove":
                ok = new_count == orig_count - 1
            elif test["op"] == "add":
                ok = new_count >= orig_count
            elif test["op"] == "swap":
                ok = new_count == orig_count
            elif test["op"] == "rearrange":
                ok = new_count == orig_count
            else:
                ok = new_count > 0

            icon = "✅" if ok else "❌"
            names = [s.name for s in modified.stops] if modified else []
            print(f"    {icon} {test['op']}: \"{test['msg']}\" → {new_count} stops ({elapsed:.1f}s)")
            if not ok:
                print(f"       Expected {test['op']} but got {orig_count}→{new_count}: {names}")
        except Exception as e:
            print(f"    ❌ {test['op']}: \"{test['msg']}\" → ERROR: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", type=int, help="Run specific scenario (1-indexed)")
    parser.add_argument("--modify-only", action="store_true", help="Only test modifications")
    parser.add_argument("--no-modify", action="store_true", help="Skip modification tests")
    args = parser.parse_args()

    scenarios = SCENARIOS
    if args.scenario:
        scenarios = [SCENARIOS[args.scenario - 1]]

    total_pass, total_fail, total_checks = 0, 0, 0
    all_elapsed = []

    for scenario in scenarios:
        try:
            t0 = time.time()
            result = run_itinerary_workflow(
                description=scenario["description"],
                interests=scenario["interests"],
                start_time=scenario["start_time"],
                end_time=scenario["end_time"],
                start_location=scenario["start_location"],
                travel_mode=scenario["travel_mode"],
            )
            elapsed = time.time() - t0
            all_elapsed.append(elapsed)

            checks = evaluate(result, scenario)
            print_result(scenario, result, checks, elapsed)

            passed = sum(1 for k, v in checks.items() if not k.startswith("_") and v is True)
            failed = sum(1 for k, v in checks.items() if not k.startswith("_") and v is False)
            total_pass += passed
            total_fail += failed
            total_checks += passed + failed

            # Run modify tests on first driving scenario
            if not args.no_modify and scenario["travel_mode"] == "driving" and not args.modify_only:
                run_modify_tests(result, scenario)

        except Exception as e:
            print(f"\n{'='*70}")
            print(f"❌ CRASH {scenario['name']}: {e}")
            print(f"{'='*70}")
            total_fail += 1
            total_checks += 1

    # Summary
    print(f"\n{'='*70}")
    print(f"SUMMARY: {total_pass}/{total_checks} checks passed, {total_fail} failed")
    if all_elapsed:
        print(f"Avg time: {sum(all_elapsed)/len(all_elapsed):.1f}s | Total: {sum(all_elapsed):.1f}s")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
