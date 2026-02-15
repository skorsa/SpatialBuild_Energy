# backup_db.py
import sqlite3
import json
import csv
from datetime import datetime
import os

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
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    if not tables:
        print("❌ No tables found in database!")
        return
    
    print(f"✅ Found {len(tables)} table(s): {', '.join([t[0] for t in tables])}")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = f"backup_{timestamp}"
    os.makedirs(backup_dir, exist_ok=True)
    
    print(f"\n📁 Creating backup in folder: {backup_dir}/")
    
    for table in tables:
        table_name = table[0]
        print(f"\n   Backing up table: {table_name}...")
        
        # Get table schema
        cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}';")
        schema_result = cursor.fetchone()
        schema = schema_result[0] if schema_result else f"CREATE TABLE {table_name} (unknown)"
        
        # Get all data
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        
        # Get column names
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [col[1] for col in cursor.fetchall()]
        
        print(f"      - {len(rows)} records, {len(columns)} columns")
        
        # Save as JSON
        data = []
        for row in rows:
            record = {}
            for j, col in enumerate(columns):
                # Handle None values
                value = row[j] if j < len(row) else None
                record[col] = value
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
        
        # Save as CSV for easy viewing
        csv_file = f'{backup_dir}/{table_name}_{timestamp}.csv'
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            for row in rows:
                # Convert any None to empty string
                cleaned_row = ['' if cell is None else cell for cell in row]
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
            table_name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            f.write(f"  - {table_name}: {count} records\n")
    
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
    else:
        print("Backup cancelled.")