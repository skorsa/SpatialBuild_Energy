import re
import sqlite3
import pandas as pd
import streamlit as st
import streamlit_authenticator as stauth
import streamlit_authenticator as Hasher
from datetime import datetime
import os
from dotenv import load_dotenv
import bcrypt
import time
from contextlib import contextmanager
from typing import List, Dict, Tuple


load_dotenv()

db_file = 'my_database.db'
conn = sqlite3.connect(db_file)

# Initialize session state variables
if "current_tab" not in st.session_state:
    st.session_state.current_tab = "tab0"  # Default tab
if 'login_status' not in st.session_state:
    st.session_state.login_status = None
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = None  # Make sure this line exists
if 'selected_criteria' not in st.session_state:
    st.session_state.selected_criteria = None
if 'selected_method' not in st.session_state:
    st.session_state.selected_method = None
if 'show_new_record_form' not in st.session_state:
    st.session_state.show_new_record_form = False
if "user_role" not in st.session_state:
    st.session_state.user_role = None

def check_database_health():
    """Check if the database is healthy and not corrupted"""
    try:
            global conn
            cursor = conn.cursor()
            
            # Test basic operations
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            
            # Check if our main table exists-
            cursor.execute("SELECT COUNT(*) FROM energy_data")
            record_count = cursor.fetchone()[0]
            
            # Test a more complex query
            cursor.execute("PRAGMA integrity_check")
            integrity_check = cursor.fetchone()[0]
            
            st.sidebar.success(f"✅ Database healthy: {len(tables)} tables, {record_count} records")
            st.sidebar.info(f"Integrity check: {integrity_check}")
            
            return True
            
    except sqlite3.DatabaseError as e:
        st.sidebar.error(f"❌ Database corrupted: {e}")
        return False
    except Exception as e:
        st.sidebar.error(f"❌ Database error: {e}")
        return False


