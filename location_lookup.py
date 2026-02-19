# location_lookup.py
import streamlit as st
import json
import os
import random

@st.cache_data(ttl=86400)  # Cache for 24 hours
def load_location_cache():
    """Load the pre-computed location cache"""
    cache_file = os.path.join(os.path.dirname(__file__), 'location_cache.json')
    try:
        with open(cache_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        st.warning("Location cache not found. Please run generate_location_cache.py first.")
        return {}

def get_location_coordinates(location_name):
    """
    Lightning fast O(1) lookup from pre-computed cache.
    Returns [lat, lon] or None if not found.
    """
    if not location_name:
        return None
    
    cache = load_location_cache()
    location_str = str(location_name).strip()
    
    # Direct lookup
    coords = cache.get(location_str)
    if coords is not None:  # ✅ Check for None
        # Add small random offset to prevent exact overlaps
        return [coords[0] + random.uniform(-0.05, 0.05), 
                coords[1] + random.uniform(-0.05, 0.05)]
    
    # Try case-insensitive match
    for cached_loc, cached_coords in cache.items():
        # ✅ Skip if cached_coords is None
        if cached_coords is None:
            continue
        if cached_loc.lower() == location_str.lower():
            return [cached_coords[0] + random.uniform(-0.05, 0.05), 
                    cached_coords[1] + random.uniform(-0.05, 0.05)]
    
    # Try partial match for things like "Eastern Europe (11 countries)"
    for cached_loc, cached_coords in cache.items():
        # ✅ Skip if cached_coords is None
        if cached_coords is None:
            continue
        if location_str.lower() in cached_loc.lower() or cached_loc.lower() in location_str.lower():
            return [cached_coords[0] + random.uniform(-0.1, 0.1), 
                    cached_coords[1] + random.uniform(-0.1, 0.1)]
    
    return None