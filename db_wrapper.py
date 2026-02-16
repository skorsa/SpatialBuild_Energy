# db_wrapper.py
import streamlit as st
from supabase import create_client
import sqlite3
import os
import re
from functools import lru_cache
import time

class DatabaseWrapper:
    def __init__(self):
        # Check if we're in production (Streamlit Cloud) or have Supabase secrets
        self.use_supabase = False
        
        # Check for Streamlit secrets first
        try:
            if 'supabase_url' in st.secrets and 'supabase_key' in st.secrets:
                self.use_supabase = True
                self.supabase_url = st.secrets["supabase_url"]
                self.supabase_key = st.secrets["supabase_key"]
        except:
            pass
        
        # Check environment variables as fallback
        if not self.use_supabase:
            if os.getenv('SUPABASE_URL') and os.getenv('SUPABASE_KEY'):
                self.use_supabase = True
                self.supabase_url = os.getenv('SUPABASE_URL')
                self.supabase_key = os.getenv('SUPABASE_KEY')
        
        if self.use_supabase:
            print("🔌 Using Supabase database")
            self.supabase = create_client(self.supabase_url, self.supabase_key)
        else:
            print("📂 Using local SQLite database")
            self.conn = sqlite3.connect('my_database.db', check_same_thread=False)
            self.conn.row_factory = sqlite3.Row  # This lets us access columns by name
    
    # ============= ENERGY DATA METHODS =============
    
    def get_energy_data(self, filters=None, limit=1000):
        """Get energy_data records with optional filters"""
        if self.use_supabase:
            query = self.supabase.table('energy_data').select('*')
            
            if filters:
                for key, value in filters.items():
                    if value is not None and value != "":
                        query = query.eq(key, value)
            
            if limit:
                query = query.limit(limit)
            
            result = query.execute()
            return result.data
        else:
            cursor = self.conn.cursor()
            sql = "SELECT * FROM energy_data"
            params = []
            
            if filters:
                where_clauses = []
                for key, value in filters.items():
                    if value is not None and value != "":
                        where_clauses.append(f"{key} = ?")
                        params.append(value)
                if where_clauses:
                    sql += " WHERE " + " AND ".join(where_clauses)
            
            if limit:
                sql += f" LIMIT {limit}"
            
            cursor.execute(sql, params)
            return cursor.fetchall()
    
    def search_energy_data(self, search_term, fields=None, limit=100):
        """Search across multiple fields including ID"""
        print(f"🔍 search_energy_data called with: '{search_term}'")
        
        if not search_term:
            return []
        
        if self.use_supabase:
            # Default fields to search
            if fields is None:
                fields = ['paragraph', 'criteria', 'energy_method', 'location', 'climate', 'building_use', 'approach']
            
            # Start with a base query
            query = self.supabase.table('energy_data').select('*')
            
            # Build filter conditions
            if search_term.isdigit():
                # If it's a number, search by ID OR text fields
                id_num = int(search_term)
                
                # Build OR conditions for text fields
                or_conditions = []
                for field in fields:
                    or_conditions.append(f"{field}.ilike.%{search_term}%")
                
                # Add ID condition
                id_condition = f"id.eq.{id_num}"
                
                # Combine: (id = X) OR (text fields LIKE %X%)
                all_conditions = [id_condition] + or_conditions
                query = query.or_(",".join(all_conditions))
            else:
                # Just search text fields
                or_conditions = []
                for field in fields:
                    or_conditions.append(f"{field}.ilike.%{search_term}%")
                query = query.or_(",".join(or_conditions))
            
            # Filter out rejected records
            query = query.not_.eq('status', 'rejected')
            
            # Add limit and order
            query = query.order('id', desc=True).limit(limit)
            
            # Execute
            result = query.execute()
            return result.data
        
        else:
            # SQLite mode
            cursor = self.conn.cursor()
            search_pattern = f'%{search_term}%'
            
            if fields is None:
                fields = ['paragraph', 'criteria', 'energy_method', 'location', 'climate', 'building_use', 'approach']
            
            # Include ID in SQLite search
            id_condition = "CAST(id AS TEXT) LIKE ?"
            field_conditions = [f"{field} LIKE ?" for field in fields]
            all_conditions = [id_condition] + field_conditions
            params = [search_pattern] * (len(fields) + 1)
            
            sql = f"""
                SELECT * FROM energy_data 
                WHERE ({' OR '.join(all_conditions)})
                AND status != 'rejected'
                ORDER BY id DESC
                LIMIT {limit}
            """
            
            cursor.execute(sql, params)
            return cursor.fetchall()
    
    def get_distinct_values(self, column, filters=None):
        """Get distinct values for a column with optional filters"""
        if self.use_supabase:
            query = self.supabase.table('energy_data').select(column)
            
            if filters:
                for key, value in filters.items():
                    if value:
                        query = query.eq(key, value)
            
            # Add basic filters
            query = query.not_.is_(column, 'null')
            query = query.neq(column, '')
            query = query.neq(column, 'Awaiting data')
            query = query.not_.eq('status', 'rejected')
            
            result = query.execute()
            
            # Extract unique values
            values = set()
            for item in result.data:
                val = item.get(column)
                if val and str(val).strip():
                    values.add(str(val).strip())
            
            return sorted(list(values))
        else:
            cursor = self.conn.cursor()
            sql = f"SELECT DISTINCT {column} FROM energy_data WHERE {column} IS NOT NULL AND {column} != '' AND {column} != 'Awaiting data' AND status != 'rejected'"
            params = []
            
            if filters:
                where_clauses = []
                for key, value in filters.items():
                    if value:
                        where_clauses.append(f"{key} = ?")
                        params.append(value)
                if where_clauses:
                    sql += " AND " + " AND ".join(where_clauses)
            
            sql += f" ORDER BY {column}"
            
            cursor.execute(sql, params)
            return [row[0] for row in cursor.fetchall() if row[0]]
    
    def get_counts_with_filters(self, group_by_column, filters=None):
        """Get counts grouped by a column with filters"""
        if self.use_supabase:
            # This is more complex in Supabase - we'll fetch and count locally for now
            query = self.supabase.table('energy_data').select('*')
            
            if filters:
                for key, value in filters.items():
                    if value:
                        query = query.eq(key, value)
            
            query = query.not_.eq('status', 'rejected')
            result = query.execute()
            
            # Count locally
            counts = {}
            for item in result.data:
                val = item.get(group_by_column)
                if val and str(val).strip():
                    key = str(val).strip()
                    counts[key] = counts.get(key, 0) + 1
            
            return counts
        else:
            cursor = self.conn.cursor()
            sql = f"SELECT {group_by_column}, COUNT(*) as count FROM energy_data WHERE {group_by_column} IS NOT NULL AND {group_by_column} != '' AND status != 'rejected'"
            params = []
            
            if filters:
                where_clauses = []
                for key, value in filters.items():
                    if value:
                        where_clauses.append(f"{key} = ?")
                        params.append(value)
                if where_clauses:
                    sql += " AND " + " AND ".join(where_clauses)
            
            sql += f" GROUP BY {group_by_column} ORDER BY {group_by_column}"
            
            cursor.execute(sql, params)
            return {row[0]: row[1] for row in cursor.fetchall()}
    
    # ============= USER METHODS =============
    
    def get_user(self, username):
        """Get user by username"""
        if self.use_supabase:
            result = self.supabase.table('users').select('*').eq('username', username).execute()
            return result.data[0] if result.data else None
        else:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
            row = cursor.fetchone()
            if row:
                # Convert to dict for consistent interface
                return {
                    'id': row[0],
                    'username': row[1],
                    'password': row[2],
                    'role': row[3],
                    'created_at': row[4] if len(row) > 4 else None
                }
            return None
    
    def create_user(self, username, hashed_password, role='user'):
        """Create a new user"""
        if self.use_supabase:
            data = {
                'username': username,
                'password': hashed_password.decode('utf-8') if isinstance(hashed_password, bytes) else hashed_password,
                'role': role
            }
            result = self.supabase.table('users').insert(data).execute()
            return result.data
        else:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                (username, hashed_password, role)
            )
            self.conn.commit()
            return cursor.lastrowid

    # ============= INSERT/UPDATE METHODS =============
    def get_next_id(self, table='energy_data'):
        """Get the next available ID by finding the max current ID and adding 1"""
        if self.use_supabase:
            try:
                # Get all IDs, sorted descending, limit 1
                result = self.supabase.table(table).select('id').order('id', desc=True).limit(1).execute()
                if result.data and len(result.data) > 0:
                    next_id = result.data[0]['id'] + 1
                else:
                    next_id = 1  # Start at 1 if no records
                print(f"Next ID for {table}: {next_id}")
                return next_id
            except Exception as e:
                print(f"Error getting next ID: {e}")
                return 1  # Default to 1 on error
        else:
            cursor = self.conn.cursor()
            cursor.execute(f"SELECT MAX(id) FROM {table}")
            max_id = cursor.fetchone()[0]
            return (max_id or 0) + 1

    def insert_record(self, table, data):
        """Insert a new record"""
        if self.use_supabase:
            # Make a copy to avoid modifying the original
            insert_data = data.copy()
            
            # Remove id if it exists (we'll set our own)
            if 'id' in insert_data:
                print(f"⚠️ Removing existing id field: {insert_data['id']}")
                del insert_data['id']
            
            # Get the next available ID
            next_id = self.get_next_id(table)
            insert_data['id'] = next_id
            
            print(f"📦 Inserting with ID: {next_id}")
            print(f"📦 Data keys: {list(insert_data.keys())}")
            
            try:
                result = self.supabase.table(table).insert(insert_data).execute()
                print(f"✅ Insert successful with ID: {next_id}")
                return result.data
            except Exception as e:
                print(f"❌ Insert error: {e}")
                # If there's a duplicate key error, try one more time with a new ID
                if 'duplicate key' in str(e).lower():
                    next_id = self.get_next_id(table)  # Get fresh ID
                    insert_data['id'] = next_id
                    print(f"🔄 Retrying with new ID: {next_id}")
                    result = self.supabase.table(table).insert(insert_data).execute()
                    return result.data
                else:
                    raise e
        else:
            # SQLite version
            cursor = self.conn.cursor()
            insert_data = data.copy()
            if 'id' in insert_data:
                del insert_data['id']
                
            columns = ', '.join(insert_data.keys())
            placeholders = ', '.join(['?' for _ in insert_data])
            values = list(insert_data.values())
            
            sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
            cursor.execute(sql, values)
            self.conn.commit()
            return cursor.lastrowid

    def update_record(self, table, record_id, data):
        """Update an existing record"""
        if self.use_supabase:
            result = self.supabase.table(table).update(data).eq('id', record_id).execute()
            return result.data
        else:
            cursor = self.conn.cursor()
            set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
            values = list(data.values()) + [record_id]
            
            sql = f"UPDATE {table} SET {set_clause} WHERE id = ?"
            cursor.execute(sql, values)
            self.conn.commit()
            return cursor.rowcount

    def get_non_rejected_records(self, limit=5000):
        """Get all records that are not rejected (includes NULL, approved, pending)"""
        if self.use_supabase:
            # In Supabase, we need to use OR condition for status != 'rejected' OR status IS NULL
            query = self.supabase.table('energy_data').select('*')
            query = query.or_('status.neq.rejected,status.is.null')
            if limit:
                query = query.limit(limit)
            result = query.execute()
            return result.data
        else:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT * FROM energy_data 
                WHERE status != 'rejected' OR status IS NULL
                LIMIT ?
            """, (limit,))
            return cursor.fetchall()

    def update_record(self, table, record_id, data):
        """Update an existing record"""
        if self.use_supabase:
            result = self.supabase.table(table).update(data).eq('id', record_id).execute()
            return result.data
        else:
            cursor = self.conn.cursor()
            set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
            values = list(data.values()) + [record_id]
            
            sql = f"UPDATE {table} SET {set_clause} WHERE id = ?"
            cursor.execute(sql, values)
            self.conn.commit()
            return cursor.rowcount

    def get_non_rejected_records(self, limit=5000):
        """Get all records that are not rejected (includes NULL, approved, pending)"""
        if self.use_supabase:
            # In Supabase, we need to use OR condition for status != 'rejected' OR status IS NULL
            query = self.supabase.table('energy_data').select('*')
            query = query.or_('status.neq.rejected,status.is.null')
            if limit:
                query = query.limit(limit)
            result = query.execute()
            return result.data
        else:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT * FROM energy_data 
                WHERE status != 'rejected' OR status IS NULL
                LIMIT ?
            """, (limit,))
            return cursor.fetchall()
    
    def update_record(self, table, record_id, data):
        """Update an existing record"""
        if self.use_supabase:
            result = self.supabase.table(table).update(data).eq('id', record_id).execute()
            return result.data
        else:
            cursor = self.conn.cursor()
            set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
            values = list(data.values()) + [record_id]
            
            sql = f"UPDATE {table} SET {set_clause} WHERE id = ?"
            cursor.execute(sql, values)
            self.conn.commit()
            return cursor.rowcount
    
    def get_non_rejected_records(self, limit=5000):
        #"""Get all records that are not rejected (includes NULL, approved, pending)"""
        if self.use_supabase:
            # In Supabase, we need to use OR condition for status != 'rejected' OR status IS NULL
            query = self.supabase.table('energy_data').select('*')
            query = query.or_('status.neq.rejected,status.is.null')
            if limit:
                query = query.limit(limit)
            result = query.execute()
            return result.data
        else:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT * FROM energy_data 
                WHERE status != 'rejected' OR status IS NULL
                LIMIT ?
            """, (limit,))
            return cursor.fetchall()

    # ============= HELPER METHODS =============
    
    @lru_cache(maxsize=128)
    def get_cached_distinct(self, column, filter_hash=""):
        """Cached version of get_distinct_values for performance"""
        return self.get_distinct_values(column)
    
    def close(self):
        if not self.use_supabase:
            self.conn.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()