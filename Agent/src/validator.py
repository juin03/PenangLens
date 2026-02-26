"""
Validation logic for the PenangLens AI Agent.

This module handles constraint checking and self-correction:
- Time constraint validation
- Opening hours validation
- Itinerary structure validation
- Self-correction message generation
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, time
import re


def validate_time_constraint(
    itinerary: List[Dict],
    requested_duration_minutes: int,
    total_duration_minutes: int
) -> Tuple[bool, Optional[str]]:
    """
    Validate if the itinerary meets the time constraint.

    Args:
        itinerary: List of stops in the itinerary
        requested_duration_minutes: User's requested total duration
        total_duration_minutes: Calculated total duration

    Returns:
        Tuple of (is_valid, error_message)
    """
    if total_duration_minutes > requested_duration_minutes:
        excess_time = total_duration_minutes - requested_duration_minutes
        error_msg = (
            f"Error: The current itinerary takes {total_duration_minutes} minutes, "
            f"which exceeds the requested {requested_duration_minutes} minutes by {excess_time} minutes. "
            f"Please remove one or more stops to fit within the time constraint."
        )
        return False, error_msg

    return True, None


def validate_opening_hours(
    landmark_name: str,
    landmark_opening_hours: str,
    visit_time_str: str
) -> Tuple[bool, Optional[str]]:
    """
    Validate if a landmark is open at the requested visit time.

    Args:
        landmark_name: Name of the landmark
        landmark_opening_hours: Opening hours string (e.g., "08:00-23:00" or "24 hours")
        visit_time_str: Requested visit time in HH:MM format

    Returns:
        Tuple of (is_valid, error_message)
    """
    if landmark_opening_hours == "24 hours":
        return True, None

    try:
        open_time, close_time = landmark_opening_hours.split('-')
        open_hour, open_min = map(int, open_time.split(':'))
        close_hour, close_min = map(int, close_time.split(':'))

        req_hour, req_min = map(int, visit_time_str.split(':'))

        open_minutes = open_hour * 60 + open_min
        close_minutes = close_hour * 60 + close_min
        req_minutes = req_hour * 60 + req_min

        if not (open_minutes <= req_minutes <= close_minutes):
            error_msg = (
                f"Error: {landmark_name} is closed at {visit_time_str}. "
                f"Opening hours: {landmark_opening_hours}. "
                f"Please choose a different time or location."
            )
            return False, error_msg

        return True, None

    except Exception as e:
        error_msg = f"Error validating opening hours for {landmark_name}: {str(e)}"
        return False, error_msg


def generate_correction_message(validation_errors: List[str]) -> str:
    """
    Generate a system message for self-correction.

    Args:
        validation_errors: List of validation error messages

    Returns:
        A formatted correction message to send back to the LLM
    """
    if not validation_errors:
        return ""

    correction_msg = "VALIDATION FAILED. Please revise your itinerary:\n\n"
    for i, error in enumerate(validation_errors, 1):
        correction_msg += f"{i}. {error}\n"

    correction_msg += "\nPlease generate a new itinerary that addresses these issues."

    return correction_msg


def calculate_total_duration(itinerary: List[Dict]) -> int:
    """
    Calculate total duration of an itinerary including visits and travel time.

    Args:
        itinerary: List of stops, each containing visit_duration_min and travel_time_min

    Returns:
        Total duration in minutes
    """
    total = 0
    for stop in itinerary:
        total += stop.get('visit_duration_min', 0)
        total += stop.get('travel_time_min', 0)

    return total


def parse_duration_from_text(text: str) -> Optional[int]:
    """
    Parse duration in minutes from natural language text.

    Args:
        text: Text containing duration (e.g., "2 hours", "90 minutes", "1.5 hours")

    Returns:
        Duration in minutes or None if not parseable
    """
    text_lower = text.lower()

    try:
        # Check for hours
        if 'hour' in text_lower:
            parts = text_lower.split('hour')[0].strip().split()
            if parts:
                hours = float(parts[-1])
                return int(hours * 60)

        # Check for minutes
        if 'minute' in text_lower or 'min' in text_lower:
            for word in ['minute', 'min']:
                if word in text_lower:
                    parts = text_lower.split(word)[0].strip().split()
                    if parts:
                        minutes = float(parts[-1])
                        return int(minutes)

        # Try to extract just a number (assume minutes)
        words = text_lower.split()
        for word in words:
            try:
                return int(float(word))
            except ValueError:
                continue

    except Exception:
        pass

    return None


def validate_itinerary_response(response_text: str) -> Tuple[bool, List[str]]:
    """
    Validate the quality of an itinerary response from the agent.

    Checks:
    1. Has multiple stops
    2. Includes travel time information
    3. Includes Google Maps links
    4. Includes total time calculation
    5. Has route visualization

    Args:
        response_text: The agent's text response

    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []
    text_lower = response_text.lower()

    # Check for stops
    stop_patterns = [r'stop\s*\d', r'\*\*stop', r'#+ stop']
    has_stops = any(re.search(p, text_lower) for p in stop_patterns)
    if not has_stops:
        # Also check for numbered lists
        has_numbered = bool(re.search(r'^\d+\.\s+\*\*', response_text, re.MULTILINE))
        if not has_numbered:
            issues.append("No clearly numbered stops found in the itinerary.")

    # Check for Google Maps links
    if 'google.com/maps' not in text_lower and '📍' not in response_text:
        issues.append("Missing Google Maps links for locations.")

    # Check for travel time between stops
    travel_indicators = ['walk', 'drive', 'minutes to', 'min to', '→', 'travel time']
    if not any(ind in text_lower for ind in travel_indicators):
        issues.append("Missing travel time information between stops.")

    # Check for total time
    total_indicators = ['total time', 'total duration', 'total:', 'overall time']
    if not any(ind in text_lower for ind in total_indicators):
        issues.append("Missing total time calculation.")

    # Check for route visualization
    if 'google.com/maps/dir' not in text_lower:
        issues.append("Missing route visualization URL (create_route_visualization_tool not used).")

    is_valid = len(issues) == 0
    return is_valid, issues