def add_scale_climate_columns():
    global conn
    cursor = conn.cursor()
    
    # Log start of execution
    print("🔧 add_scale_climate_columns() function called - checking database schema...")
    st.sidebar.info("🔧 Checking database schema for scale/climate columns...")
    
    # Add scale column if it doesn't exist
    try:
        cursor.execute("ALTER TABLE energy_data ADD COLUMN scale TEXT DEFAULT 'Awaiting data'")
        print("✅ Added 'scale' column to energy_data table")
        st.sidebar.success("✅ Added 'scale' column to energy_data table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("ℹ️ 'scale' column already exists in energy_data table")
            st.sidebar.info("ℹ️ 'scale' column already exists")
        else:
            print(f"⚠️ Unexpected error with scale column: {e}")
            st.sidebar.warning(f"⚠️ Error with scale column: {e}")
    
    # Add climate column if it doesn't exist
    try:
        cursor.execute("ALTER TABLE energy_data ADD COLUMN climate TEXT DEFAULT 'Awaiting data'")
        print("✅ Added 'climate' column to energy_data table")
        st.sidebar.success("✅ Added 'climate' column to energy_data table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("ℹ️ 'climate' column already exists in energy_data table")
            st.sidebar.info("ℹ️ 'climate' column already exists")
        else:
            print(f"⚠️ Unexpected error with climate column: {e}")
            st.sidebar.warning(f"⚠️ Error with climate column: {e}")
    
    conn.commit()
    
    # Verify the current schema
    cursor.execute("PRAGMA table_info(energy_data)")
    columns = cursor.fetchall()
    print("📋 Current energy_data table schema:")
    st.sidebar.text("📋 Current table columns:")
    for col in columns:
        print(f"   - {col[1]} ({col[2]})")
        st.sidebar.text(f"   - {col[1]} ({col[2]})")

    print("🔧 Database schema check completed")
    st.sidebar.success("🔧 Database schema check completed")

# Run this function once to add the new columns
# add_scale_climate_columns() DONE!

def query_approved_criteria(conn):
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT criteria FROM energy_data WHERE status NOT IN ('rejected', 'pending')  ORDER BY criteria ASC")
        return cursor.fetchall()
    
    
def query_approved_energy_outputs(conn):
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT energy_method FROM energy_data WHERE status NOT IN ('rejected', 'pending') ORDER BY energy_method ASC")
        return cursor.fetchall()

def contribute():
        # Check if user is logged in
    if not st.session_state.get('logged_in') or not st.session_state.get('current_user'):
        st.warning("Please log in to contribute to the database.")
        return  # Exit the function early
    # Fetch existing determinants and energy outputs from approved records
    approved_determinants = query_approved_criteria(conn)
    criteria_list = ["Select a Determinant", "Add new Determinant"] + [f"{row[0]}" for row in approved_determinants]
    approved_energy_outputs = query_approved_energy_outputs(conn)
    energy_method_list = ["Select an Energy Output", "Add new Energy Output"] + [f"{row[0]}" for row in approved_energy_outputs]

    # Initialize session state
    if "selected_determinant_choice" not in st.session_state:
        st.session_state.selected_determinant_choice = "Select a Determinant"
    if "selected_energy_output_choice" not in st.session_state:
        st.session_state.selected_energy_output_choice = "Select an Energy Output"
    if "selected_selected_direction" not in st.session_state:
        st.session_state.selected_selected_direction = None
    if "new_determinant" not in st.session_state:
        st.session_state.new_determinant = ""
    if "new_energy_output" not in st.session_state:
        st.session_state.new_energy_output = ""
    if "reset_form" not in st.session_state:
        st.session_state.reset_form = False

    # Reset session state if reset_form flag is True
    if st.session_state.reset_form:
        st.session_state.selected_determinant_choice = "Select a Determinant"
        st.session_state.selected_energy_output_choice = "Select an Energy Output"
        st.session_state.selected_selected_direction = None
        st.session_state.new_determinant = ""
        st.session_state.new_energy_output = ""
        st.session_state.reset_form = False

    # Dropdown for Determinants
    selected_determinant_choice = st.selectbox(
        "Determinant",
        criteria_list,
        key="selected_determinant_choice"
    )

    # Handle adding a new determinant
    new_determinant = ""
    if selected_determinant_choice == "Add new Determinant":
        new_determinant = st.text_input("Enter New Determinant", key="new_determinant")

    # Dropdown for Energy Output
    new_energy_output = ""
    if selected_determinant_choice != "Select a Determinant":
        selected_energy_output_choice = st.selectbox(
            "Energy Output",
            energy_method_list,
            key="selected_energy_output_choice"
        )

        # Handle adding a new energy output
        if selected_energy_output_choice == "Add new Energy Output":
            new_energy_output = st.text_input("Enter New Energy Output", key="new_energy_output")
    else:
        selected_energy_output_choice = "Select an Energy Output"

    # Radio buttons for direction
    if (
        st.session_state.selected_energy_output_choice != "Select an Energy Output"
        and st.session_state.selected_determinant_choice != "Select a Determinant"
    ):
        st.radio(
            "Please select the direction of the relationship",
            ["Increase", "Decrease"],
            key="selected_selected_direction"
        )

    # Display text area and save button if all fields are selected
    if st.session_state.selected_selected_direction:
        st.markdown(
            f"<p>Please add your findings which show that a {st.session_state.selected_selected_direction} "
            f"(or presence) in {new_determinant or st.session_state.selected_determinant_choice} leads to <i>{'higher' if st.session_state.selected_selected_direction == 'Increase' else 'lower'}</i> "
            f"{new_energy_output or st.session_state.selected_energy_output_choice}.</p>",
            unsafe_allow_html=True
        )

        # Add New Record Section
        new_paragraph = st.text_area(
            f"Add new record for {new_determinant or st.session_state.selected_determinant_choice} and {new_energy_output or st.session_state.selected_energy_output_choice} "
            f"({st.session_state.selected_selected_direction})",
            key="new_paragraph"
        )

        # In the save section, make sure you're using st.session_state.current_user:
        if st.button("Save", key="save_new_record"):
            # Save record only if text is provided
            if new_paragraph.strip():
                cursor = conn.cursor()

                # Save the record - FIX THE USER FIELD
                cursor.execute('''
                    INSERT INTO energy_data (criteria, energy_method, direction, paragraph, status, user, scale, climate)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    new_determinant or st.session_state.selected_determinant_choice,
                    new_energy_output or st.session_state.selected_energy_output_choice,
                    st.session_state.selected_selected_direction,
                    new_paragraph,
                    "pending",
                    st.session_state.current_user,  # FIXED: Use st.session_state.current_user
                    "Awaiting data",  # Default scale
                    "Awaiting data"   # Default climate
                ))
                conn.commit()

                # Set reset_form flag
                st.session_state.reset_form = True

                st.success("New record submitted successfully. Thank you for your contribution. Status: pending verification")

                # Allow time to read success message
                time.sleep(2)

                # Refresh the app to reflect the reset
                st.rerun()
            else:
                st.warning("Please ensure the record is not empty before saving.")


def import_location_climate_data_unique():
    global conn
    st.subheader("Import Location, Climate & Scale Data")
    
    # Add reset button section at the top
    col1, col2 = st.columns(2)
    
    with col1:
        st.warning("⚠️ **Reset Options**")
    with col2:
        if st.button("🗑️ Clear All, Climate and Scale Data", key="clear_location_data_btn", use_container_width=True):
            reset_location_climate_scale_data()
    
    st.markdown("---")
    
    # File upload with UNIQUE key
    uploaded_file = st.file_uploader("Upload Excel file with location/climate data", 
                                   type=["xlsx", "csv", "ods"],
                                   key="location_climate_import_unique")
    
    if uploaded_file is not None:
        try:
            # NEW: Enable matching feature
            use_matching = st.checkbox("🔍 Enable Automatic Study Matching", value=True, 
                                     help="Automatically match Excel studies with database records")
            
            if use_matching:
                # Store the uploaded file in session state so it's available for processing
                st.session_state.uploaded_excel_file = uploaded_file
                
                # Use the enhanced matching import
                matched, unmatched = admin_import_and_match_studies(uploaded_file)

                # Read the Excel file and store it in session state
                uploaded_file.seek(0)  # Reset file pointer
                excel_df = pd.read_excel(uploaded_file, sheet_name=0)
                st.session_state.current_excel_df = excel_df

                display_admin_matching_review(matched, unmatched, excel_df)

            else:
                # Use the original import logic
                df = pd.read_excel(uploaded_file, sheet_name=0)
                
                # Clean column names and data
                df.columns = [str(col).strip() for col in df.columns]
                
                # FLEXIBLE COLUMN MAPPING - Handle different column names
                column_mapping = {}
                
                # Map expected column names with flexibility
                possible_study_cols = ['Study', 'study', 'Title', 'title', 'Paper', 'paper']
                possible_location_cols = ['Location', 'location', 'Site', 'site', 'Region', 'region']
                possible_climate_cols = ['Climate', 'climate', 'Climate Zone', 'climate_zone']
                possible_scale_cols = ['Scale', 'scale', 'Scale. (Neighbourhood (rural, urban), Regional, National and State,)']
                
                
                # Find matching columns
                for col in df.columns:
                    col_clean = str(col).strip()
                    if any(study_col in col_clean for study_col in possible_study_cols):
                        column_mapping[col] = 'study'
                    elif any(loc_col in col_clean for loc_col in possible_location_cols):
                        column_mapping[col] = 'location'
                    elif any(climate_col in col_clean for climate_col in possible_climate_cols):
                        column_mapping[col] = 'climate'
                    elif any(scale_col in col_clean for scale_col in possible_scale_cols):
                        column_mapping[col] = 'scale'
                
                # Check if we found a study column
                if not any('study' in col.lower() for col in column_mapping.values()):
                    st.error("No study column found in the uploaded file. Please ensure your Excel file has a column for study names.")
                    st.write("Available columns:", list(df.columns))
                    return
                
                # Rename columns
                df = df.rename(columns=column_mapping)
                
                # Display preview
                st.write("**Preview of data to import:**")
                st.dataframe(df.head(10))
                
                # Show statistics
                st.write(f"**Total records in file:** {len(df)}")
                st.write(f"**Columns:** {list(df.columns)}")
                
                # Import button with unique key
                if st.button("Import Data to Database", type="primary", key="import_button_unique"):
                    import_progress = st.progress(0)
                    status_text = st.empty()
                    
                    # FIX: Use context manager instead of manual connection
                    
                    cursor = conn.cursor()
                    
                    updated_count = 0
                    not_found_studies = []
                    
                    for index, row in df.iterrows():
                        # Update progress
                        progress = (index + 1) / len(df)
                        import_progress.progress(progress)
                        status_text.text(f"Processing {index + 1}/{len(df)}: {row['study'][:50]}...")
                        
                        # Clean study name for matching (remove extra spaces, etc.)
                        study_name = str(row['study']).strip()
                        
                        # Try to find matching record in database
                        # First, try exact match
                        cursor.execute('''
                            SELECT id, paragraph FROM energy_data 
                            WHERE paragraph LIKE ? 
                            OR paragraph LIKE ?
                            LIMIT 1
                        ''', (f'%{study_name}%', f'%{study_name[:30]}%'))
                        
                        result = cursor.fetchone()
                        
                        if result:
                            record_id, paragraph = result
                            
                            # Update the record with location, climate, and scale data
                            cursor.execute('''
                                UPDATE energy_data 
                                SET location = ?, climate = ?, scale = ?
                                WHERE id = ?
                            ''', (
                                str(row.get('location', '')).strip(),
                                str(row.get('climate', '')).strip(),
                                str(row.get('scale', '')).strip(),
                                record_id
                            ))
                            
                            updated_count += 1
                        else:
                            not_found_studies.append(study_name)
                    
                        conn.commit()
                    
                    import_progress.empty()
                    status_text.empty()
                    
                    # Show results
                    st.success(f"✅ Import completed!")
                    st.write(f"**Records updated:** {updated_count}")
                    
                    if not_found_studies:
                        st.warning(f"**{len(not_found_studies)} studies not found in database:**")
                        with st.expander("Show unmatched studies"):
                            for study in not_found_studies[:20]:  # Show first 20
                                st.write(f"- {study}")
                            if len(not_found_studies) > 20:
                                st.write(f"... and {len(not_found_studies) - 20} more")
                    
                    # Refresh to show updated data
                    st.rerun()
                
        except Exception as e:
            st.error(f"Error reading Excel file: {str(e)}")
            st.write("Please check the file format and ensure it contains the correct sheet name.")

def reset_location_climate_scale_data():
    """Clear all climate, and scale data and reset to defaults"""
    global conn
    cursor = conn.cursor()
    try:
        # Clear ALL imported data and reset to default values
        cursor.execute('''
            UPDATE energy_data 
            SET climate = NULL,
                scale = 'Awaiting data'
        ''')
        
        conn.commit()
        st.success("✅ All imported data cleared and reset! (Climate, Scale)")
        
        # Show comprehensive statistics
        
        cursor.execute("SELECT COUNT(*) FROM energy_data WHERE climate IS NULL")
        climate_cleared_count = cursor.fetchone()[0]
               
        cursor.execute("SELECT COUNT(*) FROM energy_data WHERE scale = 'Awaiting data'")
        scale_reset_count = cursor.fetchone()[0]
        
        st.info(f"""
        **Reset Statistics:**
        - Records with climate cleared: {climate_cleared_count}
        - Records with scale reset: {scale_reset_count}
        """)
        
    except Exception as e:
        st.error(f"Error resetting climate and scale data: {str(e)}")

    # Refresh to show updated data
    time.sleep(2)
    st.rerun()

# Update the query functions to handle the new filters
def query_location_options(conn):
    """Get unique location values from the database"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT location FROM energy_data 
        WHERE location IS NOT NULL 
          AND location != '' 
        ORDER BY location ASC
    ''')
    locations = [row[0] for row in cursor.fetchall()]
    return [loc for loc in locations if loc and str(loc).strip()]

def query_koppen_climate_options(conn):
    """Get only Koppen climate categories with descriptions"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT climate FROM energy_data 
        WHERE climate IS NOT NULL 
          AND climate != '' 
          AND climate != 'Awaiting data'
          AND climate != 'Varies'
          AND climate != 'Varied'
        ORDER BY climate ASC
    ''')
    climates = [row[0] for row in cursor.fetchall()]
    
    # Define official Köppen climate classifications with descriptions
    koppen_climates_with_descriptions = {
        # Group A: Tropical Climates
        'Af': 'Tropical Rainforest',
        'Am': 'Tropical Monsoon', 
        'Aw': 'Tropical Savanna',
        'As': 'Tropical Savanna (Dry Summer)',
        # Group B: Arid Climates
        'BWh': 'Hot Desert',
        'BWk': 'Cold Desert',
        'BSh': 'Hot Semi-arid', 
        'BSk': 'Cold Semi-arid',
        # Group C: Temperate Climates
        'Cfa': 'Humid Subtropical',
        'Cfb': 'Oceanic',
        'Cfc': 'Subpolar Oceanic',
        'Csa': 'Hot-summer Mediterranean',
        'Csb': 'Warm-summer Mediterranean',
        'Csc': 'Cold-summer Mediterranean',
        # Group D: Continental Climates
        'Dfa': 'Hot-summer Humid Continental',
        'Dfb': 'Warm-summer Humid Continental', 
        'Dfc': 'Subarctic',
        'Dfd': 'Extremely Cold Subarctic',
        # Group E: Polar Climates
        'ET': 'Tundra',
        'EF': 'Ice Cap'
    }
    
    # Filter to only include valid Köppen classifications and format with descriptions
    valid_climates = []
    for climate in climates:
        if climate in koppen_climates_with_descriptions:
            # Format as "Code - Description"
            formatted_climate = f"{climate} - {koppen_climates_with_descriptions[climate]}"
            valid_climates.append((climate, formatted_climate))
    
    # Sort by climate code and return formatted list
    valid_climates.sort(key=lambda x: x[0])
    return [formatted for _, formatted in valid_climates]

def get_climate_code_from_formatted(formatted_climate):
    """Extract climate code from formatted string"""
    if formatted_climate == "All":
        return "All"
    # Extract the code part (everything before the first space)
    return formatted_climate.split(' - ')[0]

def query_dominant_climate_options(conn):
    """Get unique dominant climate values with descriptions and color glyphs"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT climate FROM energy_data 
        WHERE climate IS NOT NULL 
          AND climate != '' 
          AND climate != 'Awaiting data'
        ORDER BY climate ASC
    ''')
    climates = [row[0] for row in cursor.fetchall()]
    
    # Define ONLY the allowed Köppen climate classifications with descriptions
    koppen_climates_with_descriptions = {
        # Group A: Tropical Climates
        'Af': 'Tropical Rainforest',
        'Am': 'Tropical Monsoon', 
        'Aw': 'Tropical Savanna',
        # Group B: Arid Climates
        'BWh': 'Hot Desert',
        'BWk': 'Cold Desert',
        'BSh': 'Hot Semi-arid', 
        'BSk': 'Cold Semi-arid',
        # Group C: Temperate Climates
        'Cfa': 'Humid Subtropical',
        'Cfb': 'Oceanic',
        'Cfc': 'Subpolar Oceanic',
        'Csa': 'Hot-summer Mediterranean',
        'Csb': 'Warm-summer Mediterranean',
        # Group D: Continental Climates
        'Dfa': 'Hot-summer Humid Continental',
        'Dfb': 'Warm-summer Humid Continental', 
        'Dfc': 'Subarctic',
        'Dfd': 'Extremely Cold Subarctic',
        # Group E: Polar Climates
        'ET': 'Tundra',
        'EF': 'Ice Cap'
    }
    
    # Color to emoji mapping
    color_to_emoji = {
        '#0000FE': '🟦',  # Blue
        '#0077FD': '🟦',  # Blue
        '#44A7F8': '🟦',  # Light Blue
        '#FD0000': '🟥',  # Red
        '#F89292': '🟥',  # Light Red
        '#F4A400': '🟧',  # Orange
        '#FEDA60': '🟨',  # Yellow
        '#FFFE04': '🟨',  # Yellow
        '#CDCE08': '🟨',  # Yellow-Green
        '#95FE97': '🟩',  # Light Green
        '#62C764': '🟩',  # Green
        '#379632': '🟩',  # Dark Green
        '#C5FF4B': '🟩',  # Lime Green
        '#64FD33': '🟩',  # Green
        '#36C901': '🟩',  # Green
        '#FE01FC': '🟪',  # Purple
        '#CA03C2': '🟪',  # Purple
        '#973396': '🟪',  # Purple
        '#8C5D91': '🟪',  # Light Purple
        '#A5ADFE': '🟦',  # Light Blue
        '#4A78E7': '🟦',  # Blue
        '#48DDB1': '🟦',  # Teal
        '#32028A': '🟪',  # Dark Purple
        '#01FEFC': '🟦',  # Cyan
        '#3DC6FA': '🟦',  # Light Blue
        '#037F7F': '🟦',  # Dark Teal
        '#004860': '🟦',  # Dark Blue
        '#AFB0AB': '⬜',  # Gray
        '#686964': '⬛',  # Dark Gray
    }
    
    # Filter to ONLY include the specified Köppen classifications with color glyphs
    valid_climates = []
    for climate in climates:
        if climate in koppen_climates_with_descriptions:
            # Get color for this climate
            color = get_climate_color(climate)
            # Get corresponding emoji
            emoji = color_to_emoji.get(color, '⬜')  # Default to white square
            # Format as "🟦 Cfa - Humid Subtropical"
            formatted_climate = f"{emoji} {climate} - {koppen_climates_with_descriptions[climate]}"
            valid_climates.append((climate, formatted_climate, color))
    
    # Sort by climate code
    valid_climates.sort(key=lambda x: x[0])
    return [(formatted, color) for _, formatted, color in valid_climates]

def get_climate_color(climate_code):
    """Get color for climate code (handles both raw codes and formatted strings)"""
    # Extract code if it's formatted as "Code - Description"
    if " - " in str(climate_code):
        climate_code = climate_code.split(" - ")[0]
    
    colors = {
        # Tropical Climates
        'Af': '#0000FE', 'Am': '#0077FD', 'Aw': '#44A7F8', 'As': '#44A7F8',
        # Arid Climates
        'BWh': "#FD0000", 'BWk': '#F89292', 'BSh': '#F4A400', 'BSk': '#FEDA60',
        # Temperate Climates
        'Csa': '#FFFE04', 'Csb': '#CDCE08', 'Csc': '#CDCE08',
        'Cwa': '#95FE97', 'Cwb': '#62C764', 'Cwc': '#379632',
        'Cfa': '#C5FF4B', 'Cfb': '#64FD33', 'Cfc': '#36C901',
        # Continental Climates
        'Dsa': '#FE01FC', 'Dsb': '#CA03C2', 'Dsc': '#973396', 'Dsd': '#8C5D91',
        'Dwa': '#A5ADFE', 'Dwb': '#4A78E7', 'Dwc': '#48DDB1', 'Dwd': '#32028A',
        'Dfa': '#01FEFC', 'Dfb': '#3DC6FA', 'Dfc': '#037F7F', 'Dfd': '#004860',
        # Polar Climates
        'ET': '#AFB0AB', 'EF': '#686964',
        # Special categories
        'All': '#999999'
    }
    return colors.get(climate_code, '#CCCCCC')

def query_multi_climate_options(conn):
    """Get climate options that appear in multiple locations/regions"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT climate, COUNT(DISTINCT location) as location_count
        FROM energy_data 
        WHERE climate IS NOT NULL 
          AND climate != '' 
          AND climate != 'Awaiting data'
          AND location IS NOT NULL
          AND location != ''
        GROUP BY climate
        HAVING COUNT(DISTINCT location) > 1
        ORDER BY climate ASC
    ''')
    multi_climates = [row[0] for row in cursor.fetchall()]
    return multi_climates

def admin_dashboard():
    # Check if user is admin
    is_admin = st.session_state.get("user_role") == "admin"
    
    st.subheader("Admin Dashboard")
    
    # Rest of your function remains the same...
    # Tab interface for different admin functions
    tab1, tab2, tab3 = st.tabs(["Edit Records", "Review Pending Submissions", "Data Import"])
    
    with tab1:
        # Use the original manage_scale_climate_data function here instead of enhanced version
        manage_scale_climate_data()
    
    with tab2:
        # Pending Data Review (existing code)
        review_pending_data()
        
    with tab3:
        # New import tab - use unique key
        import_location_climate_data_unique()


def admin_import_and_match_studies(uploaded_file):
    global conn
    """
    Admin-only function: Import Excel and auto-match studies with review interface
    """
    try:
        # Read Excel file
        df = pd.read_excel(uploaded_file, sheet_name=0)
        
        # Check if 'Study' column exists
        if 'Study' not in df.columns:
            # Try to find a similar column name
            study_columns = [col for col in df.columns if 'study' in col.lower() or 'title' in col.lower()]
            if study_columns:
                # Use the first matching column
                study_column = study_columns[0]
            else:
                st.error("No 'Study' column found in the uploaded file. Available columns: " + ", ".join(df.columns))
                return [], []
        else:
            study_column = 'Study'
        
        # Get study names
        study_names = df[study_column].dropna().unique()
        
        matched_records = []
        unmatched_studies = []
        
        st.info(f"🔍 Matching {len(study_names)} studies in database...")
        st.warning("**Matching Rule:** Entire study text from spreadsheet must exist within the Study Reference text")
        
        progress_bar = st.progress(0)
        status_text = st.empty()

        cursor = conn.cursor()
        
        for i, study_name in enumerate(study_names):
            # Clean and normalize the study name
            clean_study = study_name.strip()
            # Normalize whitespace: replace newlines with spaces and remove extra spaces
            clean_study_normalized = ' '.join(clean_study.replace('\n', ' ').split())
            
            status_text.text(f"Searching: {clean_study_normalized[:50]}...")
            
            # Use the normalized version for matching
            clean_study_lower = clean_study_normalized.lower()
            
            # Variation 1: Exact substring match with normalized text (case-insensitive)
            cursor.execute('''
                SELECT id, paragraph, criteria, energy_method, direction, scale, climate, location
                FROM energy_data 
                WHERE LOWER(paragraph) LIKE LOWER(?)
            ''', (f'%{clean_study_normalized}%',))
            
            results = cursor.fetchall()
            
            # If no results, try with the original text (in case normalization changed something)
            if not results:
                cursor.execute('''
                    SELECT id, paragraph, criteria, energy_method, direction, scale, climate, location
                    FROM energy_data
                    WHERE LOWER(paragraph) LIKE LOWER(?)
                ''', (f'%{clean_study}%',))
                results = cursor.fetchall()
            
            # If still no results, try matching the first 80% of the normalized study name
            if not results and len(clean_study_normalized) > 20:
                partial_study = clean_study_normalized[:int(len(clean_study_normalized) * 0.8)]
                cursor.execute('''
                    SELECT id, paragraph, criteria, energy_method, direction, scale, climate, location 
                    FROM energy_data 
                    WHERE LOWER(paragraph) LIKE LOWER(?)
                ''', (f'%{partial_study}%',))
                results = cursor.fetchall()
            
            if results:
                for result in results:
                    record_id, paragraph, criteria, energy_method, direction, scale, climate, location = result
                    
                    # Additional verification with normalized text
                    paragraph_lower = paragraph.lower()
                    
                    # Check with normalized study text
                    if clean_study_lower in paragraph_lower:
                        confidence = "exact_match"
                        match_position = paragraph_lower.find(clean_study_lower)
                    elif len(clean_study_normalized) > 20 and clean_study_normalized[:int(len(clean_study_normalized) * 0.8)].lower() in paragraph_lower:
                        confidence = "partial_match_80pct"
                        match_position = paragraph_lower.find(clean_study_normalized[:int(len(clean_study_normalized) * 0.8)].lower())
                    else:
                        confidence = "weak_match"
                        match_position = -1
                    
                    matched_records.append({
                        'excel_study': clean_study,  # Keep original for display
                        'excel_study_normalized': clean_study_normalized,  # Store normalized version
                        'db_record_id': record_id,
                        'matching_paragraph': paragraph,
                        'criteria': criteria,
                        'energy_method': energy_method,
                        'direction': direction,
                        'scale': scale,
                        'climate': climate,
                        'location': location,
                        'confidence': confidence,
                        'match_position': match_position
                    })
            else:
                unmatched_studies.append({
                    'study_name': clean_study,
                    'reason': 'No database matches found with case-insensitive matching'
                })
            
            progress_bar.progress((i + 1) / len(study_names))
        
        progress_bar.empty()
        status_text.empty()
        
        # Sort matched records by confidence and match position
        matched_records.sort(key=lambda x: (
            0 if x['confidence'] == 'exact_match' else 
            1 if x['confidence'] == 'partial_match_80pct' else 2,
            x['match_position'] if x['match_position'] >= 0 else 9999
        ))
        
        return matched_records, unmatched_studies
        
    except Exception as e:
        st.error(f"Error during import: {e}")
        return [], []


def display_admin_matching_review(matched_records, unmatched_studies, excel_df=None):
    """
    Display the matching review interface for admin
    """
    # Use the Excel data from session state if not provided
    if excel_df is None and hasattr(st.session_state, 'current_excel_df'):
        excel_df = st.session_state.current_excel_df
    
    # Summary with match quality info
    st.subheader("📊 Import Results Summary")
    
    # Calculate match quality statistics
    exact_matches = len([m for m in matched_records if m['confidence'] == 'exact_match'])
    partial_matches = len([m for m in matched_records if m['confidence'] == 'partial_match_80pct'])
    weak_matches = len([m for m in matched_records if m['confidence'] == 'weak_match'])
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Studies", len(matched_records) + len(unmatched_studies))
    with col2:
        st.metric("Exact Matches", exact_matches)
    with col3:
        st.metric("Partial Matches", partial_matches)
    with col4:
        st.metric("Unmatched", len(unmatched_studies))
    
    # Show match quality warning
    if weak_matches > 0:
        st.warning(f"⚠️ {weak_matches} weak matches found. Please review these carefully!")
    
    # Initialize session state for pagination
    if "match_page" not in st.session_state:
        st.session_state.match_page = 0
    
    # Matches Tab
    if matched_records:
        st.subheader("✅ Matched Studies")
        
        # Show match quality filter
        st.write("**Filter by Match Quality:**")
        quality_filter = st.multiselect(
            "Select confidence levels to show:",
            ["exact_match", "partial_match_80pct", "weak_match"],
            default=["exact_match", "partial_match_80pct"],
            key="quality_filter"
        )
        
        # Filter matches by quality
        filtered_matches = [m for m in matched_records if m['confidence'] in quality_filter]
        
        if not filtered_matches:
            st.info("No matches found with the selected confidence levels.")
            return
        
        # IMPORT BUTTON AT THE TOP
        confirmed_matches = []
        
        # Quick select all checkbox at the top
        select_all = st.checkbox("Select All Filtered Matches", key="select_all_matches")
        
        # Process confirmed matches button at the TOP
        if filtered_matches and st.button("🚀 Import Data for Selected Matches", type="primary", key="import_top_button"):
            # If "Select All" is checked, confirm all filtered matches
            if select_all:
                confirmed_matches = filtered_matches
            else:
                # Otherwise, collect only the confirmed ones
                for i, match in enumerate(filtered_matches):
                    if st.session_state.get(f"match_confirm_{i}", match['confidence'] == 'exact_match'):
                        confirmed_matches.append(match)
            
            if confirmed_matches:
                # Use the Excel data from session state
                current_excel_df = st.session_state.get('current_excel_df')
                if current_excel_df is not None:
                    updated_count = process_confirmed_matches(confirmed_matches, current_excel_df)
                    if updated_count > 0:
                        st.success(f"✅ Successfully updated {updated_count} records!")
                        time.sleep(2)
                        st.rerun()
                else:
                    st.error("❌ Excel data not available. Please re-upload the file.")
            else:
                st.warning("No matches selected for import. Please confirm matches using the checkboxes.")
        
        st.markdown("---")
        
        # PAGINATION SETTINGS
        MATCHES_PER_PAGE = 10
        total_pages = (len(filtered_matches) + MATCHES_PER_PAGE - 1) // MATCHES_PER_PAGE
        
        # Page navigation at the top
        if total_pages > 1:
            col_prev, col_page, col_next = st.columns([1, 2, 1])
            with col_prev:
                if st.button("◀ Previous", 
                            disabled=st.session_state.match_page == 0, 
                            key=f"prev_page_{st.session_state.match_page}"):
                    st.session_state.match_page = max(0, st.session_state.match_page - 1)
                    st.rerun()
            with col_page:
                st.write(f"**Page {st.session_state.match_page + 1} of {total_pages}**")
            with col_next:
                if st.button("Next ▶", 
                            disabled=st.session_state.match_page >= total_pages - 1, 
                            key=f"next_page_{st.session_state.match_page}"):
                    st.session_state.match_page = min(total_pages - 1, st.session_state.match_page + 1)
                    st.rerun()
        
        # Calculate current page slice
        start_idx = st.session_state.match_page * MATCHES_PER_PAGE
        end_idx = min(start_idx + MATCHES_PER_PAGE, len(filtered_matches))
        current_page_matches = filtered_matches[start_idx:end_idx]
        
        st.write(f"**Showing {len(filtered_matches)} filtered matches ({start_idx + 1}-{end_idx})**")
        
        # Display current page matches
        for i, match in enumerate(current_page_matches):
            global_index = start_idx + i
            
            # Color code based on confidence
            confidence_color = {
                'exact_match': '🟢',
                'partial_match_80pct': '🟡', 
                'weak_match': '🔴'
            }
            
            with st.expander(f"{confidence_color[match['confidence']]} Match {global_index + 1} | Record ID: {match['db_record_id']}", expanded=True):
                
                # Imported Study Title
                st.markdown("#### 📥 Imported Study Title")
                st.text_area(
                    "Complete title from Excel import:",
                    value=match['excel_study'],
                    height=80,
                    key=f"imported_study_{global_index}",
                    disabled=True
                )
                
                # Database Study Reference with highlighted match
                st.markdown("#### 🗄️ Database Study Reference")
                
                paragraph = match['matching_paragraph']
                study = match['excel_study']
                study_normalized = match.get('excel_study_normalized', ' '.join(study.replace('\n', ' ').split()))
                paragraph_lower = paragraph.lower()
                study_lower = study_normalized.lower()

                if study_lower in paragraph_lower:
                    # Find the actual case version in the paragraph for highlighting
                    start_idx_text = paragraph_lower.index(study_lower)
                    end_idx_text = start_idx_text + len(study_normalized)
                    
                    # Create highlighted text with the match in bold (using original case from paragraph)
                    highlighted_paragraph = (
                        paragraph[:start_idx_text] +
                        "**" + paragraph[start_idx_text:end_idx_text] + "**" +
                        paragraph[end_idx_text:]
                    )
                    
                    st.markdown(highlighted_paragraph)
                    
                    # Match confirmation
                    st.success(f"✅ **Exact match found!** (Record ID: {match['db_record_id']})")
                    
                else:
                    # Show plain paragraph if no exact match found
                    st.text_area(
                        "Database reference:",
                        value=paragraph,
                        height=200,
                        key=f"database_paragraph_{global_index}",
                        disabled=True
                    )
                    st.error(f"❌ **Study title not found in paragraph!** (Record ID: {match['db_record_id']})")
                    
                # SIMPLE CONFIRMATION
                st.markdown("---")
                confirm_key = f"match_confirm_{global_index}"
                default_value = match['confidence'] == 'exact_match'
                
                col_confirm1, col_confirm2 = st.columns([3, 1])
                
                with col_confirm1:
                    if select_all:
                        st.session_state[confirm_key] = True
                        st.checkbox("**Confirm this match for import**", value=True, key=confirm_key, disabled=True)
                    else:
                        if confirm_key not in st.session_state:
                            st.session_state[confirm_key] = default_value
                        st.checkbox("**Confirm this match for import**", value=st.session_state[confirm_key], key=confirm_key)
                
                with col_confirm2:
                    confidence_badge = {
                        'exact_match': "🟢 Exact Match",
                        'partial_match_80pct': "🟡 Partial Match", 
                        'weak_match': "🔴 Weak Match"
                    }
                    st.info(confidence_badge[match['confidence']])
                
                if st.session_state[confirm_key]:
                    confirmed_matches.append(match)
        
        # Bottom navigation
        if total_pages > 1:
            st.markdown("---")
            col_prev_bottom, col_page_bottom, col_next_bottom = st.columns([1, 2, 1])
            with col_prev_bottom:
                if st.button("◀ Previous Page", 
                            disabled=st.session_state.match_page == 0, 
                            key=f"prev_page_bottom_{st.session_state.match_page}"):
                    st.session_state.match_page = max(0, st.session_state.match_page - 1)
                    st.rerun()
            with col_page_bottom:
                st.write(f"**Page {st.session_state.match_page + 1} of {total_pages}**")
            with col_next_bottom:
                if st.button("Next Page ▶", 
                            disabled=st.session_state.match_page >= total_pages - 1, 
                            key=f"next_page_bottom_{st.session_state.match_page}"):
                    st.session_state.match_page = min(total_pages - 1, st.session_state.match_page + 1)
                    st.rerun()
        
        # Additional import button at the bottom
        if len(filtered_matches) > MATCHES_PER_PAGE:
            st.markdown("---")
            if confirmed_matches and st.button("🚀 Import Data for Selected Matches", type="primary", key="import_bottom_button"):
                current_excel_df = st.session_state.get('current_excel_df')
                if current_excel_df is not None:
                    updated_count = process_confirmed_matches(confirmed_matches, current_excel_df)
                    if updated_count > 0:
                        st.success(f"✅ Successfully updated {updated_count} records!")
                        time.sleep(2)
                        st.rerun()
                else:
                    st.error("❌ Excel data not available. Please re-upload the file.")
    
    # Unmatched studies section
    if unmatched_studies:
        st.subheader("❌ Unmatched Studies")
        st.warning(f"{len(unmatched_studies)} studies couldn't be automatically matched")
        
        UNMATCHED_PER_PAGE = 20
        total_unmatched_pages = (len(unmatched_studies) + UNMATCHED_PER_PAGE - 1) // UNMATCHED_PER_PAGE
        
        if "unmatched_page" not in st.session_state:
            st.session_state.unmatched_page = 0
        
        # For unmatched studies pagination
        if total_unmatched_pages > 1:
            col_prev_u, col_page_u, col_next_u = st.columns([1, 2, 1])
            with col_prev_u:
                if st.button("◀ Previous", 
                            disabled=st.session_state.unmatched_page == 0, 
                            key=f"prev_unmatched_{st.session_state.unmatched_page}"):
                    st.session_state.unmatched_page = max(0, st.session_state.unmatched_page - 1)
                    st.rerun()
            with col_page_u:
                st.write(f"**Page {st.session_state.unmatched_page + 1} of {total_unmatched_pages}**")
            with col_next_u:
                if st.button("Next ▶", 
                            disabled=st.session_state.unmatched_page >= total_unmatched_pages - 1, 
                            key=f"next_unmatched_{st.session_state.unmatched_page}"):
                    st.session_state.unmatched_page = min(total_unmatched_pages - 1, st.session_state.unmatched_page + 1)
                    st.rerun()
        
        start_idx_u = st.session_state.unmatched_page * UNMATCHED_PER_PAGE
        end_idx_u = min(start_idx_u + UNMATCHED_PER_PAGE, len(unmatched_studies))
        
        for i in range(start_idx_u, end_idx_u):
            unmatched = unmatched_studies[i]
            st.write(f"{i + 1}. {unmatched['study_name']}")
        
        # Bottom navigation for unmatched
        if total_unmatched_pages > 1:
            st.markdown("---")
            col_prev_u_bottom, col_page_u_bottom, col_next_u_bottom = st.columns([1, 2, 1])
            with col_prev_u_bottom:
                if st.button("◀ Previous", 
                            disabled=st.session_state.unmatched_page == 0, 
                            key=f"prev_unmatched_bottom_{st.session_state.unmatched_page}"):
                    st.session_state.unmatched_page = max(0, st.session_state.unmatched_page - 1)
                    st.rerun()
            with col_page_u_bottom:
                st.write(f"**Page {st.session_state.unmatched_page + 1} of {total_unmatched_pages}**")
            with col_next_u_bottom:
                if st.button("Next ▶", 
                            disabled=st.session_state.unmatched_page >= total_unmatched_pages - 1, 
                            key=f"next_unmatched_bottom_{st.session_state.unmatched_page}"):
                    st.session_state.unmatched_page = min(total_unmatched_pages - 1, st.session_state.unmatched_page + 1)
                    st.rerun()
        
        # Export option
        if st.button("📤 Export Unmatched List", key="export_unmatched_button"):
            df_unmatched = pd.DataFrame(unmatched_studies)
            csv = df_unmatched.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name="unmatched_studies.csv",
                mime="text/csv",
                key="download_unmatched_csv"
            )

