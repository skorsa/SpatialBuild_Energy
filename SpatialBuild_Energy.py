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
    st.session_state.current_user = None 
    st.session_state.selected_criteria = None
if 'selected_method' not in st.session_state:
    st.session_state.selected_method = None
if 'show_new_record_form' not in st.session_state:
    st.session_state.show_new_record_form = False
if "user_role" not in st.session_state:
    st.session_state.user_role = None
if "match_page" not in st.session_state:
    st.session_state.match_page = 0
if "unmatched_page" not in st.session_state:
    st.session_state.unmatched_page = 0
if "uploaded_excel_file" not in st.session_state:
    st.session_state.uploaded_excel_file = None
if "current_excel_df" not in st.session_state:
    st.session_state.current_excel_df = None
if "selected_quality_filter" not in st.session_state:
    st.session_state.selected_quality_filter = ["exact_match", "strong_match", "strong_match_90pct", "good_match"]

# ADD THIS FOR EDIT FUNCTIONALITY:
if "admin_editing_record_id" not in st.session_state:
    st.session_state.admin_editing_record_id = None    

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
        # Add scale and climate fields before the save button
        st.markdown("---")
        st.subheader("Additional Information (Optional)")

        col_scale, col_climate = st.columns(2)

        with col_scale:
            scale_options = query_dynamic_scale_options(conn)
            selected_scale = st.selectbox(
                "Scale",
                options=["Select scale"] + scale_options + ["Add new scale"],
                key="contribute_scale"
            )
            
            new_scale = ""
            if selected_scale == "Add new scale":
                new_scale = st.text_input("Enter new scale", key="contribute_new_scale")

        with col_climate:
            climate_options_data = query_dominant_climate_options(conn)
            climate_options = [formatted for formatted, color in climate_options_data]
            selected_climate = st.selectbox(
                "Climate",
                options=["Select climate"] + climate_options + ["Add new climate"],
                key="contribute_climate"
            )
            
            new_climate = ""
            if selected_climate == "Add new climate":
                new_climate = st.text_input("Enter new climate code", key="contribute_new_climate")

        # Location field
        location = st.text_input("Location (optional)", key="contribute_location", 
                                placeholder="e.g., United States, Europe, Specific city/region")

        st.markdown("---")

        # In the save section, make sure you're using st.session_state.current_user:
        if st.button("Save", key="save_new_record"):
            # Save record only if text is provided
            if new_paragraph.strip():
                cursor = conn.cursor()

                # Prepare scale and climate values
                final_scale = new_scale if selected_scale == "Add new scale" else selected_scale
                final_climate = new_climate if selected_climate == "Add new climate" else selected_climate
                
                # Clean climate code if it's formatted
                if final_climate and " - " in final_climate:
                    final_climate = final_climate.split(" - ")[0]
                    # Remove emoji if present
                    final_climate = ''.join([c for c in final_climate if c.isalnum()])

                # Save the record
                cursor.execute('''
                    INSERT INTO energy_data (criteria, energy_method, direction, paragraph, status, user, scale, climate, location)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    new_determinant or st.session_state.selected_determinant_choice,
                    new_energy_output or st.session_state.selected_energy_output_choice,
                    st.session_state.selected_selected_direction,
                    new_paragraph,
                    "pending",
                    st.session_state.current_user,
                    final_scale if final_scale != "Select scale" else "Awaiting data",
                    final_climate if final_climate != "Select climate" else "Awaiting data",
                    location if location else None
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
                possible_scale_cols = ['Scale', 'scale', 'Scale (Coverage)', 'Scale. (Neighbourhood (rural, urban), Regional, National and State,)']
                
                
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
    """Clear all climate, Location and scale data and reset to defaults"""
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
        st.success("✅ All imported data cleared and reset! (Climate, Location, Scale)")
        
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
    Enhanced Admin function: Import Excel and auto-match studies using only study titles
    """
    try:
        # Read Excel file
        df = pd.read_excel(uploaded_file, sheet_name=0)
        
        # Find study column (flexible naming)
        study_column = None
        for col in df.columns:
            if any(keyword in col.lower() for keyword in ['study', 'title', 'paper', 'reference']):
                study_column = col
                break
        
        if not study_column:
            st.error("No study/title column found in the uploaded file. Available columns: " + ", ".join(df.columns))
            return [], []
        
        # Get study names
        study_names = df[study_column].dropna().unique()
        
        matched_records = []
        unmatched_studies = []
        
        st.info(f"🔍 Matching {len(study_names)} studies in database using enhanced title matching...")
        
        progress_bar = st.progress(0)
        status_text = st.empty()

        cursor = conn.cursor()
        
        for i, study_name in enumerate(study_names):
            if pd.isna(study_name) or not study_name:
                continue
                
            # Clean and normalize the study name
            clean_study = preprocess_study_name(study_name)
            
            status_text.text(f"Searching: {clean_study[:50]}...")
            
            # Try multiple matching strategies
            matches = find_study_matches_by_title(cursor, clean_study, study_name)
            
            if matches:
                for match_data in matches:
                    matched_records.append({
                        'excel_study': study_name,  # Original name
                        'excel_study_normalized': clean_study,
                        'db_record_id': match_data['record_id'],
                        'matching_paragraph': match_data['paragraph'],
                        'criteria': match_data['criteria'],
                        'energy_method': match_data['energy_method'],
                        'direction': match_data['direction'],
                        'scale': match_data['scale'],
                        'climate': match_data['climate'],
                        'location': match_data['location'],
                        'confidence': match_data['confidence'],
                        'match_position': match_data['match_position'],
                        'match_percentage': match_data['match_percentage'],
                        'matching_text': match_data['matching_text']
                    })
            else:
                unmatched_studies.append({
                    'study_name': study_name,
                    'normalized_name': clean_study,
                    'reason': 'No database matches found with enhanced title matching'
                })
            
            progress_bar.progress((i + 1) / len(study_names))
        
        progress_bar.empty()
        status_text.empty()
        
        # Sort matches by confidence
        confidence_order = {
            'exact_match': 0,
            'strong_match': 1,
            'good_match': 2,
            'partial_match': 3,
            'fuzzy_match': 4
        }
        
        matched_records.sort(key=lambda x: (
            confidence_order.get(x['confidence'], 999),
            -x.get('match_percentage', 0)
        ))
        
        return matched_records, unmatched_studies
        
    except Exception as e:
        st.error(f"Error during import: {e}")
        import traceback
        st.error(f"Detailed error: {traceback.format_exc()}")
        return [], []

def preprocess_study_name(study_name):
    """Clean and normalize study names for better matching"""
    if pd.isna(study_name) or not study_name:
        return ""
    
    # Convert to string and strip
    clean_name = str(study_name).strip()
    
    # Remove extra whitespace and newlines
    clean_name = ' '.join(clean_name.split())
    
    # Remove common prefixes/suffixes that might interfere with matching
    prefixes_to_remove = ['study of', 'analysis of', 'investigation of', 'the ']
    for prefix in prefixes_to_remove:
        if clean_name.lower().startswith(prefix):
            clean_name = clean_name[len(prefix):].strip()
    
    return clean_name

def convert_urls_to_links(text):
    """
    Convert URLs in text to clickable HTML links
    Includes: http/https URLs, www URLs, doi.org links, and DOI numbers
    """
    if not text:
        return text
    
    # Replace newlines with HTML line breaks
    text = text.replace('\n', '<br>')
    
    # URL patterns to match
    patterns = [
        # Standard http/https URLs
       # (r'(https?://\S+)', r'<a href="\1" target="_blank" style="color: #0066cc; text-decoration: none;">\1</a>'),
        # www URLs (without http)
       # (r'\b(www\.\S+)\b', r'<a href="http://\1" target="_blank" style="color: #0066cc; text-decoration: none;">\1</a>'),
        # doi.org links
        (r'\b(doi\.org/\S+)\b', r'<a href="https://\1" target="_blank" style="color: #0066cc; text-decoration: none;">\1</a>'),
        # DOI numbers (10.xxx/xxx)
      #  (r'\b(10\.\d{4,9}/[-._;()/:A-Z0-9]+)\b', r'<a href="https://doi.org/\1" target="_blank" style="color: #0066cc; text-decoration: none;">\1</a>')
    ]
    
    # Apply each pattern
    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    return text

def display_study_content(paragraph, record_id):
    """Simple display of study content"""
    # Convert URLs to clickable links
    paragraph_with_links = convert_urls_to_links(paragraph)
    
    #st.text_area(f"Study Content", value=paragraph, height=150, key=f"content_{record_id}", disabled=False)
    # # Display in a styled container
    st.markdown(
        f'''
        <div style="
            border: 1px solid #e0e0e0;
            padding: 15px;
            border-radius: 8px;
            background-color: #f8f9fa;
            max-height: 250px;
            overflow-y: auto;
            font-family: Arial, sans-serif;
            line-height: 1.5;
            font-size: 14px;
        ">
            {paragraph_with_links}
        </div>
        ''',
        unsafe_allow_html=True
    )
    

def find_study_matches_by_title(cursor, clean_study, original_study):
    """Find matches using multiple title-based strategies"""
    matches = []
    
    # Strategy 1: Exact substring match
    exact_matches = find_exact_substring_matches(cursor, clean_study, original_study)
    matches.extend(exact_matches)
    
    if not matches:
        # Strategy 2: Significant portion matching (80% of title)
        significant_matches = find_significant_portion_matches(cursor, clean_study, original_study)
        matches.extend(significant_matches)
    
    if not matches:
        # Strategy 3: Keyword matching with significant words
        keyword_matches = find_keyword_based_matches(cursor, clean_study, original_study)
        matches.extend(keyword_matches)
    
    return matches

def find_exact_substring_matches(cursor, clean_study, original_study):
    """Find exact or near-exact substring matches"""
    matches = []
    
    # Try different variations of the study title
    search_terms = [
        clean_study,
        original_study,  # Try original first
    ]
    
    # Remove duplicates
    search_terms = list(dict.fromkeys([term for term in search_terms if term and len(term) > 10]))
    
    for term in search_terms:
        try:
            cursor.execute('''
                SELECT id, paragraph, criteria, energy_method, direction, scale, climate, location
                FROM energy_data 
                WHERE LOWER(paragraph) LIKE LOWER(?)
            ''', (f'%{term}%',))
            
            results = cursor.fetchall()
            
            for result in results:
                record_id, paragraph, criteria, energy_method, direction, scale, climate, location = result
                paragraph_lower = paragraph.lower()
                term_lower = term.lower()
                
                if term_lower in paragraph_lower:
                    match_position = paragraph_lower.find(term_lower)
                    match_percentage = (len(term) / len(paragraph)) * 100
                    
                    # Determine confidence level
                    if match_percentage > 30:
                        confidence = 'exact_match'
                    elif match_percentage > 15:
                        confidence = 'strong_match'
                    else:
                        confidence = 'good_match'
                    
                    matches.append({
                        'record_id': record_id,
                        'paragraph': paragraph,
                        'criteria': criteria,
                        'energy_method': energy_method,
                        'direction': direction,
                        'scale': scale,
                        'climate': climate,
                        'location': location,
                        'confidence': confidence,
                        'match_position': match_position,
                        'match_percentage': match_percentage,
                        'matching_text': term
                    })
        except Exception as e:
            # Skip this term if it causes SQL errors
            continue
    
    return matches

def find_significant_portion_matches(cursor, clean_study, original_study):
    """Match using significant portions of the study title"""
    matches = []
    
    # Try different portions of the title
    portions_to_try = []
    
    # If title is long, try first 80% and last 80%
    if len(clean_study) > 30:
        portion_80 = int(len(clean_study) * 0.8)
        portions_to_try.append(clean_study[:portion_80])
        portions_to_try.append(clean_study[-portion_80:])
    
    # Try first 30 characters (common for citations)
    if len(clean_study) > 30:
        portions_to_try.append(clean_study[:30])
    
    # Try last 30 characters
    if len(clean_study) > 30:
        portions_to_try.append(clean_study[-30:])
    
    # Remove duplicates and short portions
    portions_to_try = list(dict.fromkeys([p for p in portions_to_try if p and len(p) >= 15]))
    
    for portion in portions_to_try:
        try:
            cursor.execute('''
                SELECT id, paragraph, criteria, energy_method, direction, scale, climate, location
                FROM energy_data 
                WHERE LOWER(paragraph) LIKE LOWER(?)
            ''', (f'%{portion}%',))
            
            results = cursor.fetchall()
            
            for result in results:
                record_id, paragraph, criteria, energy_method, direction, scale, climate, location = result
                paragraph_lower = paragraph.lower()
                portion_lower = portion.lower()
                
                if portion_lower in paragraph_lower:
                    match_position = paragraph_lower.find(portion_lower)
                    match_percentage = (len(portion) / len(clean_study)) * 100
                    
                    matches.append({
                        'record_id': record_id,
                        'paragraph': paragraph,
                        'criteria': criteria,
                        'energy_method': energy_method,
                        'direction': direction,
                        'scale': scale,
                        'climate': climate,
                        'location': location,
                        'confidence': 'strong_match',
                        'match_position': match_position,
                        'match_percentage': match_percentage,
                        'matching_text': portion
                    })
        except Exception as e:
            # Skip this portion if it causes SQL errors
            continue
    
    return matches

def find_keyword_based_matches(cursor, clean_study, original_study):
    """Match based on significant keywords from the title"""
    matches = []
    
    # Extract meaningful keywords (excluding common words)
    keywords = extract_significant_keywords(clean_study)
    
    if len(keywords) >= 2:  # Need at least 2 significant keywords
        # Try different combinations - SIMPLIFIED to avoid complex SQL building
        search_strategies = [
            keywords[:3],  # First 3 keywords only
        ]
        
        for strategy_keywords in search_strategies:
            if len(strategy_keywords) < 2:
                continue
                
            # Use a simpler approach - search for each keyword individually and combine results
            potential_matches = {}
            
            for keyword in strategy_keywords:
                try:
                    cursor.execute('''
                        SELECT id, paragraph, criteria, energy_method, direction, scale, climate, location
                        FROM energy_data 
                        WHERE LOWER(paragraph) LIKE LOWER(?)
                    ''', (f'%{keyword}%',))
                    
                    results = cursor.fetchall()
                    
                    for result in results:
                        record_id, paragraph, criteria, energy_method, direction, scale, climate, location = result
                        
                        if record_id not in potential_matches:
                            potential_matches[record_id] = {
                                'record': result,
                                'keywords_found': 0,
                                'paragraph': paragraph
                            }
                        
                        potential_matches[record_id]['keywords_found'] += 1
                except Exception as e:
                    # Skip this keyword if it causes SQL errors
                    continue
            
            # Only keep records that found multiple keywords
            for record_id, match_data in potential_matches.items():
                if match_data['keywords_found'] >= 2:  # At least 2 keywords found
                    record_id, paragraph, criteria, energy_method, direction, scale, climate, location = match_data['record']
                    confidence_score = (match_data['keywords_found'] / len(strategy_keywords)) * 100
                    
                    if confidence_score >= 60:
                        matches.append({
                            'record_id': record_id,
                            'paragraph': paragraph,
                            'criteria': criteria,
                            'energy_method': energy_method,
                            'direction': direction,
                            'scale': scale,
                            'climate': climate,
                            'location': location,
                            'confidence': 'good_match',
                            'match_position': 0,
                            'match_percentage': confidence_score,
                            'matching_text': f"Keywords: {', '.join(strategy_keywords)}"
                        })
    
    return matches

def extract_significant_keywords(text):
    """Extract meaningful keywords, excluding common words"""
    # Common words to exclude
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 
        'with', 'by', 'as', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'this', 'that', 'these', 'those', 'it', 'its', 'they', 'their', 'them',
        'from', 'into', 'through', 'during', 'before', 'after', 'above', 'below'
    }
    
    # Split into words and filter
    words = text.lower().split()
    significant_words = [
        word for word in words 
        if (len(word) > 3 and word not in stop_words and word.isalpha())
    ]
    
    return significant_words

def display_unmatched_study_detailed(unmatched, index, conn):
    """Display individual unmatched study with detailed analysis"""
    with st.expander(f"❌ {unmatched['study_name'][:80]}{'...' if len(unmatched['study_name']) > 80 else ''}", expanded=False):
        col_study, col_analysis, col_actions = st.columns([3, 2, 1])
        
        with col_study:
            st.write(f"**Study:** {unmatched['study_name']}")
            st.write(f"**Length:** {len(unmatched['study_name'])} characters")
            st.write(f"**Reason:** {unmatched.get('reason', 'No match found')}")
            
            # Show study characteristics
            characteristics = []
            if len(unmatched['study_name']) < 20:
                characteristics.append("🔴 Very short")
            if len(unmatched['study_name']) > 100:
                characteristics.append("🔴 Very long")
            if unmatched['study_name'].isupper():
                characteristics.append("🔴 All uppercase")
            if any(char in unmatched['study_name'] for char in ['@', '#', '$', '%', '&', '*', '+', '=']):
                characteristics.append("🔴 Special chars")
            if "  " in unmatched['study_name']:
                characteristics.append("🔴 Multiple spaces")
            if any(char.isdigit() for char in unmatched['study_name']):
                characteristics.append("🔴 Contains numbers")
            
            if characteristics:
                st.write("**Issues:**", ", ".join(characteristics))
        
        with col_analysis:
            # Quick analysis
            suggestions = analyze_study_name(unmatched['study_name'])
            st.write("**Suggestions:**")
            for suggestion in suggestions:
                st.write(f"• {suggestion}")
            
            # Keyword analysis
            keywords = [word for word in unmatched['study_name'].split() if len(word) > 4]
            if keywords:
                st.write(f"**Keywords ({len(keywords)}):** {', '.join(keywords[:5])}")
        
        with col_actions:
            # Quick actions
            if st.button("🔍 Search DB", key=f"search_db_{index}"):
                similar = quick_database_search(conn, unmatched['study_name'])
                if similar:
                    st.success(f"Found {len(similar)} potential matches")
                    for sim in similar[:2]:
                        st.write(f"- ID {sim['id']}: {sim['paragraph'][:80]}...")
                else:
                    st.error("No similar records found")
            
            if st.button("📝 Copy", key=f"copy_{index}"):
                st.code(unmatched['study_name'])
            
            # Manual match attempt
            if st.button("🎯 Manual Match", key=f"manual_{index}"):
                attempt_manual_match(unmatched, conn)

def display_unmatched_analysis(unmatched_studies):
    """Display comprehensive analysis of unmatched studies"""
    st.subheader("📊 Unmatched Studies Analysis")
    
    # Length analysis
    lengths = [len(study['study_name']) for study in unmatched_studies]
    avg_length = sum(lengths) / len(lengths) if lengths else 0
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Average Length", f"{avg_length:.1f} chars")
    with col2:
        st.metric("Shortest", f"{min(lengths) if lengths else 0} chars")
    with col3:
        st.metric("Longest", f"{max(lengths) if lengths else 0} chars")
    
    # Common issues breakdown
    issues = {
        "Very Short (<20 chars)": len([s for s in unmatched_studies if len(s['study_name']) < 20]),
        "Very Long (>100 chars)": len([s for s in unmatched_studies if len(s['study_name']) > 100]),
        "Contains Special Chars": len([s for s in unmatched_studies if any(c in s['study_name'] for c in ['@', '#', '$', '%', '&', '*', '+', '='])]),
        "All UPPERCASE": len([s for s in unmatched_studies if s['study_name'].isupper()]),
        "Multiple Spaces": len([s for s in unmatched_studies if "  " in s['study_name']]),
        "Contains Numbers": len([s for s in unmatched_studies if any(char.isdigit() for char in s['study_name'])]),
        "Few Keywords (<2)": len([s for s in unmatched_studies if len([word for word in s['study_name'].split() if len(word) > 4]) < 2])
    }
    
    st.write("**Common Issues Found:**")
    for issue, count in issues.items():
        if count > 0:
            percentage = (count / len(unmatched_studies)) * 100
            st.write(f"• {issue}: {count} studies ({percentage:.1f}%)")
    
    # Length distribution
    show_length_distribution(unmatched_studies)

def test_study_matching(conn, test_studies):
    """Test matching for sample studies to debug issues"""
    st.subheader("🧪 Matching Test Results")
    
    for study in test_studies:
        st.write(f"**Testing:** {study['study_name']}")
        
        # Try different matching strategies
        cursor = conn.cursor()
        
        # Strategy 1: Exact match
        cursor.execute('''
            SELECT id, paragraph FROM energy_data 
            WHERE paragraph LIKE ? 
            LIMIT 1
        ''', (f'%{study["study_name"]}%',))
        exact_result = cursor.fetchone()
        
        # Strategy 2: First 30 characters
        if len(study["study_name"]) > 30:
            partial = study["study_name"][:30]
            cursor.execute('''
                SELECT id, paragraph FROM energy_data 
                WHERE paragraph LIKE ? 
                LIMIT 1
            ''', (f'%{partial}%',))
            partial_result = cursor.fetchone()
        else:
            partial_result = None
        
        # Strategy 3: Keyword matching
        keywords = [word for word in study["study_name"].split() if len(word) > 5]
        keyword_results = []
        for keyword in keywords[:3]:
            cursor.execute('''
                SELECT id, paragraph FROM energy_data 
                WHERE paragraph LIKE ? 
                LIMIT 1
            ''', (f'%{keyword}%',))
            result = cursor.fetchone()
            if result:
                keyword_results.append((keyword, result))
        
        # Display results
        if exact_result:
            st.success(f"✅ Exact match found: ID {exact_result[0]}")
        elif partial_result:
            st.info(f"🟡 Partial match found: ID {partial_result[0]}")
        elif keyword_results:
            st.warning(f"🟠 Keyword matches: {[kw for kw, _ in keyword_results]}")
        else:
            st.error("❌ No matches found with any strategy")
        
        st.write("---")

def attempt_manual_match(unmatched_study, conn):
    """Allow manual matching for difficult cases"""
    st.info(f"**Manual match for:** {unmatched_study['study_name']}")
    
    search_term = st.text_input("Search database manually", 
                               value=unmatched_study['study_name'],
                               key=f"manual_search_{unmatched_study['study_name'][:10]}")
    
    if search_term:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, paragraph FROM energy_data 
            WHERE paragraph LIKE ? 
            LIMIT 10
        ''', (f'%{search_term}%',))
        results = cursor.fetchall()
        
        if results:
            st.success(f"Found {len(results)} potential matches")
            for record_id, paragraph in results:
                with st.expander(f"Record ID: {record_id}"):
                    st.text_area("Content", value=paragraph, height=100, key=f"manual_content_{record_id}")
                    if st.button(f"Select this match", key=f"select_manual_{record_id}"):
                        # You can implement manual match confirmation here
                        st.success(f"Manually matched to record {record_id}")
        else:
            st.error("No matches found with manual search")

