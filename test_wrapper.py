# test_wrapper.py
from db_wrapper import DatabaseWrapper
import os
import json

print("=" * 60)
print("TESTING DATABASE WRAPPER")
print("=" * 60)

# Test with Supabase mode
print("\n🔌 Testing Supabase mode...")
os.environ['STREAMLIT_RUNTIME_ENV'] = 'production'

try:
    db = DatabaseWrapper()
    
    # Test 1: Get distinct criteria
    print("\n1. Getting distinct criteria...")
    criteria = db.get_distinct_values('criteria')
    print(f"   Found {len(criteria)} criteria")
    print(f"   First 5: {criteria[:5]}")
    
    # Test 2: Search for something
    print("\n2. Searching for 'energy'...")
    results = db.search_energy_data("energy", limit=5)
    print(f"   Found {len(results)} results")
    if results:
        print(f"   First result ID: {results[0].get('id') if isinstance(results[0], dict) else results[0][0]}")
    
    # Test 3: Get counts
    print("\n3. Getting counts by climate...")
    counts = db.get_counts_with_filters('climate')
    print(f"   Found {len(counts)} climate types")
    for climate, count in list(counts.items())[:5]:
        print(f"   - {climate}: {count}")
    
    # Test 4: Get user
    print("\n4. Getting admin user...")
    user = db.get_user('admin')
    if user:
        print(f"   Found admin user: {user.get('username')} with role {user.get('role')}")
    else:
        print("   Admin user not found")
    
    db.close()
    print("\n✅ Supabase tests complete!")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

# Test with SQLite mode
print("\n" + "=" * 60)
print("📂 Testing SQLite mode...")
print("=" * 60)

# Remove env var to force SQLite
os.environ.pop('STREAMLIT_RUNTIME_ENV', None)

try:
    db = DatabaseWrapper()
    
    # Test 1: Get distinct criteria
    print("\n1. Getting distinct criteria...")
    criteria = db.get_distinct_values('criteria')
    print(f"   Found {len(criteria)} criteria")
    print(f"   First 5: {criteria[:5]}")
    
    # Test 2: Search
    print("\n2. Searching for 'energy'...")
    results = db.search_energy_data("energy", limit=5)
    print(f"   Found {len(results)} results")
    
    db.close()
    print("\n✅ SQLite tests complete!")
    
except Exception as e:
    print(f"\n❌ Error: {e}")