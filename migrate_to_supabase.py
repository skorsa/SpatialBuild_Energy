# migrate_to_supabase.py
import sqlite3
import json
from supabase import create_client
import os
from dotenv import load_dotenv
import time
import base64

load_dotenv()

def serialize_value(value):
    """Convert bytes to string for JSON serialization"""
    if value is None:
        return None
    elif isinstance(value, bytes):
        # For Supabase, we need to send the actual password string
        # Assuming the passwords are bcrypt hashes (which are ASCII-safe)
        try:
            return value.decode('utf-8')
        except:
            # If it's not UTF-8, convert to base64
            return base64.b64encode(value).decode('ascii')
    elif isinstance(value, (str, int, float, bool)):
        return value
    else:
        return str(value)

def migrate_data():
    print("=" * 60)
    print("🚀 SUPABASE MIGRATION SCRIPT")
    print("=" * 60)
    
    # Get Supabase credentials
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    
    if not url or not key:
        print("\n❌ Missing Supabase credentials!")
        print("Please set SUPABASE_URL and SUPABASE_KEY in your .env file")
        return
    
    # Connect to Supabase
    print("\n🔌 Connecting to Supabase...")
    supabase = create_client(url, key)
    
    # Connect to SQLite with proper text handling
    print("📂 Connecting to local SQLite database...")
    sqlite_conn = sqlite3.connect('my_database.db')
    # Don't use bytes factory - we'll handle it manually
    sqlite_cursor = sqlite_conn.cursor()
    
    # Get all tables, but skip sqlite internal tables
    sqlite_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = [table[0] for table in sqlite_cursor.fetchall()]
    
    print(f"\n📋 Found tables: {', '.join(tables)}")
    
    migration_summary = {}
    
    for table_name in tables:
        print(f"\n{'='*40}")
        print(f"📋 Migrating table: {table_name}")
        print('='*40)
        
        # Get all data from SQLite
        sqlite_cursor.execute(f"SELECT * FROM {table_name}")
        rows = sqlite_cursor.fetchall()
        
        # Get column names
        sqlite_cursor.execute(f"PRAGMA table_info({table_name})")
        columns_info = sqlite_cursor.fetchall()
        columns = [col[1] for col in columns_info]
        
        print(f"   Found {len(rows)} records")
        print(f"   Columns: {', '.join(columns)}")
        
        if len(rows) == 0:
            print("   ⏭️  No data to migrate")
            migration_summary[table_name] = 0
            continue
        
        # Insert in batches
        batch_size = 50
        successful = 0
        failed = 0
        
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i+batch_size]
            
            # Convert to dict format with proper serialization
            records = []
            for row in batch:
                record = {}
                for j, col in enumerate(columns):
                    if col != 'rowid' and j < len(row):
                        value = row[j]
                        # Special handling for password field
                        if col == 'password' and isinstance(value, bytes):
                            # For Supabase, we need to send the actual hash string
                            # Assuming it's a bcrypt hash (starts with $2b$)
                            try:
                                # Try to decode as UTF-8
                                record[col] = value.decode('utf-8')
                            except:
                                # If that fails, convert to base64
                                record[col] = base64.b64encode(value).decode('ascii')
                        else:
                            record[col] = serialize_value(value)
                records.append(record)
            
            # Insert into Supabase
            try:
                print(f"   Attempting to insert batch {i//batch_size + 1}...")
                result = supabase.table(table_name).insert(records).execute()
                successful += len(batch)
                print(f"   ✅ Batch {i//batch_size + 1}/{(len(rows)-1)//batch_size + 1}: {len(batch)} records")
            except Exception as e:
                print(f"   ❌ Batch {i//batch_size + 1} failed: {str(e)[:200]}...")
                failed += len(batch)
                
                # Save failed batch for inspection
                failed_file = f'failed_batch_{table_name}_{i}.json'
                with open(failed_file, 'w', encoding='utf-8') as f:
                    json.dump(records, f, indent=2, default=str)
                print(f"      Saved failed records to {failed_file}")
            
            time.sleep(0.5)  # Rate limiting
        
        migration_summary[table_name] = {
            'total': len(rows),
            'successful': successful,
            'failed': failed
        }
        
        print(f"\n   📊 {table_name} summary: {successful}/{len(rows)} migrated")
    
    # Verify counts
    print("\n" + "="*60)
    print("📊 VERIFYING MIGRATION")
    print("="*60)
    
    for table_name in tables:
        # SQLite count
        sqlite_cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        sqlite_count = sqlite_cursor.fetchone()[0]
        
        # Supabase count
        try:
            result = supabase.table(table_name).select('*', count='exact').execute()
            supabase_count = result.count if hasattr(result, 'count') else len(result.data)
            
            print(f"\n📋 {table_name}:")
            print(f"   SQLite:   {sqlite_count} records")
            print(f"   Supabase: {supabase_count} records")
            
            if sqlite_count == supabase_count:
                print(f"   ✅ MATCH!")
            else:
                print(f"   ❌ MISMATCH! Difference: {sqlite_count - supabase_count}")
                
        except Exception as e:
            print(f"   ❌ Could not verify {table_name}: {e}")
    
    sqlite_conn.close()
    
    print("\n" + "="*60)
    print("✅ MIGRATION COMPLETE!")
    print("="*60)
    print("\n📈 Summary:")
    for table, stats in migration_summary.items():
        if isinstance(stats, dict):
            print(f"   {table}: {stats['successful']}/{stats['total']} migrated")
        else:
            print(f"   {table}: {stats} records (no data)")
    
    # Save summary
    with open('migration_summary.json', 'w', encoding='utf-8') as f:
        json.dump(migration_summary, f, indent=2, default=str)

if __name__ == "__main__":
    print("\n⚠️  WARNING: This will migrate ALL data to Supabase!")
    print("Make sure you have a backup before proceeding.")
    print("\nChecklist:")
    print("✓ Run backup script first")
    print("✓ Supabase tables created")
    print("✓ .env file with credentials")
    
    response = input("\nReady to migrate? (yes/no): ")
    if response.lower() == 'yes':
        migrate_data()
    else:
        print("Migration cancelled.")