def display_admin_matching_review(matched_records, unmatched_studies, excel_df=None):
    """
    Display the matching review interface for admin with unmatched studies inspection
    """
    
    # Match quality statistics
    exact_count = len([m for m in matched_records if m['confidence'] == 'exact_match'])
    strong_count = len([m for m in matched_records if m['confidence'] == 'strong_match'])
    good_count = len([m for m in matched_records if m['confidence'] == 'good_match'])
    
    # Display confidence breakdown
    st.write("**Match Quality Breakdown:**")
    st.write(f"🟢 Exact Match: {exact_count}")
    st.write(f"🟡 Strong Match: {strong_count}")
    st.write(f"🟠 Good Match: {good_count}")
    st.write(f"❌ No Match: {len(unmatched_studies)}")
    
    # Quality filter
    st.write("**Filter by Match Quality:**")
    quality_options = ['exact_match', 'strong_match', 'good_match']
    
    quality_descriptions = {
        'exact_match': '🟢 Exact Match',
        'strong_match': '🟡 Strong Match',
        'good_match': '🟠 Good Match'
    }
    
    selected_qualities = st.multiselect(
        "Select confidence levels to show:",
        options=quality_options,
        format_func=lambda x: quality_descriptions.get(x, x),
        default=quality_options,  # Show all by default
        key="simple_quality_filter"
    )
    
    # Filter matches by quality
    filtered_matches = [m for m in matched_records if m['confidence'] in selected_qualities]

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
    
    # PAGINATION SETTINGS - FIXED: Initialize match_page if not exists
    if "match_page" not in st.session_state:
        st.session_state.match_page = 0
        
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
        
        with st.expander(f"{'🟢' if match['confidence'] == 'exact_match' else '🟡' if match['confidence'] == 'strong_match' else '🟠'} Match {global_index + 1} | Record ID: {match['db_record_id']}", expanded=True):
            
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
                if match['confidence'] == 'exact_match':
                    st.success(f"✅ **Exact match found!** (Record ID: {match['db_record_id']})")
                elif match['confidence'] == 'strong_match':
                    st.info(f"🟡 **Strong match found** (Record ID: {match['db_record_id']})")
                else:
                    st.info(f"🟠 **Good match found** (Record ID: {match['db_record_id']})")
                
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
            default_value = match['confidence'] == 'exact_match'  # Auto-confirm exact matches
            
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
                    'strong_match': "🟡 Strong Match",
                    'good_match': "🟠 Good Match"
                }
                st.info(confidence_badge.get(match['confidence'], "Unknown"))
            
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

    # UNMATCHED STUDIES SECTION - NEW AND IMPROVED
    if unmatched_studies:
        st.markdown("---")
        st.subheader("❌ Unmatched Studies")
        st.warning(f"**{len(unmatched_studies)} studies couldn't be automatically matched**")
        
        # Analysis of unmatched studies
        with st.expander("📊 Unmatched Studies Analysis", expanded=False):
            # Basic statistics
            col1, col2, col3 = st.columns(3)
            with col1:
                avg_length = sum(len(study['study_name']) for study in unmatched_studies) / len(unmatched_studies)
                st.metric("Average Title Length", f"{avg_length:.1f} chars")
            with col2:
                shortest = min(len(study['study_name']) for study in unmatched_studies)
                st.metric("Shortest Title", f"{shortest} chars")
            with col3:
                longest = max(len(study['study_name']) for study in unmatched_studies)
                st.metric("Longest Title", f"{longest} chars")
            
            # Common issues
            st.write("**Common Issues:**")
            very_short = len([s for s in unmatched_studies if len(s['study_name']) < 20])
            very_long = len([s for s in unmatched_studies if len(s['study_name']) > 200])
            all_upper = len([s for s in unmatched_studies if s['study_name'].isupper()])
            
            if very_short > 0:
                st.write(f"• Very short titles (<20 chars): {very_short}")
            if very_long > 0:
                st.write(f"• Very long titles (>200 chars): {very_long}")
            if all_upper > 0:
                st.write(f"• All uppercase titles: {all_upper}")
        
        # Display unmatched studies with detailed inspection
        st.write("**Inspect Unmatched Studies:**")
        
        # Search and filter for unmatched studies
        col_search, col_filter = st.columns(2)
        with col_search:
            unmatched_search = st.text_input("Search unmatched studies", placeholder="Enter keyword...", key="unmatched_search")
        
        with col_filter:
            unmatched_filter = st.selectbox("Filter by length", 
                                          ["All", "Very Short (<20 chars)", "Short (20-50)", "Medium (50-100)", "Long (100-200)", "Very Long (>200)"],
                                          key="unmatched_filter")
        
        # Filter unmatched studies
        filtered_unmatched = unmatched_studies
        
        if unmatched_search:
            filtered_unmatched = [s for s in filtered_unmatched if unmatched_search.lower() in s['study_name'].lower()]
        
        if unmatched_filter != "All":
            if unmatched_filter == "Very Short (<20 chars)":
                filtered_unmatched = [s for s in filtered_unmatched if len(s['study_name']) < 20]
            elif unmatched_filter == "Short (20-50)":
                filtered_unmatched = [s for s in filtered_unmatched if 20 <= len(s['study_name']) < 50]
            elif unmatched_filter == "Medium (50-100)":
                filtered_unmatched = [s for s in filtered_unmatched if 50 <= len(s['study_name']) < 100]
            elif unmatched_filter == "Long (100-200)":
                filtered_unmatched = [s for s in filtered_unmatched if 100 <= len(s['study_name']) < 200]
            elif unmatched_filter == "Very Long (>200)":
                filtered_unmatched = [s for s in filtered_unmatched if len(s['study_name']) >= 200]
        
        st.write(f"**Showing {len(filtered_unmatched)} of {len(unmatched_studies)} unmatched studies**")
        
        # Display each unmatched study with analysis
        for i, unmatched in enumerate(filtered_unmatched):
            with st.expander(f"❌ {unmatched['study_name'][:80]}{'...' if len(unmatched['study_name']) > 80 else ''}", expanded=False):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.write(f"**Study Title:** {unmatched['study_name']}")
                    st.write(f"**Length:** {len(unmatched['study_name'])} characters")
                    st.write(f"**Normalized:** {unmatched.get('normalized_name', 'N/A')}")
                    st.write(f"**Reason:** {unmatched.get('reason', 'No match found')}")
                    
                    # Quick analysis
                    st.write("**Quick Analysis:**")
                    if len(unmatched['study_name']) < 20:
                        st.write("• 🔴 Title is very short - may need manual matching")
                    if len(unmatched['study_name']) > 200:
                        st.write("• 🔴 Title is very long - try matching with first 100 characters")
                    if unmatched['study_name'].isupper():
                        st.write("• 🔴 Title is all uppercase - try converting to normal case")
                    
                    # Show first 100 chars of normalized version for manual search
                    st.write("**Try searching for this in database:**")
                    search_suggestion = unmatched.get('normalized_name', unmatched['study_name'])[:100]
                    st.code(search_suggestion)
                
                with col2:
                    # Quick actions
                    if st.button("🔍 Search DB", key=f"search_unmatched_{i}"):
                        # Quick database search for similar content
                        similar_results = quick_database_search_unmatched(conn, unmatched['study_name'])
                        if similar_results:
                            st.success(f"Found {len(similar_results)} potential matches")
                            for sim in similar_results[:3]:
                                st.write(f"- ID {sim['id']}: {sim['paragraph'][:80]}...")
                        else:
                            st.error("No similar records found")
                    
                    if st.button("📝 Copy", key=f"copy_unmatched_{i}"):
                        st.code(unmatched['study_name'])
        
        # Export unmatched studies
        st.markdown("---")
        if st.button("📤 Export Unmatched Studies to CSV", key="export_unmatched_button"):
            export_unmatched_studies(filtered_unmatched)