def extract_climate_data(climate_text):
    """
    Extract dominant climate and multi-climate regions from climate text
    Format examples:
    - "Cfa (Humid subtropical)" -> dominant: Cfa, multi: None
    - "USA | Cfa (Humid subtropical) dominant, also Dfa, Dfb, BWh" -> dominant: Cfa, multi: ['Cfa', 'Dfa', 'Dfb', 'BWh']
    - "Cfa, Dfa" -> dominant: Cfa, multi: ['Cfa', 'Dfa']
    - "Tropical" -> dominant: Tropical, multi: None
    """
    if not climate_text or pd.isna(climate_text) or str(climate_text).strip() == '':
        return None, []
    
    climate_text = str(climate_text).strip()
    
    # Remove country/region prefix if present (everything before |)
    if '|' in climate_text:
        climate_text = climate_text.split('|')[1].strip()
    
    # Initialize variables
    dominant_climate = None
    multi_climates = []
    
    # Extract ALL Koppen climate codes from the text
    all_climate_codes = re.findall(r'[A-Z][a-z]?[A-Z]?[a-z]?', climate_text)
    
    # Remove duplicates and empty values
    all_climate_codes = list(set([code.strip() for code in all_climate_codes if code.strip()]))
    
    # Determine dominant climate and multi-climates
    if len(all_climate_codes) == 0:
        # No climate codes found, check for textual climate names
        climate_lower = climate_text.lower()
        if 'tropical' in climate_lower:
            dominant_climate = 'Tropical'
            multi_climates = ['Tropical']
        elif 'arid' in climate_lower or 'desert' in climate_lower:
            dominant_climate = 'Arid'
            multi_climates = ['Arid']
        elif 'temperate' in climate_lower:
            dominant_climate = 'Temperate'
            multi_climates = ['Temperate']
        elif 'continental' in climate_lower:
            dominant_climate = 'Continental'
            multi_climates = ['Continental']
        elif 'polar' in climate_lower:
            dominant_climate = 'Polar'
            multi_climates = ['Polar']
        elif 'mediterranean' in climate_lower:
            dominant_climate = 'Mediterranean'
            multi_climates = ['Mediterranean']
    
    elif len(all_climate_codes) == 1:
        # Single climate code
        dominant_climate = all_climate_codes[0]
        multi_climates = [dominant_climate]  # Include in multi for consistency
    
    else:
        # Multiple climate codes - determine dominant
        # Look for explicit dominant pattern
        dominant_pattern = r'([A-Z][a-z]?[A-Z]?[a-z]?)\s*\([^)]+\)\s*dominant'
        dominant_match = re.search(dominant_pattern, climate_text)
        
        if dominant_match:
            dominant_climate = dominant_match.group(1).strip()
        else:
            # No explicit dominant, use the first one as dominant
            dominant_climate = all_climate_codes[0]
        
        # All codes go into multi_climates
        multi_climates = all_climate_codes
    
    # Clean up: ensure dominant is included in multi if not already
    if dominant_climate and dominant_climate not in multi_climates:
        multi_climates.append(dominant_climate)
    
    # Remove duplicates again
    multi_climates = list(set(multi_climates))
    
    return dominant_climate, multi_climates

