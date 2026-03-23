"""
Smart Itinerary Optimizer with real-time constraints.
Optimizes itineraries based on time, weather, crowds, and opening hours.
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, AsyncGenerator
import os
from .logging_config import get_logger

logger = get_logger("penang_agent.smart_optimizer")


# Crowd patterns (based on typical tourist behavior)
CROWD_PATTERNS = {
    "fort_cornwallis": {"peak_start": 10, "peak_end": 14, "quiet_before": 9, "quiet_after": 15},
    "kek_lok_si": {"peak_start": 11, "peak_end": 15, "quiet_before": 8, "quiet_after": 16},
    "penang_hill": {"peak_start": 10, "peak_end": 13, "quiet_before": 8, "quiet_after": 15},
    "khoo_kongsi": {"peak_start": 11, "peak_end": 14, "quiet_before": 9, "quiet_after": 15},
    "cheong_fatt_tze": {"peak_start": 11, "peak_end": 13, "quiet_before": 10, "quiet_after": 14},
}

# Golden hour spots (best for photos)
GOLDEN_HOUR_SPOTS = [
    "kek_lok_si", "penang_hill", "clan_jetties", "fort_cornwallis", "komtar"
]

# Indoor spots (good for rain)
INDOOR_SPOTS = [
    "cheong_fatt_tze", "pinang_peranakan_mansion", "khoo_kongsi", 
    "penang_state_museum", "camera_museum"
]


class SmartOptimizer:
    """Optimizes itineraries with time-of-day intelligence."""
    
    def __init__(self):
        self.weather_api_key = os.getenv("OPENWEATHER_API_KEY", "")
    
    async def optimize_with_streaming(
        self,
        spots: List[Dict],
        start_time: str,
        end_time: str,
        travel_mode: str = "walking"
    ) -> AsyncGenerator[Dict, None]:
        """
        Optimize itinerary with streaming progress updates.
        
        Yields status updates as JSON:
        {"type": "status", "message": "Checking weather..."}
        {"type": "status", "message": "Analyzing crowd patterns..."}
        {"type": "result", "optimized_spots": [...]}
        """
        try:
            # Parse times
            start_hour = int(start_time.split(':')[0])
            end_hour = int(end_time.split(':')[0])
            available_minutes = (end_hour - start_hour) * 60
            
            yield {"type": "status", "message": "🌤️ Checking weather forecast..."}
            await asyncio.sleep(0.1)  # Allow UI to update
            
            # Quick weather check (parallel)
            weather_task = asyncio.create_task(self._get_weather_quick())
            
            yield {"type": "status", "message": "👥 Analyzing crowd patterns..."}
            await asyncio.sleep(0.1)
            
            # Score each spot based on timing
            scored_spots = []
            for spot in spots:
                score = self._calculate_time_score(
                    spot, start_hour, end_hour
                )
                scored_spots.append({**spot, "time_score": score})
            
            yield {"type": "status", "message": "⏰ Checking opening hours..."}
            await asyncio.sleep(0.1)
            
            # Filter out closed spots
            open_spots = [s for s in scored_spots if self._is_open(s, start_hour, end_hour)]
            
            # Get weather result
            weather = await weather_task
            is_rainy = weather.get("rain_probability", 0) > 50
            
            if is_rainy:
                yield {"type": "status", "message": "☔ Rain expected - prioritizing indoor spots..."}
                await asyncio.sleep(0.1)
                # Boost indoor spots
                for spot in open_spots:
                    if self._is_indoor(spot):
                        spot["time_score"] += 20
            
            yield {"type": "status", "message": "📸 Optimizing for golden hour..."}
            await asyncio.sleep(0.1)
            
            # Boost golden hour spots if timing is right
            golden_hour_start = 16  # 4 PM
            golden_hour_end = 18    # 6 PM
            if end_hour >= golden_hour_start:
                for spot in open_spots:
                    if self._is_golden_hour_spot(spot):
                        spot["time_score"] += 15
                        spot["golden_hour_tip"] = "Best for photos at sunset"
            
            yield {"type": "status", "message": "🎯 Finalizing optimal sequence..."}
            await asyncio.sleep(0.1)
            
            # Sort by score (highest first)
            open_spots.sort(key=lambda x: x["time_score"], reverse=True)
            
            # Select spots that fit time budget
            selected = self._fit_to_time_budget(open_spots, available_minutes)
            
            # Add timing recommendations
            optimized = self._add_timing_recommendations(selected, start_hour, is_rainy)
            
            yield {
                "type": "result",
                "optimized_spots": optimized,
                "weather": weather,
                "total_spots": len(optimized),
                "optimization_applied": True
            }
            
        except Exception as e:
            logger.error(f"Smart optimization failed: {e}")
            yield {
                "type": "error",
                "message": "Optimization failed, using default order",
                "spots": spots
            }
    
    async def _get_weather_quick(self) -> Dict:
        """Quick weather check (cached, non-blocking)."""
        try:
            # In production, call OpenWeather API
            # For now, return mock data quickly
            await asyncio.sleep(0.2)  # Simulate API call
            return {
                "rain_probability": 30,
                "temperature": 32,
                "condition": "partly_cloudy"
            }
        except:
            return {"rain_probability": 0, "temperature": 30, "condition": "clear"}
    
    def _calculate_time_score(self, spot: Dict, start_hour: int, end_hour: int) -> int:
        """Calculate timing score for a spot (0-100)."""
        score = 50  # Base score
        
        spot_id = spot.get("id", "").lower().replace(" ", "_")
        
        # Check crowd patterns
        if spot_id in CROWD_PATTERNS:
            pattern = CROWD_PATTERNS[spot_id]
            
            # Bonus if visiting during quiet hours
            if start_hour < pattern["quiet_before"]:
                score += 25
            elif end_hour > pattern["quiet_after"]:
                score += 20
            
            # Penalty if visiting during peak
            if pattern["peak_start"] <= start_hour <= pattern["peak_end"]:
                score -= 15
        
        return max(0, min(100, score))
    
    def _is_open(self, spot: Dict, start_hour: int, end_hour: int) -> bool:
        """Check if spot is open during visit window."""
        # Get opening hours from spot data
        opening_hours = spot.get("opening_hours", {})
        
        if not opening_hours:
            return True  # Assume open if no data
        
        open_time = opening_hours.get("open", 0)
        close_time = opening_hours.get("close", 24)
        
        # Check if visit window overlaps with opening hours
        return start_hour >= open_time and end_hour <= close_time
    
    def _is_indoor(self, spot: Dict) -> bool:
        """Check if spot is indoor (good for rain)."""
        spot_id = spot.get("id", "").lower().replace(" ", "_")
        return spot_id in INDOOR_SPOTS
    
    def _is_golden_hour_spot(self, spot: Dict) -> bool:
        """Check if spot is good for golden hour photos."""
        spot_id = spot.get("id", "").lower().replace(" ", "_")
        return spot_id in GOLDEN_HOUR_SPOTS
    
    def _fit_to_time_budget(self, spots: List[Dict], available_minutes: int) -> List[Dict]:
        """Select spots that fit within time budget."""
        selected = []
        used_minutes = 0
        
        for spot in spots:
            duration = spot.get("visit_duration_min", 45)
            travel_time = spot.get("travel_time_min", 10)
            
            total_needed = duration + travel_time
            
            if used_minutes + total_needed <= available_minutes:
                selected.append(spot)
                used_minutes += total_needed
            
            if len(selected) >= 6:  # Max 6 spots
                break
        
        return selected
    
    def _add_timing_recommendations(
        self, spots: List[Dict], start_hour: int, is_rainy: bool
    ) -> List[Dict]:
        """Add timing tips to each spot."""
        current_hour = start_hour
        
        for i, spot in enumerate(spots):
            duration = spot.get("visit_duration_min", 45)
            spot_id = spot.get("id", "").lower().replace(" ", "_")
            
            tips = []
            
            # Crowd tip
            if spot_id in CROWD_PATTERNS:
                pattern = CROWD_PATTERNS[spot_id]
                if current_hour < pattern["quiet_before"]:
                    tips.append("🟢 Quiet time - fewer crowds")
                elif pattern["peak_start"] <= current_hour <= pattern["peak_end"]:
                    tips.append("🟡 Peak hours - expect crowds")
                else:
                    tips.append("🟢 Good timing")
            
            # Weather tip
            if is_rainy and self._is_indoor(spot):
                tips.append("☔ Indoor - perfect for rainy weather")
            
            # Golden hour tip
            if spot.get("golden_hour_tip"):
                tips.append(f"📸 {spot['golden_hour_tip']}")
            
            spot["suggested_time"] = f"{current_hour:02d}:00"
            spot["timing_tips"] = tips
            
            # Update current time
            current_hour += duration // 60
        
        return spots


# Global instance
smart_optimizer = SmartOptimizer()