def quick_database_search_unmatched(conn, study_name):
    """Quick search for similar content in database for unmatched studies"""
    cursor = conn.cursor()
    
    # Try different search strategies for unmatched studies
    search_terms = [
        study_name[:30],  # First 30 chars
        ' '.join(study_name.split()[:5]),  # First 5 words
        ' '.join([word for word in study_name.split() if len(word) > 5][:3]),  # Long words only
    ]
    
    results = []
    for term in search_terms:
        if len(term) > 5:  # Only search meaningful terms
            try:
                cursor.execute('''
                    SELECT id, paragraph FROM energy_data 
                    WHERE paragraph LIKE ? 
                    LIMIT 3
                ''', (f'%{term}%',))
                results.extend(cursor.fetchall())
            except:
                continue
    
    # Remove duplicates
    unique_results = []
    seen_ids = set()
    for id, paragraph in results:
        if id not in seen_ids:
            unique_results.append({'id': id, 'paragraph': paragraph})
            seen_ids.add(id)
    
    return unique_results

def export_unmatched_studies(unmatched_studies):
    """Export unmatched studies to CSV"""
    import pandas as pd
    from datetime import datetime
    
    # Create DataFrame
    df_unmatched = pd.DataFrame(unmatched_studies)
    
    # Download button
    csv = df_unmatched.to_csv(index=False)
    st.download_button(
        label="Download Unmatched Studies CSV",
        data=csv,
        file_name=f"unmatched_studies_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
        key="download_unmatched_full"
    )
        
def find_similar_studies(unmatched_studies):
    """Group similar unmatched studies together"""
    from difflib import SequenceMatcher
    
    similar_groups = []
    processed = set()
    
    for i, study1 in enumerate(unmatched_studies):
        if i in processed:
            continue
            
        group = [study1]
        processed.add(i)
        
        for j, study2 in enumerate(unmatched_studies[i+1:], i+1):
            if j in processed:
                continue
                
            similarity = SequenceMatcher(None, study1['study_name'].lower(), study2['study_name'].lower()).ratio()
            if similarity > 0.7:  # 70% similarity threshold
                group.append(study2)
                processed.add(j)
        
        if len(group) > 1:
            similar_groups.append(group)
    
    return similar_groups


def display_similar_studies(similar_groups):
    """Display groups of similar unmatched studies"""
    if similar_groups:
        st.success(f"Found {len(similar_groups)} groups of similar studies:")
        for i, group in enumerate(similar_groups):
            with st.expander(f"Group {i+1} - {len(group)} similar studies"):
                for study in group:
                    st.write(f"- {study['study_name']}")
    else:
        st.info("No similar study groups found.")

def display_database_sampling(conn):
    """Show a sample of database content for comparison"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT paragraph FROM energy_data 
        WHERE LENGTH(paragraph) > 50 
        ORDER BY RANDOM() 
        LIMIT 5
    ''')
    samples = cursor.fetchall()
    
    st.info("**Random database content samples:**")
    for i, (sample,) in enumerate(samples):
        with st.expander(f"Sample {i+1}"):
            st.text(sample[:500] + "..." if len(sample) > 500 else sample)

def display_common_issues(unmatched_studies):
    """Analyze and display common issues with unmatched studies"""
    issues = {
        "Very Long Names (>100 chars)": [],
        "Very Short Names (<20 chars)": [],
        "Contains Special Characters": [],
        "All UPPERCASE": [],
        "Contains Numbers": []
    }
    
    for study in unmatched_studies:
        name = study['study_name']
        
        if len(name) > 100:
            issues["Very Long Names (>100 chars)"].append(study)
        if len(name) < 20:
            issues["Very Short Names (<20 chars)"].append(study)
        if any(char in name for char in ['@', '#', '$', '%', '&', '*', '+', '=']):
            issues["Contains Special Characters"].append(study)
        if name.isupper():
            issues["All UPPERCASE"].append(study)
        if any(char.isdigit() for char in name):
            issues["Contains Numbers"].append(study)
    
    st.warning("**Common Issues Found:**")
    for issue_type, studies in issues.items():
        if studies:
            with st.expander(f"{issue_type} ({len(studies)} studies)"):
                for study in studies[:5]:  # Show first 5
                    st.write(f"- {study['study_name']}")
                if len(studies) > 5:
                    st.write(f"... and {len(studies) - 5} more")

def analyze_study_name(study_name):
    """Provide analysis suggestions for a study name"""
    suggestions = []
    
    if len(study_name) > 100:
        suggestions.append("Study name is very long - consider shortening")
    if len(study_name) < 20:
        suggestions.append("Study name is very short - may need more context")
    if study_name.isupper():
        suggestions.append("Study name is all uppercase - try converting to normal case")
    if any(char in study_name for char in ['@', '#', '$', '%', '&', '*', '+', '=']):
        suggestions.append("Contains special characters - remove for better matching")
    if "  " in study_name:
        suggestions.append("Contains multiple spaces - normalize spacing")
    if study_name.count('.') > 3:
        suggestions.append("Many abbreviations - might affect matching")
    
    if not suggestions:
        suggestions.append("No obvious issues detected")
    
    return suggestions

def quick_database_search(conn, study_name):
    """Quick search for similar content in database"""
    cursor = conn.cursor()
    
    # Try different search strategies
    search_terms = [
        study_name[:30],  # First 30 chars
        study_name[-30:], # Last 30 chars
        ' '.join(study_name.split()[:5]),  # First 5 words
        ' '.join(study_name.split()[-5:]), # Last 5 words
    ]
    
    results = []
    for term in search_terms:
        if len(term) > 5:  # Only search meaningful terms
            cursor.execute('''
                SELECT id, paragraph FROM energy_data 
                WHERE paragraph LIKE ? 
                LIMIT 3
            ''', (f'%{term}%',))
            results.extend(cursor.fetchall())
    
    # Remove duplicates
    unique_results = []
    seen_ids = set()
    for id, paragraph in results:
        if id not in seen_ids:
            unique_results.append({'id': id, 'paragraph': paragraph})
            seen_ids.add(id)
    
    return unique_results
    
def extract_climate_data(climate_text):
    """
    Extract dominant climate code from climate text
    Format examples:
    - "United Arab Emirates (UAE), Downtown Abu Dhabi | BWh (Hot desert)" -> "BWh"
    - "USA | Cfa (Humid subtropical) dominant, also Dfa, Dfb, BWh" -> "Cfa"
    - "Cfa (Humid subtropical)" -> "Cfa"
    - "Cfa, Dfa" -> "Cfa"
    """
    if not climate_text or pd.isna(climate_text) or str(climate_text).strip() == '':
        return None, []
    
    climate_text = str(climate_text).strip()
    
    # Define valid Köppen climate codes we want to extract
    valid_climate_codes = [
        'Af', 'Am', 'Aw', 'BWh', 'BWk', 'BSh', 'BSk', 
        'Cfa', 'Cfb', 'Cfc', 'Csa', 'Csb', 
        'Dfa', 'Dfb', 'Dfc', 'Dfd', 'ET', 'EF'
    ]
    
    # Method 1: Extract after "| " (most common format)
    if '| ' in climate_text:
        # Get the part after the pipe
        after_pipe = climate_text.split('| ')[1]
        # Look for the first valid climate code
        for code in valid_climate_codes:
            if code in after_pipe:
                dominant_climate = code
                # Also extract any other valid codes for multi-climate
                multi_climates = [c for c in valid_climate_codes if c in after_pipe]
                return dominant_climate, multi_climates
    
    # Method 2: Look for any valid climate codes in the text
    found_codes = [code for code in valid_climate_codes if code in climate_text]
    if found_codes:
        # Use the first found code as dominant
        dominant_climate = found_codes[0]
        return dominant_climate, found_codes
    
    # Method 3: If no valid codes found, return the original text as dominant
    return climate_text, [climate_text]


def show_length_distribution(unmatched_studies):
    """Show length distribution of unmatched studies"""
    lengths = [len(study['study_name']) for study in unmatched_studies]
    
    if lengths:
        # Create a simple histogram using value_counts
        length_ranges = {
            "<20": len([l for l in lengths if l < 20]),
            "20-50": len([l for l in lengths if 20 <= l < 50]),
            "50-100": len([l for l in lengths if 50 <= l < 100]),
            "100-200": len([l for l in lengths if 100 <= l < 200]),
            ">200": len([l for l in lengths if l >= 200]),
        }
        
        st.write("**Length Distribution:**")
        for range_name, count in length_ranges.items():
            if count > 0:
                percentage = (count / len(lengths)) * 100
                st.write(f"• {range_name} chars: {count} studies ({percentage:.1f}%)")

def display_unmatched_study(study, index):
    """Display individual unmatched study with analysis"""
    with st.expander(f"❌ {study['study_name'][:80]}{'...' if len(study['study_name']) > 80 else ''}", expanded=False):
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.write(f"**Study:** {study['study_name']}")
            st.write(f"**Length:** {len(study['study_name'])} characters")
            st.write(f"**Reason:** {study.get('reason', 'No match found')}")
            
            # Quick analysis
            analysis = analyze_study_name(study['study_name'])
            st.write("**Analysis:**")
            for item in analysis:
                st.write(f"• {item}")
        
        with col2:
            # Quick actions
            if st.button("🔍 Search DB", key=f"search_db_{index}"):
                similar = quick_database_search(conn, study['study_name'])
                if similar:
                    st.success(f"Found {len(similar)} potential matches")
                    for sim in similar[:2]:
                        st.write(f"- ID {sim['id']}: {sim['paragraph'][:80]}...")
                else:
                    st.error("No similar records found")
            
            if st.button("📝 Copy", key=f"copy_{index}"):
                st.code(study['study_name'])

def export_filtered_unmatched(filtered_unmatched):
    """Export filtered unmatched studies"""
    df_filtered = pd.DataFrame(filtered_unmatched)
    csv = df_filtered.to_csv(index=False)
    st.download_button(
        label="Download Filtered Unmatched CSV",
        data=csv,
        file_name=f"unmatched_studies_filtered_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
        key="download_filtered_unmatched"
    )

# Also need to update the process_confirmed_matches function:
def process_confirmed_matches(confirmed_matches, excel_df):
    """Process the user-confirmed matches with all data fields"""
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
            # Extract all data from Excel row with flexible column names
            location = ''
            climate_text = ''
            scale = ''
            building_use = ''
            approach = ''
            sample_size = ''
            
            # Find all columns
            for col in excel_match.index:
                col_lower = str(col).lower()
                if 'location' in col_lower or 'site' in col_lower or 'region' in col_lower:
                    location = str(excel_match[col]) if pd.notna(excel_match[col]) else ''
                elif 'climate' in col_lower:
                    climate_text = str(excel_match[col]) if pd.notna(excel_match[col]) else ''
                elif 'scale' in col_lower:
                    scale = str(excel_match[col]) if pd.notna(excel_match[col]) else ''
                elif 'building' in col_lower and ('use' in col_lower or 'type' in col_lower):
                    building_use = str(excel_match[col]) if pd.notna(excel_match[col]) else ''
                elif 'approach' in col_lower or 'method' in col_lower:
                    approach = str(excel_match[col]) if pd.notna(excel_match[col]) else ''
                elif 'sample' in col_lower or 'n' == col_lower:
                    sample_size = str(excel_match[col]) if pd.notna(excel_match[col]) else ''
            
            # Extract climate code using new function
def extract_just_climate_code(climate_text):
    """
    Extract ONLY the climate code from climate text, preserving ORIGINAL case
    Format examples:
    - "Ilam, Iran. | Csa (Mediterranean)" -> "Csa"
    - "Beijing, china | Dwa (Monsoon-influenced hot-summer humid continental)" -> "Dwa"
    - "Csa (Mediterranean)" -> "Csa"
    - "Csa" -> "Csa"
    - "United Arab Emirates (UAE), Downtown Abu Dhabi | BWh (Hot desert)" -> "BWh"
    """
    if not climate_text or pd.isna(climate_text) or str(climate_text).strip() == '':
        return None
    
    climate_text = str(climate_text).strip()
    
    # If there's a pipe "|" in the text, take ONLY the part after it
    if '|' in climate_text:
        # Split by pipe and take the second part
        parts = climate_text.split('|')
        if len(parts) > 1:
            climate_text = parts[1].strip()
    
    # Now extract just the climate code - preserve original case
    import re
    
    # Look for patterns like "Csa (Mediterranean)" or just "Csa"
    # Match 2-3 letters where first is uppercase, rest can be uppercase or lowercase
    match = re.search(r'([A-Z][A-Za-z]{1,2})', climate_text)
    
    if match:
        climate_code = match.group(1)
        # PRESERVE ORIGINAL CASE - don't modify it!
        return climate_code
    
    return None

def add_new_columns_to_database():
    """Add new columns to the database if they don't exist"""
    global conn
    cursor = conn.cursor()
    
    print("🔧 Adding new columns to database...")
    
    # List of new columns to add
    new_columns = [
        ('building_use', 'TEXT'),
        ('approach', 'TEXT'),
        ('sample_size', 'TEXT')
    ]
    
    for column_name, column_type in new_columns:
        try:
            cursor.execute(f"ALTER TABLE energy_data ADD COLUMN {column_name} {column_type}")
            print(f"✅ Added '{column_name}' column to energy_data table")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"ℹ️ '{column_name}' column already exists")
            else:
                print(f"⚠️ Error with {column_name} column: {e}")
    
    conn.commit()
    print("🔧 Database schema update completed")