def process_confirmed_matches(confirmed_matches, excel_df):
    """Process the user-confirmed matches with enhanced climate data handling"""
    if excel_df is None:
        st.error("❌ No Excel data available for import.")
        return 0

    cursor = conn.cursor()
    
    updated_count = 0
    not_found_in_excel = []
    
    for match in confirmed_matches:
        record_id = match['db_record_id']
        excel_study = match['excel_study']
        
        # Find the corresponding row in the Excel data
        study_column = None
        for col in excel_df.columns:
            if 'study' in col.lower() or 'title' in col.lower():
                study_column = col
                break
        
        if study_column is None:
            st.error("❌ No study column found in Excel file.")
            return 0
        
        # Find matching row in Excel
        excel_match = None
        for idx, row in excel_df.iterrows():
            excel_study_name = str(row[study_column]).strip()
            if excel_study_name == excel_study:
                excel_match = row
                break
        
        if excel_match is not None:
            # Extract data from Excel row with flexible column names
            location = ''
            climate_text = ''
            scale = ''
            
            # Find location column
            for col in excel_match.index:
                if 'location' in col.lower() or 'site' in col.lower() or 'region' in col.lower():
                    location = str(excel_match[col]) if pd.notna(excel_match[col]) else ''
            
            # Find climate column - look for 'climate' in column name
            for col in excel_match.index:
                if 'climate' in col.lower():
                    climate_text = str(excel_match[col]) if pd.notna(excel_match[col]) else ''
                    break  # Use the first climate column found
            
            # Find scale column
            for col in excel_match.index:
                if 'scale' in col.lower() and 'coverage' not in col.lower():
                    scale = str(excel_match[col]) if pd.notna(excel_match[col]) else ''
            
            # Extract dominant climate and multi-climate regions from the climate_text
            dominant_climate, multi_climates = extract_climate_data(climate_text)
            
            # Convert multi_climates list to string for database storage
            multi_climate_str = ', '.join(multi_climates) if multi_climates else None
            
            # Update the database record - store dominant in 'climate' and multi in 'climate_multi'
            cursor.execute('''
                UPDATE energy_data 
                SET location = ?, climate = ?, climate_multi = ?, scale = ?
                WHERE id = ?
            ''', (location, dominant_climate, multi_climate_str, scale, record_id))
            
            updated_count += 1
            
            # Log the climate extraction for debugging
            st.sidebar.write(f"Record {record_id}: Climate text='{climate_text}' -> Dominant='{dominant_climate}', Multi='{multi_climate_str}'")
            
        else:
            not_found_in_excel.append(excel_study)
    
    conn.commit()
    
    if not_found_in_excel:
        st.warning(f"⚠️ {len(not_found_in_excel)} studies not found in Excel file")
    
    return updated_count

