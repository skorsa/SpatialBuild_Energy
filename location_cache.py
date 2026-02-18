# location_cache.py - Generated file
import json
import os

@st.cache_data
def load_location_cache():
    """Load pre-computed location coordinates"""
    cache_file = os.path.join(os.path.dirname(__file__), 'location_cache.json')
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            return json.load(f)
    return {}

def get_location_coordinates(location_name):
    """Lightning fast O(1) lookup"""
    cache = load_location_cache()
    return cache.get(str(location_name).strip())