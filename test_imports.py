# test_imports.py
import sys
print(f"Python path: {sys.executable}")

try:
    from supabase import create_client
    print("✅ supabase.create_client imported successfully")
except ImportError as e:
    print(f"❌ Failed to import create_client: {e}")

try:
    import supabase
    print(f"✅ supabase module found at: {supabase.__file__}")
except ImportError as e:
    print(f"❌ Failed to import supabase: {e}")

print("\nPython path:")
for p in sys.path:
    print(f"  {p}")