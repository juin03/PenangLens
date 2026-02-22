"""
Route Optimization for PenangLens Itinerary Planning

This module provides algorithms to optimize the order of locations in an itinerary
to minimize total travel distance/time.

Uses Google Distance Matrix API to calculate actual distances between all locations,
then applies optimization algorithms to find the best route.
"""

import os
import requests
from typing import List, Dict, Tuple
import itertools


def get_distance_matrix(locations: List[str]) -> Dict[Tuple[int, int], Dict]:
    """
    Get pairwise distances and travel times between all locations using Google Distance Matrix API.
    Handles API limits by batching requests.
    
    Args:
        locations: List of location names/addresses
        
    Returns:
        Dictionary mapping (origin_idx, dest_idx) tuples to distance/duration info
        Example: {(0, 1): {"distance": 650, "duration": 480}, ...}
    """
    api_key = os.getenv('GOOGLE_MAPS_API_KEY') or os.getenv('GOOGLE_API_KEY')
    
    if not api_key:
        print("Warning: No Google Maps API key found")
        return {}
    
    # Google Distance Matrix API limit: 100 elements per request
    # elements = origins × destinations
    # For safety, limit to 10 locations at a time (10×10 = 100 elements)
    
    MAX_LOCATIONS_PER_BATCH = 10
    
    if len(locations) > MAX_LOCATIONS_PER_BATCH:
        print(f"Warning: {len(locations)} locations exceeds batch size. Using nearest neighbor only.")
        # For large sets, we'll only calculate distances needed for nearest neighbor
        # to avoid API limits. This is less accurate but necessary.
        return get_distance_matrix_sparse(locations, api_key)
    
    # Format locations for API (add Penang, Malaysia if not present)
    formatted_locations = []
    for loc in locations:
        if "Penang" not in loc and "Malaysia" not in loc:
            formatted_locations.append(f"{loc}, George Town, Penang, Malaysia")
        else:
            formatted_locations.append(loc)
    
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    
    params = {
        'origins': '|'.join(formatted_locations),
        'destinations': '|'.join(formatted_locations),
        'mode': 'walking',
        'key': api_key
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        if data['status'] != 'OK':
            print(f"Distance Matrix API error: {data['status']}")
            return {}
        
        # Parse response into distance matrix
        matrix = {}
        rows = data.get('rows', [])
        
        for i, row in enumerate(rows):
            elements = row.get('elements', [])
            for j, element in enumerate(elements):
                if element['status'] == 'OK':
                    matrix[(i, j)] = {
                        'distance': element['distance']['value'],  # meters
                        'duration': element['duration']['value']   # seconds
                    }
        
        return matrix
        
    except Exception as e:
        print(f"Error getting distance matrix: {e}")
        return {}


def get_distance_matrix_sparse(locations: List[str], api_key: str) -> Dict[Tuple[int, int], Dict]:
    """
    Get sparse distance matrix for large location sets (only nearest neighbors).
    This avoids API limits by not requesting all pairs.
    
    Args:
        locations: List of location names/addresses  
        api_key: Google Maps API key
        
    Returns:
        Sparse distance matrix with only needed distances
    """
    # For large sets, we only get distances needed for nearest neighbor algorithm
    # This means: for each location, get distances to ~5 nearest candidates
    
    formatted_locations = []
    for loc in locations:
        if "Penang" not in loc and "Malaysia" not in loc:
            formatted_locations.append(f"{loc}, George Town, Penang, Malaysia")
        else:
            formatted_locations.append(loc)
    
    matrix = {}
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    
    # Process in small batches: each origin against 10 destinations at a time
    for i in range(len(formatted_locations)):
        for batch_start in range(0, len(formatted_locations), 10):
            batch_end = min(batch_start + 10, len(formatted_locations))
            batch_destinations = formatted_locations[batch_start:batch_end]
            
            params = {
                'origins': formatted_locations[i],
                'destinations': '|'.join(batch_destinations),
                'mode': 'walking',
                'key': api_key
            }
            
            try:
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                if data['status'] == 'OK' and data.get('rows'):
                    elements = data['rows'][0].get('elements', [])
                    for j, element in enumerate(elements):
                        dest_idx = batch_start + j
                        if element['status'] == 'OK':
                            matrix[(i, dest_idx)] = {
                                'distance': element['distance']['value'],
                                'duration': element['duration']['value']
                            }
            except Exception as e:
                print(f"Error in batch request: {e}")
                continue
    
    return matrix


def nearest_neighbor_route(distance_matrix: Dict[Tuple[int, int], Dict], 
                           num_locations: int,
                           start_idx: int = 0) -> List[int]:
    """
    Find route using greedy nearest-neighbor algorithm.
    Not optimal but fast and gives good results for small sets.
    
    Args:
        distance_matrix: Output from get_distance_matrix()
        num_locations: Number of locations
        start_idx: Index to start from (default 0)
        
    Returns:
        List of location indices in optimized order
    """
    if num_locations <= 2:
        return list(range(num_locations))
    
    unvisited = set(range(num_locations))
    route = [start_idx]
    unvisited.remove(start_idx)
    
    current = start_idx
    
    while unvisited:
        # Find nearest unvisited location
        nearest = None
        min_distance = float('inf')
        
        for next_loc in unvisited:
            if (current, next_loc) in distance_matrix:
                dist = distance_matrix[(current, next_loc)]['distance']
                if dist < min_distance:
                    min_distance = dist
                    nearest = next_loc
        
        if nearest is None:
            # Fallback: just pick the first unvisited
            nearest = unvisited.pop()
            route.append(nearest)
        else:
            route.append(nearest)
            unvisited.remove(nearest)
        
        current = nearest
    
    return route


def brute_force_optimal_route(distance_matrix: Dict[Tuple[int, int], Dict],
                               num_locations: int,
                               start_idx: int = 0) -> List[int]:
    """
    Find truly optimal route by trying all permutations (only for small N <= 8).
    
    Args:
        distance_matrix: Output from get_distance_matrix()
        num_locations: Number of locations (should be <= 8)
        start_idx: Index to start from
        
    Returns:
        List of location indices in optimal order
    """
    if num_locations > 8:
        print("Warning: Too many locations for brute force, using nearest neighbor")
        return nearest_neighbor_route(distance_matrix, num_locations, start_idx)
    
    if num_locations <= 2:
        return list(range(num_locations))
    
    # Get all locations except start
    other_locations = [i for i in range(num_locations) if i != start_idx]
    
    best_route = None
    best_distance = float('inf')
    
    # Try all permutations
    for perm in itertools.permutations(other_locations):
        route = [start_idx] + list(perm)
        
        # Calculate total distance
        total_dist = 0
        for i in range(len(route) - 1):
            if (route[i], route[i+1]) in distance_matrix:
                total_dist += distance_matrix[(route[i], route[i+1])]['distance']
            else:
                total_dist = float('inf')
                break
        
        if total_dist < best_distance:
            best_distance = total_dist
            best_route = route
    
    return best_route if best_route else list(range(num_locations))


def optimize_route(locations: List[str], 
                   start_location: str = None,
                   use_brute_force: bool = True) -> Dict:
    """
    Optimize the order of locations to minimize total walking distance.
    
    Args:
        locations: List of location names/addresses
        start_location: Optional specific start location (must be in locations list)
        use_brute_force: If True and N<=8, use optimal algorithm; else use nearest neighbor
        
    Returns:
        Dictionary with:
        - 'optimized_order': List of locations in optimal order
        - 'total_distance': Total walking distance in meters
        - 'total_duration': Total walking time in seconds
        - 'original_order': Original order for comparison
    """
    if len(locations) < 2:
        return {
            'optimized_order': locations,
            'total_distance': 0,
            'total_duration': 0,
            'original_order': locations
        }
    
    # Get distance matrix
    distance_matrix = get_distance_matrix(locations)
    
    if not distance_matrix:
        print("Could not get distance matrix, returning original order")
        return {
            'optimized_order': locations,
            'total_distance': None,
            'total_duration': None,
            'original_order': locations
        }
    
    # Determine start index
    start_idx = 0
    if start_location and start_location in locations:
        start_idx = locations.index(start_location)
    
    # Optimize route
    if use_brute_force and len(locations) <= 8:
        optimized_indices = brute_force_optimal_route(distance_matrix, len(locations), start_idx)
    else:
        optimized_indices = nearest_neighbor_route(distance_matrix, len(locations), start_idx)
    
    # Calculate total distance and duration
    total_distance = 0
    total_duration = 0
    
    for i in range(len(optimized_indices) - 1):
        curr = optimized_indices[i]
        next_loc = optimized_indices[i + 1]
        if (curr, next_loc) in distance_matrix:
            total_distance += distance_matrix[(curr, next_loc)]['distance']
            total_duration += distance_matrix[(curr, next_loc)]['duration']
    
    # Return optimized order
    optimized_order = [locations[i] for i in optimized_indices]
    
    return {
        'optimized_order': optimized_order,
        'optimized_indices': optimized_indices,
        'total_distance': total_distance,
        'total_duration': total_duration,
        'original_order': locations,
        'distance_matrix': distance_matrix
    }


# Example usage
if __name__ == "__main__":
    test_locations = [
        "Armenian Street, George Town",
        "Lebuh Chulia, George Town",
        "Lebuh Ah Quee, George Town",
        "Cannon Street, George Town"
    ]
    
    result = optimize_route(test_locations)
    
    print("Original order:", result['original_order'])
    print("Optimized order:", result['optimized_order'])
    print(f"Total distance: {result['total_distance']}m")
    print(f"Total duration: {result['total_duration']}s ({result['total_duration']//60} min)")
