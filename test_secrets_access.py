# test_secrets_access.py
import streamlit as st
import os

print(f"Current working directory: {os.getcwd()}")
print(f"Looking for secrets in: {os.path.join(os.getcwd(), '.streamlit', 'secrets.toml')}")
print(f"File exists: {os.path.exists(os.path.join(os.getcwd(), '.streamlit', 'secrets.toml'))}")

try:
    # Try to access secrets
    if 'supabase_url' in st.secrets:
        print("✅ supabase_url found in secrets")
        print(f"   Value starts with: {st.secrets['supabase_url'][:20]}...")
    else:
        print("❌ supabase_url not in secrets")
        print(f"Available secrets keys: {list(st.secrets.keys())}")
except Exception as e:
    print(f"❌ Error accessing secrets: {e}")