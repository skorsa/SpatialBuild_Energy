# backup_db.py
import sqlite3
import json
import csv
from datetime import datetime
import os
import base64

def serialize_value(value):
    """Convert values to JSON-serializable format"""
    if value is None:
        return None
    elif isinstance(value, bytes):
        # Convert bytes to base64 string
        return {
            '__bytes__': True,
            'data': base64.b64encode(value).decode('ascii')
        }
    elif isinstance(value, (str, int, float, bool)):
        return value
    else:
        # Convert anything else to string
        return str(value)

def deserialize_value(value):
    """Convert back from serialized format"""
    if isinstance(value, dict) and value.get('__bytes__'):
        return base64.b64decode(value['data'])
    return value

def backup_database():
    print("=" * 50)
    print("🔐 DATABASE BACKUP UTILITY")
    print("=" * 50)
    
    # Check if database exists
    if not os.path.exists('my_database.db'):
        print("❌ Error: my_database.db not found in current directory!")
        print(f"Current directory: {os.getcwd()}")
        return
    
    # Connect to your SQLite database
    print("\n📂 Connecting to database...")
    conn = sqlite3.connect('my_database.db')
    # Important: Set connection to return bytes instead of strings for BLOB fields
    conn.text_factory = bytes
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    if not tables:
        print("❌ No tables found in database!")
        return
    
    print(f"✅ Found {len(tables)} table(s): {', '.join([t[0].decode('utf-8') if isinstance(t[0], bytes) else t[0] for t in tables])}")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = f"backup_{timestamp}"
    os.makedirs(backup_dir, exist_ok=True)
    
    print(f"\n📁 Creating backup in folder: {backup_dir}/")
    
    for table in tables:
        table_name_bytes = table[0]
        table_name = table_name_bytes.decode('utf-8') if isinstance(table_name_bytes, bytes) else table_name_bytes
        print(f"\n   Backing up table: {table_name}...")
        
        # Get table schema
        cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}';")
        schema_result = cursor.fetchone()
        schema = schema_result[0].decode('utf-8') if schema_result and schema_result[0] else f"CREATE TABLE {table_name} (unknown)"
        
        # Get all data
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        
        # Get column names
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns_info = cursor.fetchall()
        columns = [col[1].decode('utf-8') if isinstance(col[1], bytes) else col[1] for col in columns_info]
        
        print(f"      - {len(rows)} records, {len(columns)} columns")
        
        # Save as JSON with binary handling
        data = []
        for row in rows:
            record = {}
            for j, col in enumerate(columns):
                # Handle None values
                value = row[j] if j < len(row) else None
                record[col] = serialize_value(value)
            data.append(record)
        
        json_file = f'{backup_dir}/{table_name}_{timestamp}.json'
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump({
                'schema': schema,
                'data': data,
                'columns': columns,
                'record_count': len(rows)
            }, f, indent=2, ensure_ascii=False)
        print(f"      ✅ JSON saved: {json_file}")
        
        # Save as CSV (skip binary fields for CSV)
        csv_file = f'{backup_dir}/{table_name}_{timestamp}.csv'
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            for row in rows:
                # Convert any non-string to string for CSV
                cleaned_row = []
                for cell in row:
                    if cell is None:
                        cleaned_row.append('')
                    elif isinstance(cell, bytes):
                        # For CSV, just indicate it's binary data
                        cleaned_row.append('[BINARY DATA]')
                    else:
                        cleaned_row.append(str(cell))
                writer.writerow(cleaned_row)
        print(f"      ✅ CSV saved: {csv_file}")
    
    # Save a manifest
    manifest_file = f'{backup_dir}/manifest_{timestamp}.txt'
    with open(manifest_file, 'w', encoding='utf-8') as f:
        f.write(f"BACKUP MANIFEST\n")
        f.write(f"=" * 50 + "\n")
        f.write(f"Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Database: my_database.db\n")
        f.write(f"Backup folder: {backup_dir}\n\n")
        
        f.write("TABLE SUMMARY:\n")
        for table in tables:
            table_name_bytes = table[0]
            table_name = table_name_bytes.decode('utf-8') if isinstance(table_name_bytes, bytes) else table_name_bytes
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            f.write(f"  - {table_name}: {count} records\n")
    
    # Also create a special backup just for the users table with passwords as hex
    try:
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()
        if users:
            users_backup = f'{backup_dir}/users_password_backup_{timestamp}.txt'
            with open(users_backup, 'w') as f:
                f.write("USERNAME,PASSWORD_HEX\n")
                for user in users:
                    username = user[1].decode('utf-8') if isinstance(user[1], bytes) else user[1]
                    password_bytes = user[2] if isinstance(user[2], bytes) else user[2].encode('utf-8')
                    f.write(f"{username},{password_bytes.hex()}\n")
            print(f"\n   ✅ Password backup saved: {users_backup}")
    except:
        print("\n   ⚠️  No users table or couldn't backup passwords")
    
    conn.close()
    
    print("\n" + "=" * 50)
    print("✅ BACKUP COMPLETE!")
    print("=" * 50)
    print(f"\n📦 Backup saved to: {backup_dir}/")
    print("\nFiles created:")
    for file in os.listdir(backup_dir):
        print(f"   - {file}")
    
    return backup_dir

if __name__ == "__main__":
    print("\nThis will create a complete backup of your database.")
    response = input("Proceed with backup? (yes/no): ")
    if response.lower() == 'yes':
        backup_dir = backup_database()
        print(f"\n🎉 Backup successful! Keep this folder safe.")
        print(f"   Location: {backup_dir}/")
    else:
        print("Backup cancelled.")