# Add the new climate_multi column to the database
def add_climate_multi_column():
    """Add climate_multi column to store multiple climate regions"""
    cursor = conn.cursor()
    
    print("🔧 Adding climate_multi column...")
    
    # Add climate_multi column if it doesn't exist
    try:
        cursor.execute("ALTER TABLE energy_data ADD COLUMN climate_multi TEXT")
        print("✅ Added 'climate_multi' column to energy_data table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("ℹ️ 'climate_multi' column already exists")
        else:
            print(f"⚠️ Error with climate_multi column: {e}")
    
    conn.commit()
    print("🔧 Database schema update completed")

# Run this once to add the new column
#add_climate_multi_column()

def remove_scale_coverage_column():
    """Remove scale_coverage column from the database"""
    global conn
    cursor = conn.cursor()
    
    print("🔧 Removing scale_coverage column...")
    
    try:
        # Create a temporary table without scale_coverage
        cursor.execute('''
            CREATE TABLE energy_data_temp AS 
            SELECT id, group_id, criteria, energy_method, direction, paragraph, 
                   status, user, scale, climate, location, climate_multi
            FROM energy_data
        ''')
        
        # Drop the old table
        cursor.execute("DROP TABLE energy_data")
        
        # Rename the temporary table
        cursor.execute("ALTER TABLE energy_data_temp RENAME TO energy_data")
        
        print("✅ Successfully removed 'scale_coverage' column")
        
    except Exception as e:
        print(f"⚠️ Error removing scale_coverage column: {e}")
        # If something goes wrong, rollback any changes
        conn.rollback()
    
    conn.commit()
    print("🔧 Database schema update completed")

# Run this function once to remove the column
#remove_scale_coverage_column()


def query_multi_climate_options(conn):
    """Get unique climate codes from climate_multi column (multiple selection)"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT climate_multi FROM energy_data 
        WHERE climate_multi IS NOT NULL 
          AND climate_multi != '' 
    ''')
    
    multi_climates = set()
    for row in cursor.fetchall():
        if row[0]:
            # Split comma-separated climate codes
            codes = [code.strip() for code in row[0].split(',')]
            multi_climates.update(codes)
    
    return sorted(multi_climates)


def add_location_scale_coverage_columns():
    db_file = 'my_database.db'
    cursor = conn.cursor()
    
    print("🔧 Adding location column...")
    
    # Add location column if it doesn't exist
    try:
        cursor.execute("ALTER TABLE energy_data ADD COLUMN location TEXT")
        print("✅ Added 'location' column to energy_data table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("ℹ️ 'location' column already exists")
        else:
            print(f"⚠️ Error with location column: {e}")
    
    # REMOVED: scale_coverage column addition
    
    conn.commit()
    
    print("🔧 Database schema update completed")
    
#add_location_scale_coverage_columns()
    

def manage_scale_climate_data():
    global conn
    st.subheader("Edit Records - Full Record Management")
    cursor = conn.cursor()
    
    # Get all column names to make it dynamic
    cursor.execute("PRAGMA table_info(energy_data)")
    columns_info = cursor.fetchall()
    column_names = [col[1] for col in columns_info]
    
    # Get dynamic options from database with error handling
    try:
        scale_options = query_dynamic_scale_options(conn)
        climate_options = query_climate_options(conn)
 
    except Exception as e:
        st.warning("Some filter data is not available yet. Please import location and climate data first.")
        scale_options = []
        climate_options = []
    
    # If no imported data yet, provide some defaults
    if not scale_options:
        scale_options = ["Not imported"]
    
    if not climate_options:
        climate_options = ["Not Imported"]
    
    # Get counts exactly like the main app - EXCLUDE EMPTY/ZERO RECORDS
    cursor.execute('''
        SELECT criteria, COUNT(paragraph) as count
        FROM energy_data
        WHERE paragraph IS NOT NULL 
          AND paragraph != '' 
          AND paragraph != '0' 
          AND paragraph != '0.0'
          AND paragraph != 'None'
          AND LENGTH(TRIM(paragraph)) > 0
          AND status NOT IN ("pending", "rejected")
        GROUP BY criteria
    ''')
    criteria_counts = dict(cursor.fetchall())
    
    cursor.execute('''
        SELECT energy_method, COUNT(paragraph) as count
        FROM energy_data
        WHERE paragraph IS NOT NULL 
          AND paragraph != '' 
          AND paragraph != '0' 
          AND paragraph != '0.0'
          AND paragraph != 'None'
          AND LENGTH(TRIM(paragraph)) > 0
          AND status NOT IN ("pending", "rejected")
        GROUP BY energy_method
    ''')
    method_counts = dict(cursor.fetchall())
    
    # Get all approved records for display - EXCLUDE EMPTY/ZERO RECORDS
    cursor.execute('''
        SELECT id, criteria, energy_method, direction, paragraph, user, status, scale, climate, location
        FROM energy_data 
        WHERE status NOT IN ("pending", "rejected")
          AND paragraph IS NOT NULL 
          AND paragraph != '' 
          AND paragraph != '0' 
          AND paragraph != '0.0'
          AND paragraph != 'None'
          AND LENGTH(TRIM(paragraph)) > 0
        ORDER BY criteria, energy_method, id
    ''')
    records = cursor.fetchall()

    # Filter options with proper counts
    criteria_list = ["All determinants"] + [f"{criteria} [{count}]" for criteria, count in criteria_counts.items()]
    method_list = ["All outputs"] + [f"{method} [{count}]" for method, count in method_counts.items()]
    
    # Direction and status options (these remain hardcoded as they're not from imports)
    direction_options = ["Increase", "Decrease"]
    status_options = ["approved", "rejected"]
    
    # Initialize all filter variables
    selected_scales = []
    selected_climates = []
    selected_climates = []

    
    # Filters
    col1, col2, = st.columns(2)
    with col1:
        selected_criteria = st.selectbox("Filter by Determinant", criteria_list, key="admin_edit_criteria")
        actual_criteria = selected_criteria.split(" [")[0] if selected_criteria != "All determinants" else None
    with col2:
        selected_method = st.selectbox("Filter by Energy Output", method_list, key="admin_edit_method")
        actual_method = selected_method.split(" [")[0] if selected_method != "All outputs" else None
    

    # Climate and location filters
    col3, col4, = st.columns(2)
    
    with col3:
        # Multi-select for scale filter with dynamic options
        if scale_options:
            selected_scales = st.multiselect("Filter by Scale", scale_options, key="admin_edit_scale_filter")
        else:
            st.info("No scale data")

        with col4:
            # Climate filter - using dropdown with colored glyphs (no redundant preview)
            if climate_options:            
                # Extract just the formatted text for the dropdown
                climate_dropdown_options = ["All"] + [formatted for formatted, color in climate_options]
                
                selected_climate_dropdown = st.selectbox(
                    "Select Climate",
                    options=climate_dropdown_options,
                    key="admin_climate_dropdown"
                )
                
                # Extract climate code for filtering
                if selected_climate_dropdown != "All":
                    climate_code = selected_climate_dropdown.split(" - ")[0].replace("🟦 ", "").replace("🟥 ", "").replace("🟧 ", "").replace("🟨 ", "").replace("🟩 ", "").replace("🟪 ", "").replace("⬛ ", "").replace("⬜ ", "") if " - " in selected_climate_dropdown else selected_climate_dropdown
                    selected_climates = [climate_code]
                else:
                    selected_climates = []
            else:
                st.info("No climate data available")
                selected_climates = []
    
    
    # Filter records in memory
    filtered_records = records
    if actual_criteria:
        filtered_records = [r for r in filtered_records if r[1] == actual_criteria]
    if actual_method:
        filtered_records = [r for r in filtered_records if r[2] == actual_method]
    if selected_scales:
        filtered_records = [r for r in filtered_records if r[7] in selected_scales]
    if selected_climates:
        filtered_records = [r for r in filtered_records if r[8] in selected_climates]

    
    st.write(f"**Showing {len(filtered_records)} approved records**")
    
    # Show data source info
    with st.expander("📊 Data Source Info", expanded=False):
        st.write(f"**Dynamic Scale Options ({len(scale_options)}):** {', '.join(scale_options[:10])}{'...' if len(scale_options) > 10 else ''}")
        st.write(f"**Dynamic Climate Options ({len(climate_options)}):** {', '.join(climate_options[:10])}{'...' if len(climate_options) > 10 else ''}")
        st.caption("💡 These options are automatically extracted from your imported Excel data")
    
    # Process records in batches if needed
    BATCH_SIZE = 10
    if len(filtered_records) > BATCH_SIZE:
        total_pages = (len(filtered_records) + BATCH_SIZE - 1) // BATCH_SIZE
        page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, key="admin_edit_page")
        start_idx = (page - 1) * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, len(filtered_records))
        display_records = filtered_records[start_idx:end_idx]
    else:
        display_records = filtered_records
    
    for record in display_records:
        record_id, criteria, energy_method, direction, paragraph, user, status, scale, climate, location = record
        
        st.markdown("---")
        
        # Header with Edit/Save buttons
        col_header1, col_header2 = st.columns([3, 1])
        with col_header1:
            st.write(f"**Record ID:** {record_id}")
            st.caption(f"Originally submitted by: {user}")
        
        with col_header2:
            edit_mode = st.session_state.get(f"admin_full_edit_{record_id}", False)
            
            if not edit_mode:
                if st.button("✏️ Edit Record", key=f"admin_full_edit_btn_{record_id}", use_container_width=True):
                    st.session_state[f"admin_full_edit_{record_id}"] = True
                    st.rerun()
        
        # Display/Edit all fields
        if st.session_state.get(f"admin_full_edit_{record_id}"):
            # Edit Mode - All fields editable
            col1, col2 = st.columns(2)
            
            with col1:
                # Determinant (free text input for flexibility)
                new_criteria = st.text_input("Determinant", value=criteria, key=f"admin_criteria_{record_id}")
                
                # Energy Output (free text input for flexibility)
                new_energy_method = st.text_input("Energy Output", value=energy_method, key=f"admin_energy_method_{record_id}")
                
                # Direction
                new_direction = st.radio("Direction", direction_options, 
                                    index=direction_options.index(direction) if direction in direction_options else 0,
                                    key=f"admin_direction_{record_id}", horizontal=True)
            
            with col2:
                # Scale - Dynamic dropdown from imported data
                st.write("**Scale:**")
                new_scale = st.selectbox(
                    "Select Scale",
                    options=[""] + scale_options,
                    index=scale_options.index(scale) + 1 if scale in scale_options else 0,
                    key=f"admin_scale_{record_id}"
                )
                
                # Climate - Dynamic dropdown with color coding
                st.write("**Climate:**")
                climate_index = 0
                if climate in climate_options:
                    climate_index = climate_options.index(climate) + 1
                
                selected_climate = st.selectbox(
                    "Select Climate",
                    options=[""] + climate_options,
                    index=climate_index,
                    key=f"admin_climate_{record_id}"
                )
                new_climate = selected_climate
                
                # Show climate color preview
                if selected_climate:
                    color = get_climate_color(selected_climate)
                    st.markdown(f"<span style='background-color: {color}; padding: 4px 12px; border-radius: 12px; color: black; font-weight: bold;'>{selected_climate}</span>", unsafe_allow_html=True)
                
                # Location and Scale
                new_location = st.text_input("Location", value=location or "", key=f"admin_location_{record_id}")
                new_scale = st.text_input("Scale", value=scale or "", key=f"admin_scale_{record_id}")
                
                # Status
                new_status = st.selectbox("Status", status_options,
                                        index=status_options.index(status) if status in status_options else 0,
                                        key=f"admin_status_{record_id}")
            
            # Paragraph content (larger area)
            st.write("**Study Content:**")
            new_paragraph = st.text_area("Content", value=paragraph, height=150, key=f"admin_paragraph_{record_id}")
            
            # Save and Cancel buttons for individual record
            col_save, col_cancel = st.columns(2)
            with col_save:
                if st.button("💾 Save This Record", key=f"admin_save_single_{record_id}", use_container_width=True, type="primary"):
                    # Save individual record to database
                    conn = sqlite3.connect("my_database.db")
                    cursor = conn.cursor()
                    
                    cursor.execute('''
                        UPDATE energy_data 
                        SET criteria = ?, energy_method = ?, direction = ?, paragraph = ?, 
                            scale = ?, climate = ?, location = ?, scale = ?, status = ?
                        WHERE id = ?
                    ''', (
                        new_criteria,
                        new_energy_method, 
                        new_direction,
                        new_paragraph,
                        new_scale,
                        new_climate,
                        new_location,
                        new_status,
                        record_id
                    ))
                    
                    conn.commit()
                    conn.close()
                    
                    st.session_state[f"admin_full_edit_{record_id}"] = False
                    st.success(f"✅ Record {record_id} updated successfully!")
                    time.sleep(1)
                    st.rerun()
            
            with col_cancel:
                if st.button("❌ Cancel Edit", key=f"admin_cancel_single_{record_id}", use_container_width=True):
                    st.session_state[f"admin_full_edit_{record_id}"] = False
                    st.rerun()
                    
        else:
            # View Mode - Display only
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Determinant:** {criteria}")
                st.write(f"**Energy Output:** {energy_method}")
                st.write(f"**Direction:** {direction}")
                if location:
                    st.write(f"**Location:** {location}")
            
            with col2:
                st.write(f"**Scale:** {scale}")
                if climate:
                    color = get_climate_color(climate)
                    st.markdown(f"**Climate:** <span style='background-color: {color}; padding: 2px 8px; border-radius: 10px; color: black;'>{climate}</span>", unsafe_allow_html=True)
                st.write(f"**Status:** {status}")
            
            # Study content preview
            with st.expander("View Study Content", expanded=False):
                st.text_area("Content", value=paragraph, height=100, key=f"admin_view_content_{record_id}", disabled=True)
    
    # Quick actions
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🔄 Refresh Data", key="admin_refresh_edit", use_container_width=True):
            st.rerun()
    with col2:
        if st.button("📊 Show Statistics", key="admin_stats_edit", use_container_width=True):
            awaiting_scale = len([r for r in records if r[7] in ["Awaiting data", "Not Specified", ""] or not r[7]])
            awaiting_climate = len([r for r in records if r[8] in ["Awaiting data", "Not Specified", ""] or not r[8]])
            total_records = len(records)
            st.info(f"""
            **Database Statistics:**
            - Total approved records: {total_records}
            - Records needing scale data: {awaiting_scale}
            - Records needing climate data: {awaiting_climate}
            - Unique scale types: {len(scale_options)}
            - Unique climate types: {len(climate_options)}
            """)
    with col3:
        if st.button("🔍 View Table Schema", key="admin_schema_view", use_container_width=True):
            st.info("**Current Table Columns:**")
            for col_name in column_names:
                st.write(f"- {col_name}")


def review_pending_data():
    global conn
    st.subheader("Review Pending Data Submissions")
    
    # Create a local database connection and cursor
    conn_local = sqlite3.connect(db_file)
    cursor = conn_local.cursor()
    
    # Fetch only pending records - EXCLUDE EMPTY/ZERO RECORDS
    cursor.execute('''
        SELECT id, criteria, energy_method, direction, paragraph, user, status 
        FROM energy_data 
        WHERE status = 'pending'
            AND paragraph IS NOT NULL 
            AND paragraph != '' 
            AND paragraph != '0' 
            AND paragraph != '0.0'
            AND paragraph != 'None'
            AND LENGTH(TRIM(paragraph)) > 0
        ORDER BY id DESC
    ''')
    pending_records = cursor.fetchall()
    
    st.write(f"**{len(pending_records)} pending submissions awaiting review**")
    
    if not pending_records:
        st.success("🎉 No pending submissions! All caught up.")
        conn_local.close()  # Close the local connection
        return
    
    for record in pending_records:
        record_id, criteria, energy_method, direction, paragraph, user, status = record
        
        st.markdown("---")
        
        # Header with Edit button
        col_header1, col_header2 = st.columns([3, 1])
        with col_header1:
            st.write(f"**Record ID:** {record_id}, **Submitted by:** {user}")
        
        with col_header2:
            edit_mode = st.session_state.get(f"admin_pending_edit_{record_id}", False)
            
            if not edit_mode:
                if st.button("✏️ Edit", key=f"admin_pending_edit_btn_{record_id}", use_container_width=True):
                    st.session_state[f"admin_pending_edit_{record_id}"] = True
                    st.rerun()
        
        if st.session_state.get(f"admin_pending_edit_{record_id}"):
            # Edit mode for pending records
            col1, col2 = st.columns(2)
            
            with col1:
                new_criteria = st.text_input("Determinant", value=criteria, key=f"admin_pending_criteria_{record_id}")
                new_energy_method = st.text_input("Energy Output", value=energy_method, key=f"admin_pending_method_{record_id}")
            
            with col2:
                new_direction = st.radio("Direction", ["Increase", "Decrease"],
                                       index=0 if direction == "Increase" else 1,
                                       key=f"admin_pending_direction_{record_id}", horizontal=True)
            
            new_paragraph = st.text_area("Study Content", value=paragraph, height=150, key=f"admin_pending_paragraph_{record_id}")
            
            # Action buttons in edit mode
            col_save, col_approve, col_reject, col_cancel = st.columns(4)
            
            with col_save:
                if st.button("💾 Save", key=f"admin_pending_save_{record_id}", use_container_width=True):
                    # Save edits but keep as pending
                    conn_edit = sqlite3.connect("my_database.db")
                    cursor_edit = conn_edit.cursor()
                    cursor_edit.execute('''
                        UPDATE energy_data 
                        SET criteria = ?, energy_method = ?, direction = ?, paragraph = ?
                        WHERE id = ?
                    ''', (new_criteria, new_energy_method, new_direction, new_paragraph, record_id))
                    conn_edit.commit()
                    conn_edit.close()
                    st.session_state[f"admin_pending_edit_{record_id}"] = False
                    st.success(f"Record {record_id} updated!")
                    time.sleep(1)
                    st.rerun()
            
            with col_approve:
                if st.button("✅ Approve", key=f"admin_pending_approve_edit_{record_id}", use_container_width=True, type="primary"):
                    # Save edits and approve
                    conn_edit = sqlite3.connect("my_database.db")
                    cursor_edit = conn_edit.cursor()
                    cursor_edit.execute('''
                        UPDATE energy_data 
                        SET criteria = ?, energy_method = ?, direction = ?, paragraph = ?, status = 'approved'
                        WHERE id = ?
                    ''', (new_criteria, new_energy_method, new_direction, new_paragraph, record_id))
                    conn_edit.commit()
                    conn_edit.close()
                    st.session_state[f"admin_pending_edit_{record_id}"] = False
                    st.success(f"Record {record_id} approved and updated!")
                    time.sleep(1)
                    st.rerun()
            
            with col_reject:
                if st.button("❌ Reject", key=f"admin_pending_reject_edit_{record_id}", use_container_width=True):
                    conn_edit = sqlite3.connect("my_database.db")
                    cursor_edit = conn_edit.cursor()
                    cursor_edit.execute("UPDATE energy_data SET status = 'rejected' WHERE id = ?", (record_id,))
                    conn_edit.commit()
                    conn_edit.close()
                    st.session_state[f"admin_pending_edit_{record_id}"] = False
                    st.error(f"Record {record_id} rejected.")
                    time.sleep(1)
                    st.rerun()
            
            with col_cancel:
                if st.button("🚫 Cancel", key=f"admin_pending_cancel_{record_id}", use_container_width=True):
                    st.session_state[f"admin_pending_edit_{record_id}"] = False
                    st.rerun()
                    
        else:
            # View mode for pending records
            # Display the relationship
            st.markdown(f"<p>The following pending study shows that a {direction} (or presence) in {criteria} leads to <i>{'higher' if direction == 'Increase' else 'lower'}</i> {energy_method}.</p>", unsafe_allow_html=True)
            
            # Display the submitted text
            st.write("**Submitted text:**")
            st.text_area("Content", value=paragraph, height=150, key=f"admin_pending_content_{record_id}", disabled=True)
            
            # Admin approval/rejection buttons (view mode)
            col1, col2, col3 = st.columns([1, 1, 2])
            
            with col1:
                if st.button(f"✅ Approve", key=f"admin_approve_{record_id}", use_container_width=True, type="primary"):
                    conn_edit = sqlite3.connect("my_database.db")
                    cursor_edit = conn_edit.cursor()
                    cursor_edit.execute("UPDATE energy_data SET status = 'approved' WHERE id = ?", (record_id,))
                    conn_edit.commit()
                    conn_edit.close()
                    st.success(f"Record {record_id} approved and added to main database!")
                    time.sleep(1)
                    st.rerun()
            
            with col2:
                if st.button(f"❌ Reject", key=f"admin_reject_{record_id}", use_container_width=True):
                    conn_edit = sqlite3.connect("my_database.db")
                    cursor_edit = conn_edit.cursor()
                    cursor_edit.execute("UPDATE energy_data SET status = 'rejected' WHERE id = ?", (record_id,))
                    conn_edit.commit()
                    conn_edit.close()
                    st.error(f"Record {record_id} rejected.")
                    time.sleep(1)
                    st.rerun()
    
    # Close the local connection
    conn_local.close()
    
    # Quick actions
    st.markdown("---")
    if st.button("🔄 Refresh Pending List", key="admin_refresh_pending", use_container_width=True):
        st.rerun()

def user_dashboard():
    global conn
    st.subheader("Review Your Submissions")

    # Create a local database connection and cursor
    conn_local = sqlite3.connect(db_file)
    cursor = conn_local.cursor()

    # Fetch all records created by the current user
    records = cursor.execute("""
        SELECT id, criteria, energy_method, direction, paragraph, user, status
        FROM energy_data
        WHERE user = ?
    """, (st.session_state.current_user,)).fetchall()

    if not records:
        st.write("No records found.")
    else:
        for record in records:
            record_id, criteria, energy_method, direction, paragraph, user, status = record
            if st.session_state.current_user == user:
                st.write(f"**Record ID:** {record_id}, **created by:** {user}, **Status:** {status}")
                st.markdown(f"<p>The following pending study shows that a {direction} (or presence) in {criteria} leads to <i>{'higher' if direction == 'Increase' else 'lower'}</i> {energy_method}.</p>", unsafe_allow_html=True)
                st.write(f"**Submitted text:** {paragraph}")

            # Admin options to approve/reject or take action
            col1, col2 = st.columns(2)
            with col2:
                if st.button(f"Remove this submission {record_id}"):
                    try:
                        cursor.execute("DELETE FROM energy_data WHERE id = ?", (record_id,))
                        conn_local.commit()
                        st.success(f"Submission {record_id} has been removed.")
                        time.sleep(1)
                        st.rerun()  # Refresh the page to reflect the changes
                    except Exception as e:
                        st.error(f"Failed to remove record {record_id}: {e}")

            st.markdown("---")  # Separator between records
    
    # Close the local connection
    conn_local.close()
    
def edit_columns():
    db_file = 'my_database.db'
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Add `status` column default to 'None'
    cursor.execute("UPDATE energy_data SET status = 'None'")
    conn.commit()
    conn.close()

# Run this function once to update the database schema
#edit_columns()

# Function to reset and re-create the table
def csv_to_sqlite(csv_file, db_file):
    try:
        # Read the CSV file into a DataFrame
        print(f"Reading CSV file: {csv_file}")
        df = pd.read_csv(csv_file, encoding='utf-8-sig')

        # Connect to the SQLite database (or create it)
        print(f"Connecting to database: {db_file}")
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # Drop the old table if it exists
        print("Dropping the existing 'energy_data' table if it exists")
        cursor.execute("DROP TABLE IF EXISTS energy_data")

        # Create the new table with group_id, criteria, energy_method, direction, and paragraph fields
        print("Creating the table 'energy_data' with direction")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS energy_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER,
                criteria TEXT,
                energy_method TEXT,
                direction TEXT,  -- Store Increase/Decrease here
                paragraph TEXT
            )
        ''')

        # Insert CSV data into SQLite, splitting paragraphs
        group_id = 1
        criteria_col = df.columns[0]  # Assuming the first column is 'criteria'
        
        # Group columns based on "Increase" and "Decrease"
        increase_cols = [col for col in df.columns if col.endswith('Increase')]
        reduction_cols = [col for col in df.columns if col.endswith('Decrease')]
        
        for _, row in df.iterrows():
            criteria = row[criteria_col]
            # Insert for each increase column
            for method in increase_cols:
                text_content = row[method]
                paragraphs = split_into_paragraphs(text_content)
                base_method = method.replace('Increase', '').strip()
                
                for paragraph in paragraphs:
                    cursor.execute('''
                        INSERT INTO energy_data (group_id, criteria, energy_method, direction, paragraph, status)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (group_id, criteria, base_method, 'Increase', paragraph))

            # Insert for each reduction column
            for method in reduction_cols:
                text_content = row[method]
                paragraphs = split_into_paragraphs(text_content)
                base_method = method.replace('Decrease', '').strip()
                
                for paragraph in paragraphs:
                    cursor.execute('''
                        INSERT INTO energy_data (group_id, criteria, energy_method, direction, paragraph, status)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (group_id, criteria, base_method, 'Decrease', paragraph))

            group_id += 1

        # Commit and close the connection
        conn.commit()
        print("Data inserted successfully")
        conn.close()

    except Exception as e:
        print(f"Error: {e}")

# Function to split a cell's content into paragraphs
def split_into_paragraphs(text: str) -> list:
    paragraphs = [para.strip() for para in str(text).split('\n\n') if para.strip()]
    return paragraphs

# Run this function once to reset and create the database
#csv_to_sqlite('Full_References_011.csv', 'my_database.db')

# Initialize session state variables
if "current_tab" not in st.session_state:
    st.session_state.current_tab = "tab0"
if 'login_status' not in st.session_state:
    st.session_state.login_status = None
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'selected_criteria' not in st.session_state:
    st.session_state.selected_criteria = None
if 'selected_method' not in st.session_state:
    st.session_state.selected_method = None
if 'show_new_record_form' not in st.session_state:
    st.session_state.show_new_record_form = False
if "user_role" not in st.session_state:
    st.session_state.user_role = None

# Database connection
db_file = 'my_database.db'
# conn = sqlite3.connect(db_file)

# Query functions #######################################################
def query_paragraphs(conn, criteria, energy_method, direction, selected_scales=None, selected_dominant_climates=None):
    """Query paragraphs with simplified filters - use local connection"""
    try:
        cursor = conn.cursor()
    
        # Base query
        query = '''
            SELECT id, paragraph FROM energy_data
            WHERE criteria = ? AND energy_method = ? AND direction = ? 
            AND status NOT IN ("pending", "rejected")
        '''
        params = [criteria, energy_method, direction]
        
        # Add scale filter if provided
        if selected_scales and "All" not in selected_scales:
            placeholders = ','.join('?' * len(selected_scales))
            query += f' AND scale IN ({placeholders})'
            params.extend(selected_scales)
        
        # Add dominant climate filter if provided
        if selected_dominant_climates and "All" not in selected_dominant_climates:
            if "Varies" in selected_dominant_climates:
                # For "Varies", look for records with multiple climates in climate_multi
                query += ' AND climate_multi IS NOT NULL AND climate_multi != "" AND INSTR(climate_multi, ",") > 0'
            else:
                placeholders = ','.join('?' * len(selected_dominant_climates))
                query += f' AND climate IN ({placeholders})'
                params.extend(selected_dominant_climates)
        
        cursor.execute(query, params)
        paragraphs = cursor.fetchall()

        return [(id, para) for id, para in paragraphs if para not in ['0', '0.0', '', None]]
    except Exception as e:
        st.error(f"Database error: {e}")
        return []

def query_criteria_list(conn):
    cursor = conn.cursor()
    cursor.execute('''
        SELECT criteria, COUNT(paragraph)
        FROM energy_data
        GROUP BY criteria
    ''')
    return cursor.fetchall()

def query_energy_method_list(conn):
    cursor = conn.cursor()
    cursor.execute('''
        SELECT energy_method, COUNT(paragraph)
        FROM energy_data
        GROUP BY energy_method
    ''', )
    return cursor.fetchall()

def query_criteria_counts(conn):
        cursor = conn.cursor()
        cursor.execute('''
            SELECT criteria, COUNT(paragraph) as count
            FROM energy_data
            WHERE paragraph IS NOT NULL AND paragraph != '' AND paragraph != '0' AND paragraph != '0.0' AND status NOT IN ("pending", "rejected")
            GROUP BY criteria
        ''')
        return cursor.fetchall()

def query_energy_method_counts(conn, selected_criteria):
    """Get energy methods with counts for specific criteria - use local connection"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT energy_method, COUNT(paragraph) as count
        FROM energy_data
        WHERE criteria = ? AND (paragraph IS NOT NULL AND paragraph != '' AND paragraph != '0' AND paragraph != '0.0' AND status NOT IN ("pending", "rejected")) 
        GROUP BY energy_method
    ''', (selected_criteria,))
    return cursor.fetchall()

def query_location_options(conn):
    """Get unique location values from the database"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT location FROM energy_data 
        WHERE location IS NOT NULL 
          AND location != '' 
        ORDER BY location ASC
    ''')
    locations = [row[0] for row in cursor.fetchall()]
    return [loc for loc in locations if loc and str(loc).strip()]


