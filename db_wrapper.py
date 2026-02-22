# db_wrapper.py
import streamlit as st
from supabase import create_client
import sqlite3
import os
import re
from functools import lru_cache
import time
import bcrypt
from datetime import datetime

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
            self.conn.row_factory = sqlite3.Row
    
    # ============= ENERGY DATA METHODS =============
    
    def get_energy_data(self, filters=None, limit=1000):
        """Get energy_data records with optional filters and auto token refresh."""
        if self.use_supabase:
            try:
                # First attempt - execute the query
                return self._execute_energy_query(filters, limit)
            except Exception as e:
                # Check if it's a JWT expiration error
                error_str = str(e).lower()
                if 'jwt expired' in error_str or 'pgrst303' in error_str:
                    try:
                        # Refresh token and retry once
                        self.supabase.auth.refresh_session()
                        return self._execute_energy_query(filters, limit)
                    except Exception as refresh_error:
                        # If refresh fails, raise the original error
                        raise e
                else:
                    # Not a token error, re-raise
                    raise e
        else:
            # SQLite mode - unchanged
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

    def _execute_energy_query(self, filters=None, limit=1000):
        """Internal method to execute the actual Supabase query for energy_data."""
        query = self.supabase.table('energy_data').select('*')
        
        if filters:
            for key, value in filters.items():
                if value is not None and value != "":
                    query = query.eq(key, value)
        
        if limit:
            query = query.limit(limit)
        
        result = query.execute()
        return result.data
        
    def search_energy_data(self, search_term, fields=None, limit=100):
        """Search across multiple fields including ID"""
        print(f"🔍 search_energy_data called with: '{search_term}'")
        search_term = search_term.replace(',', ' ')
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
    
    # ============= AUTH METHODS =============
    
    def sign_up(self, email, password, username):
        """Sign up a new user with email verification"""
        if self.use_supabase:
            try:
                # Sign up with Supabase Auth
                auth_response = self.supabase.auth.sign_up({
                    "email": email,
                    "password": password,
                    "options": {
                        "data": {
                            "username": username,
                            "role": "user"
                        }
                    }
                })
                
                # Also store in your users table for existing app compatibility
                if auth_response.user:
                    user_data = {
                        'username': username,
                        'email': email,
                        'role': 'user',
                        'email_confirmed': False,
                        'auth_id': auth_response.user.id
                    }
                    
                    # Insert without password field
                    self.supabase.table('users').insert(user_data).execute()
                            
                    return {"success": True, "user": auth_response.user}
            except Exception as e:
                error_str = str(e)
                # Return more specific error messages
                if 'already registered' in error_str.lower():
                    return {"success": False, "error": "Email already registered"}
                elif 'duplicate key' in error_str.lower() and 'email' in error_str.lower():
                    return {"success": False, "error": "Email already registered"}
                elif 'rate limit' in error_str.lower():
                    return {"success": False, "error": "Rate limit exceeded. Please try again later."}
                else:
                    return {"success": False, "error": error_str}
        else:
            # SQLite fallback (no email verification)
            cursor = self.conn.cursor()
            try:
                hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
                cursor.execute(
                    "INSERT INTO users (username, password, role, email, email_confirmed) VALUES (?, ?, ?, ?, ?)",
                    (username, hashed, 'user', email, 1)
                )
                self.conn.commit()
                return {"success": True, "user": {"id": cursor.lastrowid, "username": username}}
            except Exception as e:
                return {"success": False, "error": str(e)}

    def sign_in(self, login_id, password):
        """
        Sign in with email OR username and password.
        Returns a dict with 'success' bool, 'user' (auth user object or dict),
        and 'user_id' (integer from the users table) if successful.
        """
        if self.use_supabase:
            try:
                # Try as email first
                auth_response = self.supabase.auth.sign_in_with_password({
                    "email": login_id,
                    "password": password
                })

                # Get the Supabase Auth user object
                auth_user = auth_response.user
                user_email = auth_user.email
                username = auth_user.user_metadata.get('username', login_id.split('@')[0])

                # Check if user exists in your custom users table by auth_id
                existing = self.supabase.table('users').select('*').eq('auth_id', auth_user.id).execute()

                if existing.data:
                    # User already linked – get the integer id
                    user_record = existing.data[0]
                    user_id = user_record['id']
                else:
                    # No record yet – try to find by username (legacy) or create new
                    existing_by_username = self.supabase.table('users').select('*').eq('username', login_id).execute()
                    if existing_by_username.data:
                        # Legacy user: update with auth_id and email
                        user_record = existing_by_username.data[0]
                        user_id = user_record['id']
                        self.supabase.table('users').update({
                            'auth_id': auth_user.id,
                            'email': user_email
                        }).eq('id', user_id).execute()
                    else:
                        # Brand new user (should have been created at signup, but just in case)
                        user_data = {
                            'username': username,
                            'email': user_email,
                            'role': 'user',
                            'email_confirmed': True,
                            'auth_id': auth_user.id
                        }
                        insert_result = self.supabase.table('users').insert(user_data).execute()
                        user_id = insert_result.data[0]['id']

                return {
                    "success": True,
                    "user": auth_user,
                    "user_id": user_id
                }

            except Exception as e:
                # If email login fails, maybe it's a username
                error_str = str(e).lower()
                if 'invalid login credentials' in error_str:
                    # Try to find user by username in your table
                    user_record = self.supabase.table('users').select('*').eq('username', login_id).execute()
                    if user_record.data and user_record.data[0].get('email'):
                        # Retry with the email
                        try:
                            auth_response = self.supabase.auth.sign_in_with_password({
                                "email": user_record.data[0]['email'],
                                "password": password
                            })
                            auth_user = auth_response.user
                            # Now get the user_id (should exist)
                            existing = self.supabase.table('users').select('id').eq('auth_id', auth_user.id).execute()
                            if existing.data:
                                user_id = existing.data[0]['id']
                            else:
                                # Fallback – shouldn't happen
                                user_id = user_record.data[0]['id']
                            return {
                                "success": True,
                                "user": auth_user,
                                "user_id": user_id
                            }
                        except Exception as inner_e:
                            return {"success": False, "error": str(inner_e)}
                return {"success": False, "error": str(e)}

        else:
            # SQLite fallback – check both username and email
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ? OR email = ?", (login_id, login_id))
            user = cursor.fetchone()
            if user and bcrypt.checkpw(password.encode('utf-8'), user[2]):  # password is at index 2
                return {
                    "success": True,
                    "user": {
                        "id": user[0],
                        "username": user[1],
                        "role": user[3],
                        "email": user[4] if len(user) > 4 else None
                    },
                    "user_id": user[0]  # integer id
                }
            return {"success": False, "error": "Invalid credentials"}
    
    def sign_out(self):
        """Sign out current user"""
        if self.use_supabase:
            self.supabase.auth.sign_out()
    
    def reset_password(self, email):
        """Send password reset email"""
        if self.use_supabase:
            try:
                self.supabase.auth.reset_password_for_email(email)
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}
        else:
            # SQLite fallback - can't really reset password
            return {"success": False, "error": "Password reset not available in SQLite mode"}
    
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

    def save_analysis(self, user_id, analysis_type, determinant, top_energy, bottom_energy, html, top_sorted=None, bottom_sorted=None, top_height=0, bottom_height=0):
        """Save a user's analysis to the database"""
        data = {
            'user_id': user_id,
            'analysis_type': analysis_type,
            'determinant': determinant,
            'top_energy': top_energy,
            'bottom_energy': bottom_energy,
            'html': html,
            'top_sorted': top_sorted,
            'bottom_sorted': bottom_sorted,
            'top_height': top_height,
            'bottom_height': bottom_height,
            'created_at': datetime.now().isoformat()
        }
        return self.insert_record('user_saved_analyses', data)

    def get_user_analyses(self, user_id):
        """Get all analyses saved by a user"""
        if self.use_supabase:
            response = self.supabase.table('user_saved_analyses') \
                .select('*') \
                .eq('user_id', user_id) \
                .order('created_at', desc=True) \
                .execute()
            return response.data
        else:
            # SQLite version
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM user_saved_analyses WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,)
            )
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]

    def delete_analysis(self, analysis_id):
        """Delete a specific saved analysis."""
        if self.use_supabase:
            self.supabase.table('user_saved_analyses') \
                .delete() \
                .eq('id', analysis_id) \
                .execute()
        else:
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM user_saved_analyses WHERE id = ?', (analysis_id,))
            self.conn.commit()


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