# Run this function once to add the new columns
#add_new_columns_to_database()

def extract_climate_code(climate_text):
    """
    Extract just the 3-letter climate code from climate text
    Format examples:
    - "Ilam, Iran. | Csa (Mediterranean)" -> "Csa"
    - "Beijing, china | Dwa (Monsoon-influenced hot-summer humid continental)" -> "Dwa"
    - "Csa (Mediterranean)" -> "Csa"
    - "Csa" -> "Csa"
    """
    if not climate_text or pd.isna(climate_text) or str(climate_text).strip() == '':
        return None
    
    climate_text = str(climate_text).strip()
    
    # If there's a pipe "|" in the text, take the part after it
    if '|' in climate_text:
        # Split by pipe and take the second part
        parts = climate_text.split('|')
        if len(parts) > 1:
            climate_text = parts[1].strip()
    
    # Now extract just the climate code (first word/letters before space or parenthesis)
    # Climate codes are typically 3 letters like Csa, Dwa, etc.
    import re
    
    # Look for patterns like "Csa (Mediterranean)" or just "Csa"
    # Match 2-3 uppercase letters possibly followed by lowercase letters
    match = re.search(r'([A-Z][A-Za-z]{1,2})', climate_text)
    
    if match:
        climate_code = match.group(1)
        # Ensure it's uppercase (in case there are lowercase letters)
        climate_code = climate_code.upper()
        return climate_code
    
    return climate_text  # Return original if no pattern found

def extract_just_climate_code(climate_text):
    """
    Extract ONLY the climate code from climate text, preserving original case
    Format examples:
    - "Ilam, Iran. | Csa (Mediterranean)" -> "Csa"
    - "Beijing, china | Dwa (Monsoon-influenced hot-summer humid continental)" -> "Dwa"
    - "Csa (Mediterranean)" -> "Csa"
    - "Csa" -> "Csa"
    - "United Arab Emirates (UAE), Downtown Abu Dhabi | BWh (Hot desert)" -> "BWh"
    """
    if not climate_text or pd.isna(climate_text) or str(climate_text).strip() == '':
        return None
    
    climate_text = str(climate_text).strip()
    
    # If there's a pipe "|" in the text, take ONLY the part after it
    if '|' in climate_text:
        # Split by pipe and take the second part
        parts = climate_text.split('|')
        if len(parts) > 1:
            climate_text = parts[1].strip()
    
    # Now extract just the climate code
    import re
    
    # Look for patterns like "Csa (Mediterranean)" or just "Csa"
    # Match 2-3 letters where first is uppercase, rest can be uppercase or lowercase
    # Climate codes: Af, Am, Aw, BWh, BWk, BSh, BSk, Cfa, Cfb, Cfc, Csa, Csb, Dfa, Dfb, Dfc, Dfd, ET, EF
    match = re.search(r'([A-Z][A-Za-z]{1,2})', climate_text)
    
    if match:
        climate_code = match.group(1)
        # PRESERVE ORIGINAL CASE - don't modify it!
        return climate_code
    
    return None