def query_scale_options(conn):
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT scale FROM energy_data 
        WHERE scale IS NOT NULL AND scale != '' 
        ORDER BY scale ASC
    ''')
    return [row[0] for row in cursor.fetchall()]

def query_climate_options(conn):
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT climate FROM energy_data 
        WHERE climate IS NOT NULL AND climate != '' 
        ORDER BY climate ASC
    ''')
    return [row[0] for row in cursor.fetchall()]

def query_dynamic_scale_options(conn):
    """Get unique scale values from the database"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT scale FROM energy_data 
        WHERE scale IS NOT NULL 
          AND scale != '' 
          AND scale != 'Awaiting data'
        ORDER BY scale ASC
    ''')
    scales = [row[0] for row in cursor.fetchall()]
    
    # Filter out None and empty values, and sort
    scales = [s for s in scales if s and str(s).strip()]
    return sorted(scales)

def query_dynamic_climate_options(conn):
    """Get unique climate values with Koppen classification colors"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT climate FROM energy_data 
        WHERE climate IS NOT NULL 
          AND climate != '' 
          AND climate != 'Awaiting data'
        ORDER BY climate ASC
    ''')
    climates = [row[0] for row in cursor.fetchall()]
    
    # Filter out None and empty values
    climates = [c for c in climates if c and str(c).strip()]
    return sorted(climates)

# End of queries section #################################

# ADMIN ACT

def admin_actions(conn, paragraph_id, new_text=None, delete=False):
    cursor = conn.cursor()
    if delete:
        cursor.execute("DELETE FROM energy_data WHERE id = ?", (paragraph_id,))
        conn.commit()
        st.success(f"Record {paragraph_id} deleted.")
    elif new_text:
        cursor.execute("UPDATE energy_data SET paragraph = ? WHERE id = ?", (new_text, paragraph_id))
        conn.commit()
        st.success(f"Record {paragraph_id} updated.")

def logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

def signup():
    username = st.text_input("Username", placeholder="Enter your username", key="signup_username")
    password = st.text_input("Password", type="password", placeholder="Enter your password", key="signup_password")
    if st.button("Sign Up"):
        if username and password:
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO users (username, password, role)
                    VALUES (?, ?, 'user')
                ''', (username, hashed_password))
                conn.commit()
                st.success("Account created successfully!")
            except sqlite3.IntegrityError:
                st.error("Username already exists.")
        else:
            st.error("Please fill out all fields.")

