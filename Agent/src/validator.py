"""
Validation logic for the PenangLens AI Agent.

This module handles constraint checking and self-correction:
- Time constraint validation
- Opening hours validation
- Self-correction message generation
"""

from typing import Dict, List, Optional
from datetime import datetime, time


def validate_time_constraint(
    itinerary: List[Dict], 
    requested_duration_minutes: int,
    total_duration_minutes: int
) -> tuple[bool, Optional[str]]:
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
) -> tuple[bool, Optional[str]]:
    """
    Validate if a landmark is open at the requested visit time.
    
    Args:
        landmark_name: Name of the landmark
        landmark_opening_hours: Opening hours string (e.g., "08:00-23:00" or "24 hours")
        visit_time_str: Requested visit time in HH:MM format
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    # 24-hour locations are always open
    if landmark_opening_hours == "24 hours":
        return True, None
    
    try:
        # Parse opening hours (format: "HH:MM-HH:MM")
        open_time, close_time = landmark_opening_hours.split('-')
        open_hour, open_min = map(int, open_time.split(':'))
        close_hour, close_min = map(int, close_time.split(':'))
        
        # Parse requested time
        req_hour, req_min = map(int, visit_time_str.split(':'))
        
        # Convert to minutes for comparison
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
            # Extract number before 'hour'
            parts = text_lower.split('hour')[0].strip().split()
            if parts:
                hours = float(parts[-1])
                return int(hours * 60)
        
        # Check for minutes
        if 'minute' in text_lower or 'min' in text_lower:
            # Extract number before 'minute' or 'min'
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