def import_location_climate_data_unique():
    global conn
    st.subheader("Import Location, Climate & Scale Data")
    
    # Add reset button section at the top
    col1, col2 = st.columns(2)
    
    with col1:
        st.warning("⚠️ **Reset Options**")
    with col2:
        if st.button("🗑️ Clear All, Climate, Location and Scale Data", key="clear_location_data_btn", use_container_width=True):
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
                possible_scale_cols = ['Scale (Coverage)', 'Scale', 'scale', 'Scale. (Neighbourhood (rural, urban), Regional, National and State,)', 'Scale (coverage)']
                possible_building_use_cols = ['Building Use', 'building_use', 'Building_Use', 'Building Type', 'building_type']
                possible_approach_cols = ['Approach', 'approach', 'Methodology', 'methodology', 'Method', 'method']
                possible_sample_size_cols = ['Sample Size', 'sample_size', 'Sample_Size', 'Sample', 'sample', 'N']
                
                # Find matching columns
                for col in df.columns:
                    col_clean = str(col).strip()
                    col_lower = col_clean.lower()
                    
                    if any(study_col in col_lower for study_col in ['study', 'title', 'paper']):
                        column_mapping[col] = 'study'
                    elif any(loc_col in col_lower for loc_col in ['location', 'site', 'region']):
                        column_mapping[col] = 'location'
                    elif any(climate_col in col_lower for climate_col in ['climate', 'climate zone']):
                        column_mapping[col] = 'climate'
                    elif any(scale_col in col_lower for scale_col in ['scale']):
                        column_mapping[col] = 'scale'
                    elif any(building_use_col in col_lower for building_use_col in ['building use', 'building_type']):
                        column_mapping[col] = 'building_use'
                    elif any(approach_col in col_lower for approach_col in ['approach', 'methodology', 'method']):
                        column_mapping[col] = 'approach'
                    elif any(sample_size_col in col_lower for sample_size_col in ['sample size', 'sample', 'n']):
                        column_mapping[col] = 'sample_size'
                
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
                st.write(f"**Columns found:** {list(column_mapping.values())}")
                
                # Debug: Show what columns are actually being mapped
                st.write("**Column mapping details:**")
                for original, mapped in column_mapping.items():
                    st.write(f"  - '{original}' → '{mapped}'")
                
                # Show sample of extracted climate codes
                if 'climate' in df.columns:
                    sample_climates = df['climate'].head(5).apply(extract_just_climate_code)
                    st.write("**Sample climate code extraction (first 5):**")
                    for i, (original, extracted) in enumerate(zip(df['climate'].head(5), sample_climates)):
                        st.write(f"  {i+1}. '{original}' → '{extracted}'")
                
                # Import button with unique key
                if st.button("Import Data to Database", type="primary", key="import_button_unique"):
                    import_progress = st.progress(0)
                    status_text = st.empty()
                    
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
                        cursor.execute('''
                            SELECT id, paragraph FROM energy_data 
                            WHERE paragraph LIKE ? 
                            OR paragraph LIKE ?
                            LIMIT 1
                        ''', (f'%{study_name}%', f'%{study_name[:100]}%'))
                        
                        result = cursor.fetchone()
                        
                        if result:
                            record_id, paragraph = result
                            
                            # Get location from Location column (not from climate text)
                            location_value = str(row.get('location', '')).strip()
                            
                            # Extract JUST the climate code from climate text
                            climate_text = str(row.get('climate', '')).strip()
                            climate_code = extract_just_climate_code(climate_text)
                            
                            # Get scale value
                            scale_value = str(row.get('scale', '')).strip()
                            
                            # Debug info for first few records
                            if index < 3:
                                st.sidebar.write(f"**Record {record_id}:**")
                                st.sidebar.write(f"  Study: '{study_name[:30]}...'")
                                st.sidebar.write(f"  Location column value: '{location_value}'")
                                st.sidebar.write(f"  Climate column text: '{climate_text}'")
                                st.sidebar.write(f"  Extracted climate code: '{climate_code}'")
                                st.sidebar.write(f"  Scale value: '{scale_value}'")
                                st.sidebar.write("---")
                            
                            # Update the record with all available data
                            cursor.execute('''
                                UPDATE energy_data 
                                SET location = ?, 
                                    climate = ?, 
                                    scale = ?,
                                    building_use = ?,
                                    approach = ?,
                                    sample_size = ?
                                WHERE id = ?
                            ''', (
                                location_value,  # From Location column
                                climate_code if climate_code else '',  # Proper Köppen format
                                scale_value,
                                str(row.get('building_use', '')).strip(),
                                str(row.get('approach', '')).strip(),
                                str(row.get('sample_size', '')).strip(),
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
                    
                    # Show summary of what was imported
                    col_summary1, col_summary2, col_summary3, col_summary4 = st.columns(4)
                    with col_summary1:
                        location_count = df['location'].notna().sum() if 'location' in df.columns else 0
                        st.metric("Location", location_count)
                    with col_summary2:
                        climate_count = df['climate'].notna().sum() if 'climate' in df.columns else 0
                        st.metric("Climate", climate_count)
                    with col_summary3:
                        scale_count = df['scale'].notna().sum() if 'scale' in df.columns else 0
                        st.metric("Scale", scale_count)
                    with col_summary4:
                        building_use_count = df['building_use'].notna().sum() if 'building_use' in df.columns else 0
                        st.metric("Building Use", building_use_count)
                    
                    # Show location import summary
                    if 'location' in df.columns:
                        unique_locations = df['location'].dropna().unique()
                        st.write(f"**Unique locations imported:** {len(unique_locations)}")
                        with st.expander("View sample locations"):
                            for loc in unique_locations[:10]:
                                st.write(f"- {loc}")
                    
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
            import traceback
            st.error(f"Detailed error: {traceback.format_exc()}")
            st.write("Please check the file format and ensure it contains the correct sheet name.")
      

def reset_location_climate_scale_data():
    """Clear all imported data and reset to defaults"""
    global conn
    cursor = conn.cursor()
    try:
        # Clear ALL imported data and reset to default values
        cursor.execute('''
            UPDATE energy_data 
            SET location = NULL,
                climate = NULL,
                scale = 'Awaiting data',
                building_use = NULL,
                approach = NULL,
                sample_size = NULL
        ''')
        
        conn.commit()
        st.success("✅ All imported data cleared and reset! (Location, Climate, Scale, Building Use, Approach, Sample Size)")
        
        # Show comprehensive statistics
        cursor.execute("SELECT COUNT(*) FROM energy_data WHERE climate IS NULL")
        climate_cleared_count = cursor.fetchone()[0]
               
        cursor.execute("SELECT COUNT(*) FROM energy_data WHERE scale = 'Awaiting data'")
        scale_reset_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM energy_data WHERE building_use IS NULL")
        building_use_cleared = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM energy_data WHERE approach IS NULL")
        approach_cleared = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM energy_data WHERE sample_size IS NULL")
        sample_size_cleared = cursor.fetchone()[0]
        
        st.info(f"""
        **Reset Statistics:**
        - Records with climate cleared: {climate_cleared_count}
        - Records with scale reset: {scale_reset_count}
        - Records with building use cleared: {building_use_cleared}
        - Records with approach cleared: {approach_cleared}
        - Records with sample size cleared: {sample_size_cleared}
        """)
        
    except Exception as e:
        st.error(f"Error resetting data: {str(e)}")

    # Refresh to show updated data
    time.sleep(2)
    st.rerun()

# Also need to update the process_confirmed_matches function to handle new columns:
def process_confirmed_matches(confirmed_matches, excel_df):
    """Process the user-confirmed matches with all data fields"""
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
            # Extract all data from Excel row with flexible column names
            location = ''
            climate_text = ''
            scale = ''
            building_use = ''
            approach = ''
            sample_size = ''
            
            # Find all columns
            for col in excel_match.index:
                col_lower = str(col).lower()
                if 'location' in col_lower or 'site' in col_lower or 'region' in col_lower:
                    location = str(excel_match[col]) if pd.notna(excel_match[col]) else ''
                elif 'climate' in col_lower:
                    climate_text = str(excel_match[col]) if pd.notna(excel_match[col]) else ''
                elif 'scale' in col_lower:  # Removed the 'coverage' exclusion
                    scale = str(excel_match[col]) if pd.notna(excel_match[col]) else ''
                elif 'building' in col_lower and ('use' in col_lower or 'type' in col_lower):
                    building_use = str(excel_match[col]) if pd.notna(excel_match[col]) else ''
                elif 'approach' in col_lower or 'method' in col_lower:
                    approach = str(excel_match[col]) if pd.notna(excel_match[col]) else ''
                elif 'sample' in col_lower or 'n' == col_lower:
                    sample_size = str(excel_match[col]) if pd.notna(excel_match[col]) else ''
            
            # FIX: Use extract_just_climate_code() which preserves case
            climate_code = extract_just_climate_code(climate_text)
            
            # Update the database record with all fields
            cursor.execute('''
                UPDATE energy_data 
                SET location = ?, 
                    climate = ?, 
                    scale = ?,
                    building_use = ?,
                    approach = ?,
                    sample_size = ?
                WHERE id = ?
            ''', (
                location, 
                climate_code if climate_code else '',  # This preserves original case
                scale,
                building_use,
                approach,
                sample_size,
                record_id
            ))
            
            updated_count += 1
            
            # Log the update for debugging
            st.sidebar.write(f"Record {record_id}:")
            st.sidebar.write(f"  Climate text: '{climate_text}'")
            st.sidebar.write(f"  Climate code: '{climate_code}'")
            st.sidebar.write(f"  Scale: '{scale}'")
            
        else:
            not_found_in_excel.append(excel_study)
    
    conn.commit()
    
    if not_found_in_excel:
        st.warning(f"⚠️ {len(not_found_in_excel)} studies not found in Excel file")
    
    return updated_count
    

def manage_scale_climate_data():
    if "admin_editing_record_id" not in st.session_state:
        st.session_state.admin_editing_record_id = None
    global conn
    st.subheader("Edit Records - Full Record Management")
    cursor = conn.cursor()
    
    # Get all column names to make it dynamic
    cursor.execute("PRAGMA table_info(energy_data)")
    columns_info = cursor.fetchall()
    column_names = [col[1] for col in columns_info]
    
    # Get dynamic options from database with error handling
    try:
        scale_options = query_scale_options_with_counts(conn)
        climate_options = query_climate_options_with_counts(conn)
    
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
        SELECT id, criteria, energy_method, direction, paragraph, user, status, scale, climate, location, 
            building_use, approach, sample_size
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
    selected_direction = None
    actual_method = None  # Initialize here to avoid UnboundLocalError

    # FILTER LAYOUT - Consistent with main app
    # Step 1: Determinant dropdown - full width
    selected_criteria = st.selectbox("Filter by Determinant", criteria_list, key="admin_edit_criteria")
    actual_criteria = selected_criteria.split(" [")[0] if selected_criteria != "All determinants" else None
    
    # Step 2: Energy Output dropdown - full width (only if determinant is selected)
    if actual_criteria:
        energy_method_counts = query_energy_method_counts(conn, actual_criteria)
        method_list = ["All outputs"] + [f"{method} [{count}]" for method, count in energy_method_counts]
        
        selected_method = st.selectbox("Filter by Energy Output", method_list, key="admin_edit_method")
        actual_method = selected_method.split(" [")[0] if selected_method != "All outputs" else None
        
        # Step 3: Direction radio buttons - full width (only if both determinant and method are selected)
        if actual_method:
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

            # Fetch counts for each direction
            direction_counts = query_direction_counts(conn, actual_criteria, actual_method)
            increase_count = direction_counts.get("Increase", 0)
            decrease_count = direction_counts.get("Decrease", 0)

            # Display radio buttons with counts
            selected_direction = st.radio(
                "Please select the direction of the relationship",
                [f"Increase [{increase_count}]", f"Decrease [{decrease_count}]"],
                index=None,  # No preselection
                key="admin_direction_radio"
            )
            
            # Step 4: Scale and Climate filters in 2 columns (only when direction is selected)
            if selected_direction:
                col_scale, col_climate = st.columns(2)
                
                with col_scale:
                    # Scale filter - with dynamic counts based on current search AND climate filter
                    if scale_options:
                        # Get current climate selection for scale counts
                        current_climate_filter = []
                        if 'admin_selected_climate' in st.session_state and st.session_state.admin_selected_climate != "All":
                            climate_code = st.session_state.admin_selected_climate.split(" - ")[0]
                            climate_code = ''.join([c for c in climate_code if c.isalnum()])
                            current_climate_filter = [climate_code]
                        
                        # Get scale options with counts filtered by current climate
                        scale_options_with_counts = query_scale_options_with_counts(
                            conn, 
                            actual_criteria, 
                            actual_method, 
                            selected_direction,  # Use selected direction
                            current_climate_filter  # Pass current climate filter
                        )
                        
                        if scale_options_with_counts:
                            # Initialize selected_scale in session state if not exists
                            if 'admin_selected_scale' not in st.session_state:
                                st.session_state.admin_selected_scale = "All"
                            
                            # Create options with counts
                            scale_options_formatted = ["All"] + [f"{scale} [{count}]" for scale, count in scale_options_with_counts]
                            
                            # Find the current index - preserve selection if it exists in new options
                            current_scale = st.session_state.admin_selected_scale
                            current_index = 0  # Default to "All"
                            
                            # Check if current selection exists in the new filtered options
                            if current_scale != "All":
                                # Extract just the scale name from the formatted option
                                if " [" in current_scale:
                                    current_scale_name = current_scale.split(" [")[0]
                                else:
                                    current_scale_name = current_scale
                                
                                # Look for this scale in the new options
                                for i, option in enumerate(scale_options_formatted):
                                    if option.startswith(current_scale_name + " [") or option == current_scale:
                                        current_index = i
                                        break
                                else:
                                    # If current selection not found, reset to "All"
                                    st.session_state.admin_selected_scale = "All"
                                    current_index = 0
                            else:
                                current_index = 0
                            
                            selected_scale = st.selectbox(
                                "Filter by Scale",
                                options=scale_options_formatted,
                                index=current_index,
                                key="admin_scale_filter"
                            )
                            
                            # Update session state only if selection actually changed
                            if selected_scale != st.session_state.admin_selected_scale:
                                st.session_state.admin_selected_scale = selected_scale
                                # Trigger rerun to update the other filter
                                st.rerun()
                            
                            # Extract just the scale name for filtering (remove count)
                            if selected_scale != "All":
                                scale_name = selected_scale.split(" [")[0]
                                selected_scales = [scale_name]
                            else:
                                selected_scales = None
                        else:
                            st.info("No scale data available for current selection")
                            selected_scales = None
                            st.session_state.admin_selected_scale = "All"
                    else:
                        st.info("No scale data")
                        selected_scales = None

                with col_climate:
                    # Climate filter - with dynamic counts based on current search AND scale filter
                    if climate_options:
                        # Get current scale selection for climate counts
                        current_scale_filter = []
                        if 'admin_selected_scale' in st.session_state and st.session_state.admin_selected_scale != "All":
                            scale_name = st.session_state.admin_selected_scale.split(" [")[0]
                            current_scale_filter = [scale_name]
                        
                        # Pass None for direction if it's not selected yet
                        current_direction = None
                        if selected_direction and selected_direction != "Select a direction":
                            current_direction = selected_direction
                        
                        # Get climate options with counts filtered by current scale
                        climate_options_with_counts = query_climate_options_with_counts(
                            conn, 
                            actual_criteria,  # This might be None
                            actual_method,    # This might be None  
                            current_direction,  # Pass None if not selected
                            current_scale_filter  # Pass current scale filter
                        )
                        
                        if climate_options_with_counts:
                            # Initialize selected_climate in session state if not exists
                            if 'admin_selected_climate' not in st.session_state:
                                st.session_state.admin_selected_climate = "All"
                            
                            # Create options with colored display and counts
                            climate_options_formatted = ["All"] + [formatted for formatted, color, count in climate_options_with_counts]
                            
                            # Find the current index - preserve selection if it exists in new options
                            current_climate = st.session_state.admin_selected_climate
                            current_index = 0  # Default to "All"
                            
                            # Check if current selection exists in the new filtered options
                            if current_climate != "All":
                                # Extract just the climate code from the formatted option
                                if " - " in current_climate:
                                    current_climate_code = current_climate.split(" - ")[0]
                                    # Remove emoji if present
                                    current_climate_code = ''.join([c for c in current_climate_code if c.isalnum()])
                                else:
                                    current_climate_code = current_climate
                                
                                # Look for this climate in the new options
                                for i, option in enumerate(climate_options_formatted):
                                    option_code = option.split(" - ")[0]
                                    option_code = ''.join([c for c in option_code if c.isalnum()])
                                    if option_code == current_climate_code:
                                        current_index = i
                                        break
                                else:
                                    # If current selection not found, reset to "All"
                                    st.session_state.admin_selected_climate = "All"
                                    current_index = 0
                            else:
                                current_index = 0
                            
                            selected_climate = st.selectbox(
                                "Filter by Climate",
                                options=climate_options_formatted,
                                index=current_index,
                                key="admin_climate_filter"
                            )
                            
                            # Update session state only if selection actually changed
                            if selected_climate != st.session_state.admin_selected_climate:
                                st.session_state.admin_selected_climate = selected_climate
                                # Trigger rerun to update the other filter
                                st.rerun()
                            
                            # Extract just the climate code for filtering
                            if selected_climate != "All":
                                # Remove the emoji, description, and count to get just the climate code
                                climate_code = selected_climate.split(" - ")[0]
                                # Remove any emoji characters and count
                                climate_code = ''.join([c for c in climate_code if c.isalnum()])
                                selected_climates = [climate_code]
                            else:
                                selected_climates = None
                        else:
                            st.info("No climate data available for current selection")
                            selected_climates = None
                            st.session_state.admin_selected_climate = "All"
                    else:
                        st.info("No climate data available")
                        selected_climates = None

    # Filter records in memory (only when all required selections are made)
    filtered_records = records
    if actual_criteria:
        filtered_records = [r for r in filtered_records if r[1] == actual_criteria]
    if actual_method:  # Now this variable is always defined
        filtered_records = [r for r in filtered_records if r[2] == actual_method]
    if selected_direction:
        clean_direction = selected_direction.split(" [")[0] if selected_direction else None
        filtered_records = [r for r in filtered_records if r[3] == clean_direction]
    if selected_scales:
        filtered_records = [r for r in filtered_records if r[7] in selected_scales]
    if selected_climates:
        # Case-insensitive comparison
        selected_climates_upper = [c.upper() for c in selected_climates]
        filtered_records = [r for r in filtered_records if r[8] and r[8].upper() in selected_climates_upper]

    # Only show results when we have the basic selections
    if actual_criteria and actual_method and selected_direction:
        st.write(f"**Showing {len(filtered_records)} approved records**")
    else:
        st.write("**Please select a determinant, energy output, and direction to see records**")
        filtered_records = []
    
    # [Rest of the function remains the same - display records, etc.]
    # Show data source info
    with st.expander("📊 Data Source Info", expanded=False):
        # Handle scale options format
        if scale_options:
            if isinstance(scale_options[0], tuple):
                scale_texts = [f"{scale} [{count}]" for scale, count in scale_options[:10]]
            else:
                scale_texts = scale_options[:10]
            st.write(f"**Dynamic Scale Options ({len(scale_options)}):** {', '.join(scale_texts)}{'...' if len(scale_options) > 10 else ''}")
        else:
            st.write("**Dynamic Scale Options (0):** No data available")
        
        # Handle climate options format
        if climate_options:
            if isinstance(climate_options[0], tuple):
                if len(climate_options[0]) == 3:
                    # New format with counts
                    climate_texts = [formatted for formatted, color, count in climate_options[:10]]
                else:
                    # Old format without counts
                    climate_texts = [formatted for formatted, color in climate_options[:10]]
            else:
                climate_texts = climate_options[:10]
            st.write(f"**Dynamic Climate Options ({len(climate_options)}):** {', '.join(climate_texts)}{'...' if len(climate_options) > 10 else ''}")
        else:
            st.write("**Dynamic Climate Options (0):** No data available")
        
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
    
    # DISPLAY RESULTS - Show study content directly in text fields
    for record in display_records:
        record_id, criteria, energy_method, direction, paragraph, user, status, scale, climate, location, building_use, approach, sample_size = record
        
        st.markdown("---")

        # Check if this record is being edited
        is_editing = st.session_state.admin_editing_record_id == record_id
        
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
                    new_direction = st.radio("Direction", ["Increase", "Decrease"], 
                                        index=0 if direction == "Increase" else 1,
                                        key=f"admin_direction_{record_id}", horizontal=True)
                    
                    # Scale (editable)
                    scale_options_list = ["Select scale"] + query_dynamic_scale_options(conn) + ["Add new scale"]
                    selected_scale = st.selectbox("Scale", 
                                                options=scale_options_list,
                                                index=scale_options_list.index(scale) if scale in scale_options_list else 0,
                                                key=f"admin_scale_{record_id}")
                    
                    new_scale = ""
                    if selected_scale == "Add new scale":
                        new_scale = st.text_input("Enter new scale", key=f"admin_new_scale_{record_id}")
                    
                    # Location (editable)
                    new_location = st.text_input("Location", value=location if location else "", 
                                               key=f"admin_location_{record_id}")
                
                with col2:
                    # Climate (editable)
                    climate_options_list = ["Select dominant climate"] + [formatted for formatted, color in query_dominant_climate_options(conn)] + ["Add new climate"]
                    
                    # Find current climate in options
                # Find current climate in options (without counts for display)
                current_climate_index = 0
                for i, opt in enumerate(climate_options_list):
                    if climate:
                        # Compare without counts for matching
                        opt_without_count = opt.split(" [")[0] if " [" in opt else opt
                        climate_clean = climate.split(" - ")[0] if " - " in climate else climate
                        if climate_clean in opt_without_count or climate in opt_without_count:
                            current_climate_index = i
                            break
                    
                    selected_climate = st.selectbox("Dominant Climate", 
                                                  options=climate_options_list,
                                                  index=current_climate_index,
                                                  key=f"admin_climate_{record_id}")
                    
                    new_climate = ""
                    if selected_climate == "Add new climate":
                        new_climate = st.text_input("Enter new climate code", key=f"admin_new_climate_{record_id}")
                    
                    # Building Use (editable)
                    new_building_use = st.text_input("Building Use", value=building_use if building_use else "", 
                                                   key=f"admin_building_use_{record_id}")
                    
                    # Approach (editable)
                    new_approach = st.text_input("Approach", value=approach if approach else "", 
                                               key=f"admin_approach_{record_id}")
                    
                    # Sample Size (editable)
                    new_sample_size = st.text_input("Sample Size", value=sample_size if sample_size else "", 
                                                  key=f"admin_sample_size_{record_id}")
                    
                    # Status (editable)
                    status_options = ["approved", "rejected", "pending"]
                    new_status = st.selectbox("Status", options=status_options,
                                           index=status_options.index(status) if status in status_options else 0,
                                           key=f"admin_status_{record_id}")
                
                # Paragraph content (larger area) - ALWAYS VISIBLE
                st.write("**Study Content:**")
                new_paragraph = st.text_area("Content", value=paragraph, height=150, key=f"admin_paragraph_{record_id}")
                
                # Save and Cancel buttons for individual record
                col_save, col_cancel = st.columns(2)
                with col_save:
                    if st.button("💾 Save This Record", key=f"admin_save_single_{record_id}", use_container_width=True, type="primary"):
                        # Prepare final values
                        final_scale = new_scale if selected_scale == "Add new scale" else (selected_scale if selected_scale != "Select scale" else scale)
                        final_climate = new_climate if selected_climate == "Add new climate" else (selected_climate if selected_climate != "Select climate" else climate)
                        
                        # Clean climate code if formatted
                        if final_climate and " - " in str(final_climate):
                            final_climate = final_climate.split(" - ")[0]
                            final_climate = ''.join([c for c in final_climate if c.isalnum()])
                        
                        # Save individual record to database
                        cursor_edit = conn.cursor()
                        cursor_edit.execute('''
                            UPDATE energy_data 
                            SET criteria = ?, energy_method = ?, direction = ?, paragraph = ?, 
                                scale = ?, climate = ?, location = ?, building_use = ?, approach = ?, 
                                sample_size = ?, status = ?
                            WHERE id = ?
                        ''', (
                            new_criteria,
                            new_energy_method, 
                            new_direction,
                            new_paragraph,
                            final_scale,
                            final_climate,
                            new_location,
                            new_building_use,
                            new_approach,
                            new_sample_size,
                            new_status,
                            record_id
                        ))
                        
                        conn.commit()
                        
                        st.session_state[f"admin_full_edit_{record_id}"] = False
                        st.success(f"✅ Record {record_id} updated successfully!")
                        time.sleep(1)
                        st.rerun()
                
                with col_cancel:
                    if st.button("❌ Cancel Edit", key=f"admin_cancel_single_{record_id}", use_container_width=True):
                        st.session_state[f"admin_full_edit_{record_id}"] = False
                        st.rerun()
                        
            else:
                # View Mode - Display all information clearly
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**Determinant:** {criteria}")
                    st.write(f"**Energy Output:** {energy_method}")
                    st.write(f"**Direction:** {direction}")
                    if location:
                        st.write(f"**Location:** {location}")
                    if building_use:
                        st.write(f"**Building Use:** {building_use}")
                    if approach:
                        st.write(f"**Approach:** {approach}")
                    if sample_size:
                        st.write(f"**Sample Size:** {sample_size}")
                
                with col2:
                    st.write(f"**Scale:** {scale}")
                    
                    if climate:
                        # Handle different climate option formats for display
                        formatted_climate_display = climate
                        if climate_options and isinstance(climate_options[0], tuple):
                            # Try to find the formatted version from climate_options
                            for option in climate_options:
                                if len(option) == 3:
                                    formatted, color_option, count = option
                                else:
                                    formatted, color_option = option
                                    
                                # Check if this formatted option matches our climate
                                climate_code_from_formatted = formatted.split(" - ")[0]
                                # Remove emoji to get just the code
                                climate_code_clean = ''.join([c for c in climate_code_from_formatted if c.isalnum()])
                                if climate_code_clean.upper() == climate.upper():
                                    # REMOVE COUNT FROM DISPLAY
                                    # Format without count: "🟦 Cfa - Humid Subtropical"
                                    # Split by " [" to remove count part
                                    if " [" in formatted:
                                        formatted_climate_display = formatted.split(" [")[0]
                                    else:
                                        formatted_climate_display = formatted
                                    break
                        
                        color = get_climate_color(climate)
                        st.markdown(f"**Climate:** <span style='background-color: {color}; padding: 2px 8px; border-radius: 10px; color: black;'>{formatted_climate_display}</span>", unsafe_allow_html=True)

                    st.write(f"**Status:** {status}")
                    st.write(f"**Submitted by:** {user}")
                
                # Study content - ALWAYS VISIBLE, not in expander
                st.write("**Study Content:**")
                display_study_content(paragraph, record_id)

    
    # Quick actions
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🔄 Refresh Data", key="admin_refresh_edit", use_container_width=True):
            st.rerun()
    with col2:
        if st.button("📊 Show Statistics", key="admin_stats_edit", use_container_width=True):
            # Calculate statistics
            awaiting_scale = len([r for r in records if r[7] in ["Awaiting data", "Not Specified", "", None] or not r[7]])
            awaiting_climate = len([r for r in records if r[8] in ["Awaiting data", "Not Specified", "", None] or not r[8]])
            awaiting_location = len([r for r in records if r[9] in ["", None] or not r[9]])
            awaiting_building_use = len([r for r in records if r[10] in ["", None] or not r[10]])
            awaiting_approach = len([r for r in records if r[11] in ["", None] or not r[11]])
            awaiting_sample_size = len([r for r in records if r[12] in ["", None] or not r[12]])
            total_records = len(records)
            
            # Display statistics
            st.info(f"""
            **Database Statistics:**
            - Total approved records: {total_records}
            - Records needing scale data: {awaiting_scale}
            - Records needing climate data: {awaiting_climate}
            - Records needing location data: {awaiting_location}
            - Records needing building use data: {awaiting_building_use}
            - Records needing approach data: {awaiting_approach}
            - Records needing sample size data: {awaiting_sample_size}
            - Unique scale types: {len(scale_options)}
            - Unique climate types: {len(climate_options)}
            """)
            
            # NEW: Show records with missing data
            st.subheader("🔍 Records with Missing Data")
            
            # Create tabs for different types of missing data
            missing_tabs = st.tabs(["Scale", "Climate", "Location", "Building Use", "Approach", "Sample Size"])
            
            with missing_tabs[0]:
                # Records missing scale data
                missing_scale = [r for r in records if r[7] in ["Awaiting data", "Not Specified", "", None] or not r[7]]
                if missing_scale:
                    st.write(f"**{len(missing_scale)} records missing scale data:**")
                    for record in missing_scale[:20]:  # Show first 20
                        record_id, criteria, energy_method, direction, paragraph, user, status, scale, climate, location, building_use, approach, sample_size = record
                        with st.expander(f"Record {record_id}: {criteria} → {energy_method} ({direction})"):
                            st.write(f"**Current Scale:** {scale if scale else 'Empty'}")
                            st.write(f"**Climate:** {climate if climate else 'Empty'}")
                            st.write(f"**Location:** {location if location else 'Empty'}")
                            
                            # Quick edit button
                            if st.button(f"✏️ Edit Record {record_id}", key=f"quick_edit_scale_{record_id}"):
                                st.session_state[f"admin_full_edit_{record_id}"] = True
                                st.rerun()
                    
                    if len(missing_scale) > 20:
                        st.write(f"... and {len(missing_scale) - 20} more records")
                else:
                    st.success("✅ All records have scale data!")
            
            with missing_tabs[1]:
                # Records missing climate data
                missing_climate = [r for r in records if r[8] in ["Awaiting data", "Not Specified", "", None] or not r[8]]
                if missing_climate:
                    st.write(f"**{len(missing_climate)} records missing climate data:**")
                    for record in missing_climate[:20]:
                        record_id, criteria, energy_method, direction, paragraph, user, status, scale, climate, location, building_use, approach, sample_size = record
                        with st.expander(f"Record {record_id}: {criteria} → {energy_method} ({direction})"):
                            st.write(f"**Scale:** {scale if scale else 'Empty'}")
                            st.write(f"**Current Climate:** {climate if climate else 'Empty'}")
                            st.write(f"**Location:** {location if location else 'Empty'}")
                            
                            if st.button(f"✏️ Edit Record {record_id}", key=f"quick_edit_climate_{record_id}"):
                                st.session_state[f"admin_full_edit_{record_id}"] = True
                                st.rerun()
                    
                    if len(missing_climate) > 20:
                        st.write(f"... and {len(missing_climate) - 20} more records")
                else:
                    st.success("✅ All records have climate data!")
            
            with missing_tabs[2]:
                # Records missing location data
                missing_location = [r for r in records if r[9] in ["", None] or not r[9]]
                if missing_location:
                    st.write(f"**{len(missing_location)} records missing location data:**")
                    for record in missing_location[:20]:
                        record_id, criteria, energy_method, direction, paragraph, user, status, scale, climate, location, building_use, approach, sample_size = record
                        with st.expander(f"Record {record_id}: {criteria} → {energy_method} ({direction})"):
                            st.write(f"**Scale:** {scale if scale else 'Empty'}")
                            st.write(f"**Climate:** {climate if climate else 'Empty'}")
                            st.write(f"**Current Location:** {location if location else 'Empty'}")
                            
                            if st.button(f"✏️ Edit Record {record_id}", key=f"quick_edit_location_{record_id}"):
                                st.session_state[f"admin_full_edit_{record_id}"] = True
                                st.rerun()
                    
                    if len(missing_location) > 20:
                        st.write(f"... and {len(missing_location) - 20} more records")
                else:
                    st.success("✅ All records have location data!")
            
            with missing_tabs[3]:
                # Records missing building use data
                missing_building_use = [r for r in records if r[10] in ["", None] or not r[10]]
                if missing_building_use:
                    st.write(f"**{len(missing_building_use)} records missing building use data:**")
                    for record in missing_building_use[:20]:
                        record_id, criteria, energy_method, direction, paragraph, user, status, scale, climate, location, building_use, approach, sample_size = record
                        with st.expander(f"Record {record_id}: {criteria} → {energy_method} ({direction})"):
                            st.write(f"**Location:** {location if location else 'Empty'}")
                            st.write(f"**Current Building Use:** {building_use if building_use else 'Empty'}")
                            
                            if st.button(f"✏️ Edit Record {record_id}", key=f"quick_edit_building_use_{record_id}"):
                                st.session_state[f"admin_full_edit_{record_id}"] = True
                                st.rerun()
                    
                    if len(missing_building_use) > 20:
                        st.write(f"... and {len(missing_building_use) - 20} more records")
                else:
                    st.success("✅ All records have building use data!")
            
            with missing_tabs[4]:
                # Records missing approach data
                missing_approach = [r for r in records if r[11] in ["", None] or not r[11]]
                if missing_approach:
                    st.write(f"**{len(missing_approach)} records missing approach data:**")
                    for record in missing_approach[:20]:
                        record_id, criteria, energy_method, direction, paragraph, user, status, scale, climate, location, building_use, approach, sample_size = record
                        with st.expander(f"Record {record_id}: {criteria} → {energy_method} ({direction})"):
                            st.write(f"**Building Use:** {building_use if building_use else 'Empty'}")
                            st.write(f"**Current Approach:** {approach if approach else 'Empty'}")
                            
                            if st.button(f"✏️ Edit Record {record_id}", key=f"quick_edit_approach_{record_id}"):
                                st.session_state[f"admin_full_edit_{record_id}"] = True
                                st.rerun()
                    
                    if len(missing_approach) > 20:
                        st.write(f"... and {len(missing_approach) - 20} more records")
                else:
                    st.success("✅ All records have approach data!")
            
            with missing_tabs[5]:
                # Records missing sample size data
                missing_sample_size = [r for r in records if r[12] in ["", None] or not r[12]]
                if missing_sample_size:
                    st.write(f"**{len(missing_sample_size)} records missing sample size data:**")
                    for record in missing_sample_size[:20]:
                        record_id, criteria, energy_method, direction, paragraph, user, status, scale, climate, location, building_use, approach, sample_size = record
                        with st.expander(f"Record {record_id}: {criteria} → {energy_method} ({direction})"):
                            st.write(f"**Approach:** {approach if approach else 'Empty'}")
                            st.write(f"**Current Sample Size:** {sample_size if sample_size else 'Empty'}")
                            
                            if st.button(f"✏️ Edit Record {record_id}", key=f"quick_edit_sample_size_{record_id}"):
                                st.session_state[f"admin_full_edit_{record_id}"] = True
                                st.rerun()
                    
                    if len(missing_sample_size) > 20:
                        st.write(f"... and {len(missing_sample_size) - 20} more records")
                else:
                    st.success("✅ All records have sample size data!")
            
            # NEW: Show records with multiple missing fields
            st.subheader("📋 Records with Multiple Missing Fields")
            
            # Find records with multiple missing fields
            records_with_multiple_missing = []
            for record in records:
                missing_count = 0
                missing_fields = []
                
                record_id, criteria, energy_method, direction, paragraph, user, status, scale, climate, location, building_use, approach, sample_size = record
                
                if scale in ["Awaiting data", "Not Specified", "", None] or not scale:
                    missing_count += 1
                    missing_fields.append("Scale")
                
                if climate in ["Awaiting data", "Not Specified", "", None] or not climate:
                    missing_count += 1
                    missing_fields.append("Climate")
                
                if location in ["", None] or not location:
                    missing_count += 1
                    missing_fields.append("Location")
                
                if building_use in ["", None] or not building_use:
                    missing_count += 1
                    missing_fields.append("Building Use")
                
                if approach in ["", None] or not approach:
                    missing_count += 1
                    missing_fields.append("Approach")
                
                if sample_size in ["", None] or not sample_size:
                    missing_count += 1
                    missing_fields.append("Sample Size")
                
                if missing_count >= 2:  # Records with 2 or more missing fields
                    records_with_multiple_missing.append({
                        'record': record,
                        'missing_count': missing_count,
                        'missing_fields': missing_fields
                    })
            
            if records_with_multiple_missing:
                # Sort by number of missing fields (most missing first)
                records_with_multiple_missing.sort(key=lambda x: x['missing_count'], reverse=True)
                
                st.write(f"**{len(records_with_multiple_missing)} records with 2+ missing fields:**")
                
                for item in records_with_multiple_missing[:10]:  # Show top 10
                    record = item['record']
                    record_id, criteria, energy_method, direction, paragraph, user, status, scale, climate, location, building_use, approach, sample_size = record
                    
                    with st.expander(f"Record {record_id}: {criteria} → {energy_method} ({direction}) - Missing: {', '.join(item['missing_fields'])}"):
                        col_info, col_action = st.columns([3, 1])
                        
                        with col_info:
                            st.write(f"**Missing Fields ({item['missing_count']}):** {', '.join(item['missing_fields'])}")
                            st.write(f"**Scale:** {scale if scale else '❌ Missing'}")
                            st.write(f"**Climate:** {climate if climate else '❌ Missing'}")
                            st.write(f"**Location:** {location if location else '❌ Missing'}")
                            st.write(f"**Building Use:** {building_use if building_use else '❌ Missing'}")
                            st.write(f"**Approach:** {approach if approach else '❌ Missing'}")
                            st.write(f"**Sample Size:** {sample_size if sample_size else '❌ Missing'}")
                        
                        with col_action:
                            if st.button(f"✏️ Edit", key=f"multi_edit_{record_id}", use_container_width=True):
                                st.session_state[f"admin_full_edit_{record_id}"] = True
                                st.rerun()
                
                if len(records_with_multiple_missing) > 10:
                    st.write(f"... and {len(records_with_multiple_missing) - 10} more records")
            else:
                st.success("🎉 No records with multiple missing fields!")
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
# Update the query_paragraphs function to handle case-insensitive matching:
def query_paragraphs(conn, criteria, energy_method, direction, selected_scales=None, selected_dominant_climates=None):
    """Query paragraphs with filters - handle climate codes case-insensitively"""
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
                query += ' AND climate_multi IS NOT NULL AND climate_multi != "" AND INSTR(climate_multi, ",") > 0'
            else:
                # Handle case-insensitive climate matching
                # Convert both database values and filter values to uppercase for comparison
                placeholders = ','.join('?' * len(selected_dominant_climates))
                query += f' AND UPPER(climate) IN ({placeholders})'
                # Convert all selected climates to uppercase for comparison
                params.extend([climate.upper() for climate in selected_dominant_climates])
        
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
    """Get climate options for admin dashboard - compatible with new format"""
    # Use the same function as the main app
    climate_data = query_dominant_climate_options(conn)
    # Return just the formatted strings for backward compatibility
    return [formatted for formatted, color in climate_data]

def query_scale_options_with_counts(conn, criteria=None, energy_method=None, direction=None, selected_climates=None, selected_locations=None):
    """Get scale options with counts filtered by current search criteria AND other active filters"""
    cursor = conn.cursor()
    
    query = '''
        SELECT scale, COUNT(*) as count
        FROM energy_data 
        WHERE scale IS NOT NULL 
          AND scale != '' 
          AND scale != 'Awaiting data'
          AND paragraph IS NOT NULL 
          AND paragraph != '' 
          AND paragraph != '0' 
          AND paragraph != '0.0'
          AND paragraph != 'None'
          AND LENGTH(TRIM(paragraph)) > 0
          AND status NOT IN ("pending", "rejected")
    '''
    params = []
    
    if criteria and criteria != "Select a determinant":
        query += ' AND criteria = ?'
        params.append(criteria)
    
    if energy_method and energy_method != "Select an output":
        query += ' AND energy_method = ?'
        params.append(energy_method)
    
    if direction and direction not in ["Select a direction", None]:
        # Handle both formatted and clean direction
        clean_direction = direction.split(" [")[0] if " [" in direction else direction
        query += ' AND direction = ?'
        params.append(clean_direction)
    
    # ADD CLIMATE FILTER TO SCALE COUNTS
    if selected_climates and selected_climates != ["All"]:
        placeholders = ','.join('?' * len(selected_climates))
        query += f' AND UPPER(climate) IN ({placeholders})'
        params.extend([c.upper() for c in selected_climates])
    
    # ADD LOCATION FILTER TO SCALE COUNTS
    if selected_locations and selected_locations != ["All"]:
        placeholders = ','.join('?' * len(selected_locations))
        query += f' AND location IN ({placeholders})'
        params.extend(selected_locations)
    
    query += ' GROUP BY scale ORDER BY scale ASC'
    
    cursor.execute(query, params)
    results = cursor.fetchall()
    scales_with_counts = [(row[0], row[1]) for row in results if row[0] and str(row[0]).strip()]
    return scales_with_counts

# Also update the query_climate_options_with_counts function to handle case properly:
def query_climate_options_with_counts(conn, criteria=None, energy_method=None, direction=None, selected_scales=None):
    """Get climate options with counts - show ALL when no specific filters are selected"""
    cursor = conn.cursor()
    
    query = '''
        SELECT climate, COUNT(*) as count
        FROM energy_data 
        WHERE climate IS NOT NULL 
          AND climate != '' 
          AND climate != 'Awaiting data'
          AND paragraph IS NOT NULL 
          AND paragraph != '' 
          AND paragraph != '0' 
          AND paragraph != '0.0'
          AND paragraph != 'None'
          AND LENGTH(TRIM(paragraph)) > 0
          AND status NOT IN ("pending", "rejected")
    '''
    params = []
    
    # Only apply filters if they're actually selected (not "Select a...")
    if criteria and criteria != "Select a determinant":
        query += ' AND criteria = ?'
        params.append(criteria)
    
    if energy_method and energy_method != "Select an output":
        query += ' AND energy_method = ?'
        params.append(energy_method)
    
    if direction and direction not in ["Select a direction", None]:
        # Handle both formatted and clean direction
        clean_direction = direction.split(" [")[0] if " [" in direction else direction
        query += ' AND direction = ?'
        params.append(clean_direction)
    
    # Only apply scale filter if specific scales are selected (not "All")
    if selected_scales and selected_scales != ["All"]:
        placeholders = ','.join('?' * len(selected_scales))
        query += f' AND scale IN ({placeholders})'
        params.extend(selected_scales)
    
    query += ' GROUP BY climate ORDER BY climate ASC'
    
    cursor.execute(query, params)
    results = cursor.fetchall()
    
    # Define Köppen climate classifications with descriptions - use UPPERCASE for lookup
    koppen_climates_with_descriptions = {
        'AF': 'Tropical Rainforest', 'AM': 'Tropical Monsoon', 'AW': 'Tropical Savanna',
        'BWH': 'Hot Desert', 'BWK': 'Cold Desert', 'BSH': 'Hot Semi-arid', 'BSK': 'Cold Semi-arid',
        'CFA': 'Humid Subtropical', 'CFB': 'Oceanic', 'CFC': 'Subpolar Oceanic',
        'CSA': 'Hot-summer Mediterranean', 'CSB': 'Warm-summer Mediterranean',
        'DFA': 'Hot-summer Humid Continental', 'DFB': 'Warm-summer Humid Continental', 
        'DFC': 'Subarctic', 'DFD': 'Extremely Cold Subarctic',
        'ET': 'Tundra', 'EF': 'Ice Cap'
    }
    
    # Color to emoji mapping
    color_to_emoji = {
        '#0000FE': '🟦', '#0077FD': '🟦', '#44A7F8': '🟦',
        '#FD0000': '🟥', '#F89292': '🟥', '#F4A400': '🟧', '#FEDA60': '🟨',
        '#FFFE04': '🟨', '#CDCE08': '🟨', '#95FE97': '🟩', '#62C764': '🟩',
        '#379632': '🟩', '#C5FF4B': '🟩', '#64FD33': '🟩', '#36C901': '🟩',
        '#FE01FC': '🟪', '#CA03C2': '🟪', '#973396': '🟪', '#8C5D91': '🟪',
        '#A5ADFE': '🟦', '#4A78E7': '🟦', '#48DDB1': '🟦', '#32028A': '🟪',
        '#01FEFC': '🟦', '#3DC6FA': '🟦', '#037F7F': '🟦', '#004860': '🟦',
        '#AFB0AB': '⬜', '#686964': '⬛',
    }
    
    # Format climate codes with descriptions and colors
    valid_climates = []
    for climate, count in results:
        if not climate or str(climate).strip() == '':
            continue
            
        # Keep original case for display, use uppercase for lookup
        climate_original = str(climate).strip()
        climate_upper = climate_original.upper()
        
        # Check if it's a valid Köppen code
        if climate_upper in koppen_climates_with_descriptions:
            # Get color for this climate
            color = get_climate_color(climate_original)
            # Get corresponding emoji
            emoji = color_to_emoji.get(color, '⬜')
            # Format as "🟦 Csa - Hot-summer Mediterranean [5]" - using original case
            description = koppen_climates_with_descriptions[climate_upper]
            formatted_climate = f"{emoji} {climate_original} - {description} [{count}]"
            valid_climates.append((climate_original, formatted_climate, color, count))
        else:
            # For non-Köppen codes, still show them but without description
            color = '#CCCCCC'  # Default gray
            emoji = '⬜'
            formatted_climate = f"{emoji} {climate_original} [{count}]"
            valid_climates.append((climate_original, formatted_climate, color, count))
    
    # Sort by climate code (case-insensitive)
    valid_climates.sort(key=lambda x: x[0].upper())
    return [(formatted, color, count) for _, formatted, color, count in valid_climates]

# Also update the get_climate_color function to handle case-insensitive:
def get_climate_color(climate_code):
    """Get color for climate code - handle mixed case"""
    # Extract code if it's formatted as "Code - Description"
    if " - " in str(climate_code):
        climate_code = climate_code.split(" - ")[0]
    
    # Convert to uppercase for dictionary lookup, but store original for display
    climate_upper = str(climate_code).upper().strip() if climate_code else ""
    
    colors = {
        # Tropical Climates
        'AF': '#0000FE', 'AM': '#0077FD', 'AW': '#44A7F8',
        # Arid Climates
        'BWH': "#FD0000", 'BWK': '#F89292', 'BSH': '#F4A400', 'BSK': '#FEDA60',
        # Temperate Climates
        'CSA': '#FFFE04', 'CSB': '#CDCE08',
        'CFA': '#C5FF4B', 'CFB': '#64FD33', 'CFC': '#36C901',
        # Continental Climates
        'DFA': '#01FEFC', 'DFB': '#3DC6FA', 'DFC': '#037F7F', 'DFD': '#004860',
        # Polar Climates
        'ET': '#AFB0AB', 'EF': '#686964',
        # Special categories
        'ALL': '#999999'
    }
    return colors.get(climate_upper, '#CCCCCC')

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

def query_direction_counts(conn, selected_criteria, selected_method):
    """Get direction counts for specific criteria and method"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT direction, COUNT(paragraph) as count
        FROM energy_data
        WHERE criteria = ? AND energy_method = ? AND paragraph IS NOT NULL AND paragraph != '' AND paragraph != '0' AND paragraph != '0.0' AND status NOT IN ("pending", "rejected")
        GROUP BY direction
    ''', (selected_criteria, selected_method))
    return dict(cursor.fetchall())

def query_location_options_with_counts(conn, criteria=None, energy_method=None, direction=None, selected_scales=None, selected_climates=None):
    """Get location options with counts filtered by current search criteria"""
    cursor = conn.cursor()
    
    query = '''
        SELECT location, COUNT(*) as count
        FROM energy_data 
        WHERE location IS NOT NULL 
          AND location != '' 
          AND paragraph IS NOT NULL 
          AND paragraph != '' 
          AND paragraph != '0' 
          AND paragraph != '0.0'
          AND paragraph != 'None'
          AND LENGTH(TRIM(paragraph)) > 0
          AND status NOT IN ("pending", "rejected")
    '''
    params = []
    
    if criteria and criteria != "Select a determinant":
        query += ' AND criteria = ?'
        params.append(criteria)
    
    if energy_method and energy_method != "Select an output":
        query += ' AND energy_method = ?'
        params.append(energy_method)
    
    if direction and direction not in ["Select a direction", None]:
        clean_direction = direction.split(" [")[0] if " [" in direction else direction
        query += ' AND direction = ?'
        params.append(clean_direction)
    
    if selected_scales and selected_scales != ["All"]:
        placeholders = ','.join('?' * len(selected_scales))
        query += f' AND scale IN ({placeholders})'
        params.extend(selected_scales)
    
    if selected_climates and selected_climates != ["All"]:
        # Case-insensitive comparison for climates
        placeholders = ','.join('?' * len(selected_climates))
        query += f' AND UPPER(climate) IN ({placeholders})'
        params.extend([c.upper() for c in selected_climates])
    
    query += ' GROUP BY location ORDER BY location ASC'
    
    cursor.execute(query, params)
    results = cursor.fetchall()
    
    return [(row[0], row[1]) for row in results if row[0] and str(row[0]).strip()]

def query_building_use_options_with_counts(conn, criteria=None, energy_method=None, direction=None, selected_scales=None, selected_climates=None, selected_locations=None):
    """Get building use options with counts filtered by current search criteria"""
    cursor = conn.cursor()
    
    query = '''
        SELECT building_use, COUNT(*) as count
        FROM energy_data 
        WHERE building_use IS NOT NULL 
          AND building_use != '' 
          AND paragraph IS NOT NULL 
          AND paragraph != '' 
          AND paragraph != '0' 
          AND paragraph != '0.0'
          AND paragraph != 'None'
          AND LENGTH(TRIM(paragraph)) > 0
          AND status NOT IN ("pending", "rejected")
    '''
    params = []
    
    if criteria and criteria != "Select a determinant":
        query += ' AND criteria = ?'
        params.append(criteria)
    
    if energy_method and energy_method != "Select an output":
        query += ' AND energy_method = ?'
        params.append(energy_method)
    
    if direction and direction not in ["Select a direction", None]:
        clean_direction = direction.split(" [")[0] if " [" in direction else direction
        query += ' AND direction = ?'
        params.append(clean_direction)
    
    if selected_scales and selected_scales != ["All"]:
        placeholders = ','.join('?' * len(selected_scales))
        query += f' AND scale IN ({placeholders})'
        params.extend(selected_scales)
    
    if selected_climates and selected_climates != ["All"]:
        placeholders = ','.join('?' * len(selected_climates))
        query += f' AND UPPER(climate) IN ({placeholders})'
        params.extend([c.upper() for c in selected_climates])
    
    if selected_locations and selected_locations != ["All"]:
        placeholders = ','.join('?' * len(selected_locations))
        query += f' AND location IN ({placeholders})'
        params.extend(selected_locations)
    
    query += ' GROUP BY building_use ORDER BY building_use ASC'
    
    cursor.execute(query, params)
    results = cursor.fetchall()
    
    return [(row[0], row[1]) for row in results if row[0] and str(row[0]).strip()]

def query_approach_options_with_counts(conn, criteria=None, energy_method=None, direction=None, selected_scales=None, selected_climates=None, selected_locations=None, selected_building_uses=None):
    """Get approach options with counts filtered by current search criteria"""
    cursor = conn.cursor()
    
    query = '''
        SELECT approach, COUNT(*) as count
        FROM energy_data 
        WHERE approach IS NOT NULL 
          AND approach != '' 
          AND paragraph IS NOT NULL 
          AND paragraph != '' 
          AND paragraph != '0' 
          AND paragraph != '0.0'
          AND paragraph != 'None'
          AND LENGTH(TRIM(paragraph)) > 0
          AND status NOT IN ("pending", "rejected")
    '''
    params = []
    
    if criteria and criteria != "Select a determinant":
        query += ' AND criteria = ?'
        params.append(criteria)
    
    if energy_method and energy_method != "Select an output":
        query += ' AND energy_method = ?'
        params.append(energy_method)
    
    if direction and direction not in ["Select a direction", None]:
        clean_direction = direction.split(" [")[0] if " [" in direction else direction
        query += ' AND direction = ?'
        params.append(clean_direction)
    
    if selected_scales and selected_scales != ["All"]:
        placeholders = ','.join('?' * len(selected_scales))
        query += f' AND scale IN ({placeholders})'
        params.extend(selected_scales)
    
    if selected_climates and selected_climates != ["All"]:
        placeholders = ','.join('?' * len(selected_climates))
        query += f' AND UPPER(climate) IN ({placeholders})'
        params.extend([c.upper() for c in selected_climates])
    
    if selected_locations and selected_locations != ["All"]:
        placeholders = ','.join('?' * len(selected_locations))
        query += f' AND location IN ({placeholders})'
        params.extend(selected_locations)
    
    if selected_building_uses and selected_building_uses != ["All"]:
        placeholders = ','.join('?' * len(selected_building_uses))
        query += f' AND building_use IN ({placeholders})'
        params.extend(selected_building_uses)
    
    query += ' GROUP BY approach ORDER BY approach ASC'
    
    cursor.execute(query, params)
    results = cursor.fetchall()
    
    return [(row[0], row[1]) for row in results if row[0] and str(row[0]).strip()]

def render_unified_search_interface(enable_editing=False):
    """Unified search interface used by both main app and admin"""
    global conn
    cursor = conn.cursor()
    
    # Get dynamic options from database
    try:
        scale_options = query_scale_options_with_counts(conn)
        climate_options = query_climate_options_with_counts(conn)
    except Exception as e:
        st.warning("Some filter data is not available yet. Please import location and climate data first.")
        scale_options = []
        climate_options = []

    # Get counts for determinants
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
    
    # Get all approved records for display
    cursor.execute('''
        SELECT id, criteria, energy_method, direction, paragraph, user, status, scale, climate, location, building_use, approach, sample_size
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
    criteria_list = ["Select a determinant"] + [f"{criteria} [{count}]" for criteria, count in criteria_counts.items()]
    
    # Initialize filter variables
    selected_scales = []
    selected_climates = []
    selected_locations = []
    selected_building_uses = []
    selected_approaches = []
    selected_direction = None
    actual_method = None

    # UNIFIED FILTER LAYOUT
    # Step 1: Determinant dropdown - full width
    selected_criteria = st.selectbox("Determinant", criteria_list, key="unified_criteria")
    actual_criteria = selected_criteria.split(" [")[0] if selected_criteria != "Select a determinant" else None
    
    # Step 2: Energy Output dropdown - full width (only if determinant is selected)
    if actual_criteria:
        energy_method_counts = query_energy_method_counts(conn, actual_criteria)
        method_list = ["Select an output"] + [f"{method} [{count}]" for method, count in energy_method_counts]
        
        selected_method = st.selectbox("Energy Output(s)", method_list, key="unified_method")
        actual_method = selected_method.split(" [")[0] if selected_method != "Select an output" else None
        
        # Step 3: Direction radio buttons - full width (only if both determinant and method are selected)
        if actual_method:
            direction_counts = query_direction_counts(conn, actual_criteria, actual_method)
            increase_count = direction_counts.get("Increase", 0)
            decrease_count = direction_counts.get("Decrease", 0)

            selected_direction = st.radio(
                "Please select the direction of the relationship",
                [f"Increase [{increase_count}]", f"Decrease [{decrease_count}]"],
                index=None,
                key="unified_direction"
            )
            
            # Step 4: Additional filters in columns (only when direction is selected)
            if selected_direction:
                # First row of filters: Scale and Climate
                col_scale, col_climate = st.columns(2)
                
                with col_scale:
                    # Scale filter
                    if scale_options:
                        current_climate_filter = []
                        if 'unified_selected_climate' in st.session_state and st.session_state.unified_selected_climate != "All":
                            climate_code = st.session_state.unified_selected_climate.split(" - ")[0]
                            climate_code = ''.join([c for c in climate_code if c.isalnum()])
                            current_climate_filter = [climate_code]
                        
                        current_location_filter = []
                        if 'unified_selected_location' in st.session_state and st.session_state.unified_selected_location != "All":
                            location_name = st.session_state.unified_selected_location.split(" [")[0]
                            current_location_filter = [location_name]
                        
                        scale_options_with_counts = query_scale_options_with_counts(
                            conn, actual_criteria, actual_method, selected_direction, 
                            current_climate_filter, current_location_filter
                        )
                        
                        if scale_options_with_counts:
                            if 'unified_selected_scale' not in st.session_state:
                                st.session_state.unified_selected_scale = "All"
                            
                            scale_options_formatted = ["All"] + [f"{scale} [{count}]" for scale, count in scale_options_with_counts]
                            
                            # Smart index calculation
                            current_scale = st.session_state.unified_selected_scale
                            current_index = 0
                            if current_scale != "All":
                                if " [" in current_scale:
                                    current_scale_name = current_scale.split(" [")[0]
                                else:
                                    current_scale_name = current_scale
                                
                                for i, option in enumerate(scale_options_formatted):
                                    if option.startswith(current_scale_name + " [") or option == current_scale:
                                        current_index = i
                                        break
                                else:
                                    st.session_state.unified_selected_scale = "All"
                                    current_index = 0
                            
                            selected_scale = st.selectbox(
                                "Filter by Scale",
                                options=scale_options_formatted,
                                index=current_index,
                                key="unified_scale"
                            )
                            
                            if selected_scale != st.session_state.unified_selected_scale:
                                st.session_state.unified_selected_scale = selected_scale
                                st.rerun()
                            
                            if selected_scale != "All":
                                scale_name = selected_scale.split(" [")[0]
                                selected_scales = [scale_name]
                    else:
                        st.info("No scale data available")

                with col_climate:
                    # Climate filter
                    if climate_options:
                        current_scale_filter = []
                        if 'unified_selected_scale' in st.session_state and st.session_state.unified_selected_scale != "All":
                            scale_name = st.session_state.unified_selected_scale.split(" [")[0]
                            current_scale_filter = [scale_name]
                        
                        current_location_filter = []
                        if 'unified_selected_location' in st.session_state and st.session_state.unified_selected_location != "All":
                            location_name = st.session_state.unified_selected_location.split(" [")[0]
                            current_location_filter = [location_name]
                        
                        # Pass None for direction if it's not selected yet
                        current_direction = None
                        if selected_direction and selected_direction != "Select a direction":
                            current_direction = selected_direction
                        
                        climate_options_with_counts = query_climate_options_with_counts(
                            conn, 
                            actual_criteria,  # This might be None if not selected
                            actual_method,    # This might be None if not selected
                            current_direction,  # Pass None if not selected
                            current_scale_filter  # Pass current scale filter
                        )
                        
                        if climate_options_with_counts:
                            if 'unified_selected_climate' not in st.session_state:
                                st.session_state.unified_selected_climate = "All"
                            
                            climate_options_formatted = ["All"] + [formatted for formatted, color, count in climate_options_with_counts]
                            
                            # Smart index calculation
                            current_climate = st.session_state.unified_selected_climate
                            current_index = 0
                            if current_climate != "All":
                                if " - " in current_climate:
                                    current_climate_code = current_climate.split(" - ")[0]
                                    current_climate_code = ''.join([c for c in current_climate_code if c.isalnum()])
                                else:
                                    current_climate_code = current_climate
                                
                                for i, option in enumerate(climate_options_formatted):
                                    option_code = option.split(" - ")[0]
                                    option_code = ''.join([c for c in option_code if c.isalnum()])
                                    if option_code.upper() == current_climate_code.upper():
                                        current_index = i
                                        break
                                else:
                                    st.session_state.unified_selected_climate = "All"
                                    current_index = 0
                            
                            selected_climate = st.selectbox(
                                "Filter by Dominant Climate",
                                options=climate_options_formatted,
                                index=current_index,
                                key="unified_climate"
                            )
                            
                            if selected_climate != st.session_state.unified_selected_climate:
                                st.session_state.unified_selected_climate = selected_climate
                                st.rerun()
                            
                            if selected_climate != "All":
                                climate_code = selected_climate.split(" - ")[0]
                                climate_code = ''.join([c for c in climate_code if c.isalnum()])
                                selected_climates = [climate_code]
                    else:
                        st.info("No climate data available")

                # Second row of filters: Location and Building Use
                col_location, col_building_use = st.columns(2)
                
                with col_location:
                    # Location filter
                    current_direction = selected_direction.split(" [")[0] if " [" in selected_direction else selected_direction
                    
                    location_options_with_counts = query_location_options_with_counts(
                        conn, actual_criteria, actual_method, current_direction, 
                        selected_scales, selected_climates
                    )
                    
                    if location_options_with_counts:
                        if 'unified_selected_location' not in st.session_state:
                            st.session_state.unified_selected_location = "All"
                        
                        location_options_formatted = ["All"] + [f"{location} [{count}]" for location, count in location_options_with_counts]
                        
                        # Smart index calculation
                        current_location = st.session_state.unified_selected_location
                        current_index = 0
                        if current_location != "All":
                            if " [" in current_location:
                                current_location_name = current_location.split(" [")[0]
                            else:
                                current_location_name = current_location
                            
                            for i, option in enumerate(location_options_formatted):
                                if option.startswith(current_location_name + " [") or option == current_location:
                                    current_index = i
                                    break
                            else:
                                st.session_state.unified_selected_location = "All"
                                current_index = 0
                        
                        selected_location = st.selectbox(
                            "Filter by Location",
                            options=location_options_formatted,
                            index=current_index,
                            key="unified_location"
                        )
                        
                        if selected_location != st.session_state.unified_selected_location:
                            st.session_state.unified_selected_location = selected_location
                            st.rerun()
                        
                        if selected_location != "All":
                            location_name = selected_location.split(" [")[0]
                            selected_locations = [location_name]
                    else:
                        st.info("No location data available")

                with col_building_use:
                    # Building Use filter
                    building_use_options_with_counts = query_building_use_options_with_counts(
                        conn, actual_criteria, actual_method, current_direction,
                        selected_scales, selected_climates, selected_locations
                    )
                    
                    if building_use_options_with_counts:
                        if 'unified_selected_building_use' not in st.session_state:
                            st.session_state.unified_selected_building_use = "All"
                        
                        building_use_options_formatted = ["All"] + [f"{use} [{count}]" for use, count in building_use_options_with_counts]
                        
                        # Smart index calculation
                        current_building_use = st.session_state.unified_selected_building_use
                        current_index = 0
                        if current_building_use != "All":
                            if " [" in current_building_use:
                                current_use_name = current_building_use.split(" [")[0]
                            else:
                                current_use_name = current_building_use
                            
                            for i, option in enumerate(building_use_options_formatted):
                                if option.startswith(current_use_name + " [") or option == current_building_use:
                                    current_index = i
                                    break
                            else:
                                st.session_state.unified_selected_building_use = "All"
                                current_index = 0
                        
                        selected_building_use = st.selectbox(
                            "Filter by Building Use",
                            options=building_use_options_formatted,
                            index=current_index,
                            key="unified_building_use"
                        )
                        
                        if selected_building_use != st.session_state.unified_selected_building_use:
                            st.session_state.unified_selected_building_use = selected_building_use
                            st.rerun()
                        
                        if selected_building_use != "All":
                            building_use_name = selected_building_use.split(" [")[0]
                            selected_building_uses = [building_use_name]
                    else:
                        st.info("No building use data available")

                # Third row: Approach filter
                col_approach = st.columns(1)[0]
                
                with col_approach:
                    # Approach filter
                    approach_options_with_counts = query_approach_options_with_counts(
                        conn, actual_criteria, actual_method, current_direction,
                        selected_scales, selected_climates, selected_locations, selected_building_uses
                    )
                    
                    if approach_options_with_counts:
                        if 'unified_selected_approach' not in st.session_state:
                            st.session_state.unified_selected_approach = "All"
                        
                        approach_options_formatted = ["All"] + [f"{approach} [{count}]" for approach, count in approach_options_with_counts]
                        
                        # Smart index calculation
                        current_approach = st.session_state.unified_selected_approach
                        current_index = 0
                        if current_approach != "All":
                            if " [" in current_approach:
                                current_approach_name = current_approach.split(" [")[0]
                            else:
                                current_approach_name = current_approach
                            
                            for i, option in enumerate(approach_options_formatted):
                                if option.startswith(current_approach_name + " [") or option == current_approach:
                                    current_index = i
                                    break
                            else:
                                st.session_state.unified_selected_approach = "All"
                                current_index = 0
                        
                        selected_approach = st.selectbox(
                            "Filter by Approach",
                            options=approach_options_formatted,
                            index=current_index,
                            key="unified_approach"
                        )
                        
                        if selected_approach != st.session_state.unified_selected_approach:
                            st.session_state.unified_selected_approach = selected_approach
                            st.rerun()
                        
                        if selected_approach != "All":
                            approach_name = selected_approach.split(" [")[0]
                            selected_approaches = [approach_name]
                    else:
                        st.info("No approach data available")

    # Filter records
    filtered_records = records
    if actual_criteria:
        filtered_records = [r for r in filtered_records if r[1] == actual_criteria]
    if actual_method:
        filtered_records = [r for r in filtered_records if r[2] == actual_method]
    if selected_direction:
        clean_direction = selected_direction.split(" [")[0] if selected_direction else None
        filtered_records = [r for r in filtered_records if r[3] == clean_direction]
    if selected_scales:
        filtered_records = [r for r in filtered_records if r[7] in selected_scales]
    if selected_climates:
        # Case-insensitive comparison
        selected_climates_upper = [c.upper() for c in selected_climates]
        filtered_records = [r for r in filtered_records if r[8] and r[8].upper() in selected_climates_upper]
    if selected_locations:
        filtered_records = [r for r in filtered_records if r[9] in selected_locations]
    if selected_building_uses:
        filtered_records = [r for r in filtered_records if r[10] in selected_building_uses]
    if selected_approaches:
        filtered_records = [r for r in filtered_records if r[11] in selected_approaches]

    # Display results
    if actual_criteria and actual_method and selected_direction:
        if len(filtered_records) == 1:
            st.markdown(f"<p><b>The following study shows that an increase (or presence) in {actual_criteria} leads to <i>{'higher' if 'Increase' in selected_direction else 'lower'}</i> {actual_method}.</b></p>", unsafe_allow_html=True)
        else:
            st.markdown(f"<p><b>The following studies show that an increase (or presence) in {actual_criteria} leads to <i>{'higher' if 'Increase' in selected_direction else 'lower'}</i> {actual_method}.</b></p>", unsafe_allow_html=True)

        for count, record in enumerate(filtered_records, start=1):
            record_id, criteria, energy_method, direction, paragraph, user, status, scale, climate, location, building_use, approach, sample_size = record
            
            st.markdown("---")
            
            # Display record information
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Determinant:** {criteria}")
                st.write(f"**Energy Output:** {energy_method}")
                st.write(f"**Direction:** {direction}")
                if location:
                    st.write(f"**Location:** {location}")
                if building_use:
                    st.write(f"**Building Use:** {building_use}")
            
            with col2:
                st.write(f"**Scale:** {scale}")
                if climate:
                    formatted_climate_display = climate
                    if climate_options and isinstance(climate_options[0], tuple):
                        for option in climate_options:
                            if len(option) == 3:
                                formatted, color_option, count_opt = option
                            else:
                                formatted, color_option = option
                            climate_code_from_formatted = formatted.split(" - ")[0]
                            climate_code_clean = ''.join([c for c in climate_code_from_formatted if c.isalnum()])
                            if climate_code_clean.upper() == climate.upper():
                                # REMOVE COUNT FROM DISPLAY
                                if " [" in formatted:
                                    formatted_climate_display = formatted.split(" [")[0]
                                else:
                                    formatted_climate_display = formatted
                                break
                    
                    color = get_climate_color(climate)
                    st.markdown(f"**Dominant Climate:** <span style='background-color: {color}; padding: 2px 8px; border-radius: 10px; color: black;'>{formatted_climate_display}</span>", unsafe_allow_html=True)
                
                if approach:
                    st.write(f"**Approach:** {approach}")
                if sample_size:
                    st.write(f"**Sample Size:** {sample_size}")

            # Study content - always visible
            display_study_content(paragraph, record_id)
            
            # Only show edit buttons for admin users
            if enable_editing and st.session_state.user_role == "admin":
                if st.button("✏️ Edit Record", key=f"edit_btn_{record_id}", use_container_width=True):
                    st.session_state[f"edit_record_{record_id}"] = True
                    st.rerun()
    
    elif actual_criteria or actual_method or selected_direction:
        st.warning("Please select a determinant, energy output, and direction to see results")
    else:
        st.info("Use the filters above to explore the database")

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


# ADD this simple function instead:
def render_spatialbuild_tab(enable_editing=False):
    """Render the main SpatialBuild Energy tab with welcome message and search"""
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
    
    render_unified_search_interface(enable_editing=enable_editing)

# Then UPDATE your main app layout at the bottom to this:
# MAIN APP LAYOUT - CLEAN AND ORGANIZED
if st.session_state.logged_in:
    if st.session_state.current_user == "admin":
        # Admin view
        tab_labels = ["SpatialBuild Energy", "Contribute", "Edit/Review"]
        tabs = st.tabs(tab_labels)
        tab0, tab1, tab2 = tabs
        
        with tab0:
            render_spatialbuild_tab(enable_editing=True)
        
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
            render_spatialbuild_tab(enable_editing=False)
        
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
        render_spatialbuild_tab(enable_editing=False)
    
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
        <p style='font-size:12px;'>If your study, or a study you are aware of, suggests any of these relationships are currently missing from the database, please email the study to sskorsavi@caad.msstate.edu<br> Your contribution will help further develop and improve this tool.</p>
    </div>
"""
st.markdown(footer_html, unsafe_allow_html=True)

conn.close()
