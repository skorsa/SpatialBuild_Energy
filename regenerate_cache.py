# regenerate_cache.py
import json
import os
from db_wrapper import DatabaseWrapper
from location_lookup import get_location_coordinates
import time

print("🚀 Starting cache regeneration...")

# Initialize database connection
# This will use environment variables if available, or fall back to SQLite
db = DatabaseWrapper()
print(f"📊 Connected to database (Supabase mode: {db.use_supabase})")

# Get all records
print("📥 Fetching all records...")
all_records = db.get_energy_data(limit=5000)
print(f"✅ Found {len(all_records)} total records")

# Extract unique locations
locations = set()
for record in all_records:
    loc = record.get('location')
    if loc and loc not in ['', None]:
        locations.add(str(loc).strip())

print(f"📍 Found {len(locations)} unique locations to geocode")

# Build new cache
cache = {}
success_count = 0
fail_count = 0

for i, loc in enumerate(locations, 1):
    print(f"⏳ [{i}/{len(locations)}] Geocoding: {loc[:50]}...")
    
    try:
        coords = get_location_coordinates(loc)
        cache[loc] = coords
        if coords:
            success_count += 1
            print(f"   ✅ Found: {coords}")
        else:
            fail_count += 1
            print(f"   ❌ Not found")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        cache[loc] = None
        fail_count += 1
    
    # Small delay to be nice to the geocoding service
    time.sleep(0.1)

# Save to file
with open('location_cache.json', 'w', encoding='utf-8') as f:
    json.dump(cache, f, indent=2)

print("\n" + "="*50)
print("✅ Cache regeneration complete!")
print(f"📈 Successfully geocoded: {success_count}")
print(f"📉 Failed: {fail_count}")
print(f"💾 Cache saved to location_cache.json")
print("="*50)