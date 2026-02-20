# clean_asterisks.py
from db_wrapper import DatabaseWrapper
import re

print("🔍 Starting location cleanup...")

db = DatabaseWrapper()
all_records = db.get_energy_data(limit=5000)

updated_count = 0
for record in all_records:
    record_id = record['id']
    old_loc = record.get('location', '')
    
    if old_loc:
        # Remove asterisks, extra spaces, and trim
        new_loc = old_loc.replace('*', '').strip()
        new_loc = re.sub(r'\s+', ' ', new_loc)  # Normalize spaces
        
        # Check if anything changed
        if new_loc != old_loc:
            print(f"📝 Updating record {record_id}:")
            print(f"   Old: '{old_loc}'")
            print(f"   New: '{new_loc}'")
            db.update_record('energy_data', record_id, {'location': new_loc})
            updated_count += 1

print(f"\n✅ Updated {updated_count} records")

# Show what's left to fix
if updated_count > 0:
    print("\n📍 Please regenerate your location cache:")
    print("   python generate_location_cache.py")