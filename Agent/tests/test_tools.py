"""
Unit tests for the tools module.

Tests the local tools (no API keys required):
- Landmark loading
- Category search
- Opening hours check
"""

import pytest
from src.tools import load_landmarks, search_places, check_opening_hours, get_landmark_by_name


class TestLoadLandmarks:
    """Tests for the landmark loading function."""

    def test_load_landmarks_returns_list(self):
        landmarks = load_landmarks()
        assert isinstance(landmarks, list)

    def test_load_landmarks_not_empty(self):
        landmarks = load_landmarks()
        assert len(landmarks) > 0

    def test_load_landmarks_has_expected_count(self):
        """We expanded to 50 landmarks."""
        landmarks = load_landmarks()
        assert len(landmarks) >= 50

    def test_landmark_has_required_fields(self):
        landmarks = load_landmarks()
        required_fields = ["id", "name", "tags", "location", "avg_duration_min", "opening_hours"]
        for landmark in landmarks:
            for field in required_fields:
                assert field in landmark, f"Missing field '{field}' in landmark {landmark.get('name', 'UNKNOWN')}"

    def test_landmark_has_new_fields(self):
        """Verify the expanded landmark schema has lat/lng and other new fields."""
        landmarks = load_landmarks()
        new_fields = ["lat", "lng", "budget_level", "accessibility", "family_friendly"]
        for landmark in landmarks:
            for field in new_fields:
                assert field in landmark, f"Missing new field '{field}' in landmark {landmark.get('name', 'UNKNOWN')}"


class TestSearchPlaces:
    """Tests for the search_places function."""

    def test_search_history(self):
        result = search_places("history")
        assert "Fort Cornwallis" in result

    def test_search_food(self):
        result = search_places("food")
        assert "found" in result.lower() or "Found" in result

    def test_search_art(self):
        result = search_places("art")
        assert "Street Art" in result

    def test_search_invalid_category(self):
        result = search_places("nonexistent_category_xyz")
        assert "No places found" in result or "no places" in result.lower()

    def test_search_heritage(self):
        result = search_places("heritage")
        assert "found" in result.lower()

    def test_search_nature(self):
        result = search_places("nature")
        assert "found" in result.lower()

    def test_search_case_insensitive(self):
        result_lower = search_places("history")
        result_upper = search_places("History")
        # Both should return results
        assert "Fort Cornwallis" in result_lower
        assert "Fort Cornwallis" in result_upper


class TestGetLandmarkByName:
    """Tests for landmark name lookup."""

    def test_exact_match(self):
        landmark = get_landmark_by_name("Fort Cornwallis")
        assert landmark is not None
        assert landmark["id"] == "L01"

    def test_case_insensitive(self):
        landmark = get_landmark_by_name("fort cornwallis")
        assert landmark is not None

    def test_not_found(self):
        landmark = get_landmark_by_name("Nonexistent Place ABC")
        assert landmark is None


class TestCheckOpeningHours:
    """Tests for opening hours verification."""

    def test_open_time(self):
        result = check_opening_hours("Fort Cornwallis", "10:00")
        assert "OPEN" in result

    def test_closed_time(self):
        result = check_opening_hours("Fort Cornwallis", "03:00")
        assert "CLOSED" in result

    def test_24_hour_place(self):
        result = check_opening_hours("Penang Street Art", "03:00")
        assert "open 24 hours" in result.lower() or "OPEN" in result

    def test_not_found_landmark(self):
        result = check_opening_hours("Nonexistent Place", "10:00")
        assert "not found" in result.lower()

    def test_boundary_open(self):
        """Test opening time boundary — should be open at opening time."""
        result = check_opening_hours("Fort Cornwallis", "08:00")
        assert "OPEN" in result

    def test_boundary_close(self):
        """Test closing time boundary — should be open at closing time."""
        result = check_opening_hours("Fort Cornwallis", "23:00")
        assert "OPEN" in result
