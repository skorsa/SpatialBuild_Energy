# diagnose_geocoding.py
import json
import time
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from db_wrapper import DatabaseWrapper

print("🚀 Starting geocoding diagnosis...")

# Initialize
db = DatabaseWrapper()
all_records = db.get_energy_data(limit=5000)

# Get unique locations
locations = set()
for record in all_records:
    loc = record.get('location')
    if loc and loc not in ['', None]:
        locations.add(str(loc).strip())

print(f"📍 Found {len(locations)} unique locations")

# Test geocoder with a simple location first
geolocator = Nominatim(user_agent="spatialbuild_diagnostic", timeout=10)
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

# Test with a known good location
test_loc = "London, UK"
print(f"\n🔍 Testing geocoder with: '{test_loc}'")
try:
    result = geocode(test_loc)
    if result:
        print(f"✅ Working! Got: [{result.latitude}, {result.longitude}]")
    else:
        print("❌ No result returned")
except Exception as e:
    print(f"❌ Error: {e}")

# Now test a few of your actual locations
test_samples = list(locations)[:10]
print("\n🔍 Testing sample locations:")
for loc in test_samples:
    print(f"\n  Testing: '{loc}'")
    try:
        result = geocode(loc)
        if result:
            print(f"  ✅ Found: [{result.latitude}, {result.longitude}]")
        else:
            print(f"  ❌ Not found")
    except Exception as e:
        print(f"  ❌ Error: {e}")
    time.sleep(1)