def login_function():
    username = st.text_input("Username", placeholder="Enter your username", key="login_username")
    password = st.text_input("Password", type="password", placeholder="Enter your password", key="login_password")
    if st.button("Login"):
        cursor = conn.cursor()
        cursor.execute("SELECT password, role FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()

    if user and bcrypt.checkpw(password.encode('utf-8'), user[0]):
        st.session_state.logged_in = True
        st.session_state.current_user = username
        st.session_state.user_role = user[1]
        st.success(f"Welcome, {username}!")
        st.rerun()
    else:
        st.error("Invalid username or password.")


# Initialize session state variables
if "current_tab" not in st.session_state:
    st.session_state.current_tab = "tab0"
if 'login_status' not in st.session_state:
    st.session_state.login_status = None
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'selected_criteria' not in st.session_state:
    st.session_state.selected_criteria = None
if 'selected_method' not in st.session_state:
    st.session_state.selected_method = None
if 'show_new_record_form' not in st.session_state:
    st.session_state.show_new_record_form = False
if "user_role" not in st.session_state:
    st.session_state.user_role = None


#  main App section - CLEAN VERSION ################################################

def render_main_tab():
    global conn
    # """Render the main SpatialBuild Energy tab content"""
    st.title("Welcome to SpatialBuild Energy")
    welcome_html = ("""<h7>This tool distills insights from over 200 studies on building energy consumption across meso and macro scales, spanning neighborhood, urban, state, regional, national, and global levels. It maps more than 100 factors influencing energy use, showing whether each increases or decreases energy outputs like total consumption, energy use intensity, or heating demand. Designed for urban planners and policymakers, the tool provides insights to craft smarter energy reduction strategies.</p><p><h7>"""
    )
    st.markdown(welcome_html, unsafe_allow_html=True)

    how_it_works_html = ("""
    1. Pick Your Focus: Choose the determinant you want to explore.<br>
    2. Select Energy Outputs: For example energy use intensity or heating demand from our database.<br>
    3. Filter the Results by the direction of the relationship (e.g., increases or decreases), and access the relevant studies with the links provided."""
    )
    st.markdown(how_it_works_html, unsafe_allow_html=True)

    # Initialize session state for selections
    if 'selected_criteria_with_count' not in st.session_state:
        st.session_state.selected_criteria_with_count = None
    if 'selected_direction_with_count' not in st.session_state:
        st.session_state.selected_direction_with_count = None
    if 'selected_energy_method_with_count' not in st.session_state:
        st.session_state.selected_energy_method_with_count = None    

    # Criteria Dropdown with Counts and Placeholder
    criteria_counts = query_criteria_counts(conn)
    criteria_list = ["Select a determinant"] + [f"{row[0]} [{row[1]}]" for row in criteria_counts]
    selected_criteria_with_count = st.selectbox(
        "Determinant",
        criteria_list,
        index=0 if st.session_state.selected_criteria_with_count is None else criteria_list.index(f"{st.session_state.selected_criteria_with_count} [{[count for crit, count in criteria_counts if crit == st.session_state.selected_criteria][0]}]"),
        format_func=lambda x: x if x == "Select a determinant" else x,
        key="main_determinant_select"  # Unique key
    )

    if selected_criteria_with_count != "Select a determinant":
        new_criteria = selected_criteria_with_count.split(" [")[0]
        if new_criteria != st.session_state.selected_criteria:
            st.session_state.selected_criteria = new_criteria
            st.session_state.selected_method = None
            st.rerun()

        # Energy Method Dropdown with Counts and Placeholder
        energy_method_counts = query_energy_method_counts(conn, st.session_state.selected_criteria)
        method_list = ["Select an output"] + [f"{row[0]} [{row[1]}]" for row in energy_method_counts]

        selected_method_with_count = st.selectbox(
            "Energy Output(s)",
            method_list,
            index=0 if st.session_state.selected_method is None else method_list.index(f"{st.session_state.selected_method} [{[count for meth, count in energy_method_counts if meth == st.session_state.selected_method][0]}]"),
            format_func=lambda x: x if x == "Select an output" else x,
            key="main_output_select"  # Unique key
        )

        if selected_method_with_count != "Select an output":
            st.session_state.selected_method = selected_method_with_count.split(" [")[0]
            
            # Query function to get the count for each direction
            def query_direction_counts(conn, selected_criteria, selected_method):
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT direction, COUNT(paragraph) as count
                    FROM energy_data
                    WHERE criteria = ? AND energy_method = ? AND paragraph IS NOT NULL AND paragraph != '' AND paragraph != '0' AND paragraph != '0.0' AND status NOT IN ("pending", "rejected")
                    GROUP BY direction
                ''', (selected_criteria, selected_method))
                return dict(cursor.fetchall())

            # Reset selected_direction when criteria or method changes
            new_criteria = selected_criteria_with_count.split(" [")[0] if selected_criteria_with_count != "Select a determinant" else None
            new_method = selected_method_with_count.split(" [")[0] if selected_method_with_count != "Select an output" else None

            # Reset selected_direction and rerun if criteria or method has changed
            if new_criteria != st.session_state.get("selected_criteria"):
                st.session_state.selected_criteria = new_criteria
                st.session_state.selected_method = None
                st.rerun()
            elif new_method != st.session_state.get("selected_method"):
                st.session_state.selected_method = new_method
                st.rerun()

            # Ensure criteria and method are selected before showing the direction choice
            if st.session_state.selected_method:
                # Fetch counts for each direction
                direction_counts = query_direction_counts(conn, st.session_state.selected_criteria, st.session_state.selected_method)
                increase_count = direction_counts.get("Increase", 0)
                decrease_count = direction_counts.get("Decrease", 0)

                # Display radio buttons with counts, without default selection
                selected_direction = st.radio(
                    "Please select the direction of the relationship",
                    [f"Increase [{increase_count}]", f"Decrease [{decrease_count}]"],
                    index=None,  # No preselection
                    key="main_direction_radio"  # Unique key
                )

            # NEW SIMPLIFIED FILTERS - Only Scale and Dominant Climate
            if st.session_state.selected_method and selected_direction:
                # Get available options with error handling
                try:
                    scale_options = query_scale_options(conn)
                    dominant_climate_options = query_dominant_climate_options(conn)
                except Exception as e:
                    st.warning("Some filter data is not available yet. Please import location and climate data first.")
                    scale_options = []
                    dominant_climate_options = []

                # Filter out "Awaiting data" from scale options
                scale_options = [option for option in scale_options if option != "Awaiting data"]

                # Create columns for filters
                col1, col2 = st.columns(2)

                with col1:
                    # Scale filter - Single select dropdown
                    if scale_options:
                        # Initialize session state for scale
                        if 'selected_scale' not in st.session_state:
                            st.session_state.selected_scale = "All"
                        
                        scale_options_with_all = ["All"] + scale_options
                        
                        selected_scale = st.selectbox(
                            "Filter by Scale",
                            options=scale_options_with_all,
                            index=scale_options_with_all.index(st.session_state.selected_scale),
                            key="scale_select"
                        )
                        
                        # Update session state and apply filter logic
                        if selected_scale != st.session_state.selected_scale:
                            st.session_state.selected_scale = selected_scale
                            st.rerun()
                        
                        selected_scales = [selected_scale] if selected_scale != "All" else None
                    else:
                        st.info("No scale data available")
                        selected_scales = None

                with col2:
                # Climate filter - with colored glyphs (no redundant preview)
                    if dominant_climate_options:
                        if 'selected_climate' not in st.session_state:
                            st.session_state.selected_climate = "All"
                        
                        # Create options list with colored display
                        climate_options_with_all = ["All"] + [formatted for formatted, color in dominant_climate_options]
                        
                        selected_climate = st.selectbox(
                            "Filter by Climate",
                            options=climate_options_with_all,
                            index=climate_options_with_all.index(st.session_state.selected_climate),
                            key="climate_select_simple"
                        )
                        
                        if selected_climate != st.session_state.selected_climate:
                            st.session_state.selected_climate = selected_climate
                            st.rerun()
                        
                        # Extract just the climate code for filtering
                        if selected_climate != "All":
                            climate_code = selected_climate.split(" - ")[0].replace("🟦 ", "").replace("🟥 ", "").replace("🟧 ", "").replace("🟨 ", "").replace("🟩 ", "").replace("🟪 ", "").replace("⬛ ", "").replace("⬜ ", "") if " - " in selected_climate else selected_climate
                            selected_dominant_climates = [climate_code]
                        else:
                            selected_dominant_climates = None
                    else:
                        st.info("No climate data available")
                        selected_dominant_climates = None

                    #logic for scale
                    paragraphs = []

                # Only query if we have all required selections
                if (st.session_state.selected_criteria and 
                    st.session_state.selected_method and 
                    selected_direction):
                    
                    # Extract just the direction without the count
                    clean_direction = selected_direction.split(" [")[0] if selected_direction else None
                    
                    # Apply "All" logic for scale
                    if selected_scales and "All" in selected_scales:
                        selected_scales = None
                    
                    # Query paragraphs with simplified filters
                    paragraphs = query_paragraphs(
                        conn, 
                        st.session_state.selected_criteria, 
                        st.session_state.selected_method, 
                        clean_direction,
                        selected_scales,           # Scale filter
                        selected_dominant_climates # Dominant climate only
                    )
                
                # Display results or warning
                if paragraphs:
                    if len(paragraphs) == 1:
                        st.markdown(f"<p><b>The following study shows that an increase (or presence) in {st.session_state.selected_criteria} leads to <i>{'higher' if selected_direction == 'Increase' else 'lower'}</i> {st.session_state.selected_method}.</b></p>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<p><b>The following studies show that an increase (or presence) in {st.session_state.selected_criteria} leads to <i>{'higher' if selected_direction == 'Increase' else 'lower'}</i> {st.session_state.selected_method}.</b></p>", unsafe_allow_html=True)

                    for count, (para_id, para_text) in enumerate(paragraphs, start=1):
                        if st.session_state.user_role == "admin":
                            new_text = st.text_area(f"Edit text for record {para_id}", value=para_text, key=f"main_edit_{para_id}")
                            col1, col2 = st.columns([1, 4])
                            with col1:
                                if st.button("Save changes", key=f"main_save_btn_{para_id}"):
                                    admin_actions(conn, para_id, new_text=new_text)
                                    st.rerun()
                            with col2:
                                if st.session_state.get(f"main_confirm_delete_{para_id}", False):
                                    st.warning(f"Are you sure you want to delete record {para_id}?")
                                    col_yes, col_no = st.columns(2)
                                    with col_yes:
                                        if st.button("Yes", key=f"main_confirm_yes_{para_id}"):
                                            admin_actions(conn, para_id, delete=True)
                                            st.session_state[f"main_confirm_delete_{para_id}"] = False
                                            st.rerun()
                                    with col_no:
                                        if st.button("Cancel", key=f"main_confirm_no_{para_id}"):
                                            st.session_state[f"main_confirm_delete_{para_id}"] = False
                                            st.rerun()
                                else:
                                    if st.button("Delete", key=f"main_delete_btn_{para_id}"):
                                        st.session_state[f"main_confirm_delete_{para_id}"] = True
                                        st.rerun()
                        else:
                            st.markdown(f"**Result {count}:**<br>{para_text}", unsafe_allow_html=True)
                else:
                    st.warning(f"No studies have been reported for an increase (or presence) in {st.session_state.selected_criteria} leading to {'higher' if selected_direction == 'Increase' else 'lower'} {st.session_state.selected_method}.")

                # Add New Record Section
                if st.session_state.logged_in and selected_direction is not None:
                    if not st.session_state.get("show_new_record_form", False):
                        if st.button("Add New Record", key="main_add_new_record"):
                            st.session_state.show_new_record_form = True

                    if st.session_state.get("show_new_record_form", False):
                        new_paragraph = st.text_area(
                            f"Add new record for {st.session_state.selected_criteria} and {st.session_state.selected_method} ({selected_direction})",
                            key="main_new_paragraph"
                        )
                        
                        if st.button("Save", key="main_save_new_record"):
                            if new_paragraph.strip() and selected_direction:
                                cursor = conn.cursor()
                                cursor.execute('''
                                    INSERT INTO energy_data (criteria, energy_method, direction, paragraph, status, user)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                ''', (st.session_state.selected_criteria, st.session_state.selected_method, selected_direction, new_paragraph, "pending", st.session_state.current_user))
                                conn.commit()
                                st.success("New record submitted successfully. Status: pending verification")
                                
                                st.session_state.show_new_record_form = False
                                time.sleep(2)                                  
                                st.rerun()
                            else:
                                st.warning("Please select a direction and ensure the record is not empty before saving.")

                # st.image("bubblechart_placeholder.png")
                # st.caption("Bubble chart visualizing studied determinants, energy outputs, and the direction of their relationships based on the literature.")


def render_contribute_tab():
    """Render the Contribute tab content"""
    st.title("We're making it better.")
    whats_next_html = ("""
    Future updates will include new features like filters for climate and scale (urban vs. national) to fine-tune recommendations.</p> <strong>Contribute to the mission.</strong>
    Log in or sign up to add your studies or references, sharing determinants, energy outputs, and their relationships. After review, your contributions will enhance the database, helping us grow this resource for urban planners, developers, and policymakers.</p>
    Let's work together to optimize macro-scale energy use and create sustainable cities. <br><strong>Dive in, explore, and start contributing today.</strong>"""
    )
    st.markdown(whats_next_html, unsafe_allow_html=True)
    
    if st.session_state.logged_in:
        contribute()
    else:
        render_login_signup_forms()

def render_login_signup_forms():
    """Render login and signup forms with unique keys"""
    login_tab, signup_tab = st.tabs(["Login", "Sign Up"])
    
    with login_tab:
        username = st.text_input("Username", placeholder="Enter your username", key="main_login_username")
        password = st.text_input("Password", type="password", placeholder="Enter your password", key="main_login_password")
        if st.button("Login", key="main_login_button"):
            conn = sqlite3.connect("my_database.db")
            cursor = conn.cursor()
            cursor.execute("SELECT password, role FROM users WHERE username = ?", (username,))
            user = cursor.fetchone()
            conn.close()

            # FIX: Check if user exists before trying to access it
            if user and bcrypt.checkpw(password.encode('utf-8'), user[0]):
                st.session_state.logged_in = True
                st.session_state.current_user = username
                st.session_state.user_role = user[1]
                st.success(f"Welcome, {username}!")
                st.rerun()
            else:
                st.error("Invalid username or password.")
    
    with signup_tab:
        username = st.text_input("Username", placeholder="Enter your username", key="main_signup_username")
        password = st.text_input("Password", type="password", placeholder="Enter your password", key="main_signup_password")
        if st.button("Sign Up", key="main_signup_button"):
            if username and password:
                hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
                try:
                    # Create LOCAL connection like working file
                    conn = sqlite3.connect("my_database.db")
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO users (username, password, role)
                        VALUES (?, ?, 'user')
                    ''', (username, hashed_password))
                    conn.commit()
                    conn.close()
                    st.success("Account created successfully!")
                except sqlite3.IntegrityError:
                    st.error("Username already exists.")
            else:
                st.error("Please fill out all fields.")

