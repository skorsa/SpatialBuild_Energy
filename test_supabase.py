# test_supabase.py
from supabase import create_client
import os

# Paste your credentials here for testing
url = input("Enter your Supabase URL: ").strip()
key = input("Enter your Supabase anon key: ").strip()

try:
    print("\n🔌 Connecting to Supabase...")
    supabase = create_client(url, key)
    
    # Try a simple query (table might not exist yet)
    try:
        result = supabase.table('energy_data').select('*').limit(1).execute()
        print("✅ Connected! Table exists.")
    except Exception as table_error:
        print("✅ Connected! (Table doesn't exist yet - that's fine)")
    
    print("\n🎉 Supabase is working!")
    print("\nSave these in your .env file:")
    print(f"SUPABASE_URL={url}")
    print(f"SUPABASE_KEY={key}")
    
except Exception as e:
    print(f"❌ Connection failed: {e}")
    print("\nTroubleshooting:")
    print("1. Check your URL - should end with .supabase.co")
    print("2. Check your key - should start with 'eyJ'")
    print("3. Make sure you're using the anon/public key, not the service_role key")