def render_admin_sidebar():
    """Render admin-specific sidebar"""
    st.sidebar.header("Admin Dashboard")
    welcome_admin_dashboard = f"""As Admin you can Add and Edit or 
    Delete existing records under the SpatialBuild Energy tab.<br>
    You can accept or reject new user submissions under the Review Pending Contributions tab. <br>
    New records and unlisted determinant energy output types can be added to the dataset under the contribute tab.<br>
    You can also remove and re-import location, climate and scale data from your excel file."""
    st.sidebar.write(welcome_admin_dashboard, unsafe_allow_html=True)
    
    if st.sidebar.button("logout"):
        logout()
        st.rerun()

def render_user_sidebar():
    """Render regular user sidebar"""
    st.sidebar.header(f"Welcome back {st.session_state.current_user}")
    welcome_user_dashboard = f"As a logged in user you can add your findings to the dataset under the contribute tab.<br>1. Select the relevant determinant.<br>2. Select energy output.<br>3. Select the relationship direction.<br>4. Add your entry and click Save.<br>Your entry will be submitted pending verification.<br>If your study references new or unlisted determinant/energy output types you can add them by choosing Add new determinant/Add new energy output."
    st.sidebar.write(welcome_user_dashboard, unsafe_allow_html=True)
    
    if st.sidebar.button("logout"):
        logout()
        st.rerun()

def render_guest_sidebar():
    """Render sidebar for non-logged in users"""
    st.sidebar.header("Welcome to SpatialBuild Energy")
    guest_info = "Log in or sign up to contribute to our database of energy studies and help build sustainable cities."
    st.sidebar.write(guest_info, unsafe_allow_html=True)

# MAIN APP LAYOUT - CLEAN AND ORGANIZED
if st.session_state.logged_in:
    if st.session_state.current_user == "admin":
        # Admin view
        tab_labels = ["SpatialBuild Energy", "Contribute", "Edit/Review"]
        tabs = st.tabs(tab_labels)
        tab0, tab1, tab2 = tabs
        
        with tab0:
            render_main_tab()
        
        with tab1:
            render_contribute_tab()
        
        with tab2:
            admin_dashboard()
        
        render_admin_sidebar()

    else:  
        # Regular user view
        tab_labels = ["SpatialBuild Energy", "Contribute", "Your Contributions"]
        tabs = st.tabs(tab_labels)
        tab0, tab1, tab2 = tabs
        
        with tab0:
            render_main_tab()
        
        with tab1:
            render_contribute_tab()
        
        with tab2:
            user_dashboard()
        
        render_user_sidebar()

else:  
    # Not logged in view
    tab_labels = ["SpatialBuild Energy", "Contribute"]
    tabs = st.tabs(tab_labels)
    tab0, tab1 = tabs
    
    with tab0:
        render_main_tab()
    
    with tab1:
        render_contribute_tab()
    
    render_guest_sidebar()

# Footer (only once)
footer_html = """
    <style>
    .custom_footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: #010101;
        color: grey;
        text-align: center;
        padding: 5px;
    }
    </style>
    <div class="custom_footer">
        <p style='font-size:12px;'>If your study, or a study you are aware of, suggests any of these relationships are currently missing from the database, please email the study to ssk5573@psu.edu.<br> Your contribution will help further develop and improve this tool.</p>
    </div>
"""
st.markdown(footer_html, unsafe_allow_html=True)

conn.close()
