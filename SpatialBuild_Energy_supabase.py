# SpatialBuild_Energy_supabase.py
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
from db_wrapper import DatabaseWrapper

load_dotenv()

# Initialize database wrapper in session state
if 'db' not in st.session_state:
    st.session_state.db = DatabaseWrapper()

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
if "papers_page" not in st.session_state:
    st.session_state.papers_page = 0

if "admin_editing_record_id" not in st.session_state:
    st.session_state.admin_editing_record_id = None    

def check_database_health():
    """Check if the database is healthy and not corrupted"""
    try:
        # For Supabase, we'll do a simple query to check connection
        if st.session_state.db.use_supabase:
            result = st.session_state.db.get_energy_data({'status': 'approved'}, limit=1)
            st.sidebar.success(f"✅ Supabase connected: {len(result)} records accessible")
            return True
        else:
            # For SQLite, we can still do health checks
            conn = sqlite3.connect('my_database.db')
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            cursor.execute("SELECT COUNT(*) FROM energy_data")
            record_count = cursor.fetchone()[0]
            conn.close()
            st.sidebar.success(f"✅ Database healthy: {len(tables)} tables, {record_count} records")
            return True
    except Exception as e:
        st.sidebar.error(f"❌ Database error: {e}")
        return False

def safe_rerun(target_tab="tab3"):
    """Safely rerun while preserving the target tab"""
    st.session_state.current_tab = target_tab
    st.rerun()

def check_button_clicks():
    """Debug function to check if buttons are being clicked"""
    if 'button_clicks' not in st.session_state:
        st.session_state.button_clicks = {}
    
    st.sidebar.write("Button click history:")
    for btn, timestamp in st.session_state.button_clicks.items():
        st.sidebar.write(f"{btn}: {datetime.fromtimestamp(timestamp).strftime('%H:%M:%S')}")

def sanitize_metadata_text(text):
    """Remove markdown formatting characters from metadata text"""
    if not text or pd.isna(text):
        return text
    
    text = str(text)
    
    # Remove markdown formatting characters
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'__(.*?)__', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'_(.*?)_', r'\1', text)
    
    # Remove any remaining asterisks
    text = text.replace('**', '').replace('*', '')
    
    return text.strip()

def query_approved_criteria():
    """Get approved criteria from database"""
    data = st.session_state.db.get_energy_data({'status': 'approved'})
    criteria = set()
    for record in data:
        if record.get('criteria'):
            criteria.add(record['criteria'])
    return [(c,) for c in sorted(criteria)]

def query_approved_energy_outputs():
    """Get approved energy outputs from database"""
    data = st.session_state.db.get_energy_data({'status': 'approved'})
    outputs = set()
    for record in data:
        if record.get('energy_method'):
            outputs.add(record['energy_method'])
    return [(o,) for o in sorted(outputs)]

def contribute():
    # Check if user is logged in
    if not st.session_state.get('logged_in') or not st.session_state.get('current_user'):
        st.warning("Please log in to contribute to the database.")
        return
    
    # Fetch existing determinants and energy outputs from approved records
    approved_determinants = query_approved_criteria()
    criteria_list = ["Select a Determinant", "Add new Determinant"] + [f"{row[0]}" for row in approved_determinants]
    approved_energy_outputs = query_approved_energy_outputs()
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
    if (st.session_state.selected_energy_output_choice != "Select an Energy Output"
        and st.session_state.selected_determinant_choice != "Select a Determinant"):
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

        st.markdown("---")
        st.subheader("Additional Information (Optional)")

        # First row: Scale, Climate, and Location
        col_1, col_2, col_3 = st.columns(3)

        with col_1:
            scale_options = query_dynamic_scale_options()
            selected_scale = st.selectbox(
                "Scale",
                options=["Select scale"] + scale_options + ["Add new scale"],
                key="contribute_scale"
            )
            
            new_scale = ""
            if selected_scale == "Add new scale":
                new_scale = st.text_input("Enter new scale", key="contribute_new_scale")

        with col_2:
            climate_options_data = query_dominant_climate_options()
            climate_options = [formatted for formatted, color in climate_options_data]
            
            selected_climate = st.selectbox(
                "Climate",
                options=["Select climate"] + climate_options,
                key="contribute_climate"
            )
            
            final_climate = None
            if selected_climate != "Select climate":
                if " - " in selected_climate:
                    final_climate = selected_climate.split(" - ")[0]
                    final_climate = ''.join([c for c in final_climate if c.isalnum()])
                else:
                    final_climate = selected_climate

        with col_3:
            location = st.text_input("Location (optional)", key="contribute_location", 
                                    placeholder="e.g., United States, Europe, Specific city/region")

        # Second row: Building Use, Approach, and Sample Size
        st.markdown("---")
        col_4, col_5, col_6 = st.columns(3)

        with col_4:
            building_use_options = ["Select building use", "Mixed use", "Residential", 
                                   "Unspecified / Other", "Commercial", "Add new building use"]
            selected_building_use = st.selectbox(
                "Building Use",
                options=building_use_options,
                key="contribute_building_use"
            )
            
            new_building_use = ""
            if selected_building_use == "Add new building use":
                new_building_use = st.text_input("Enter new building use", key="contribute_new_building_use")

        with col_5:
            approach_options = ["Select approach", "Top-down", "Bottom-up", "Hybrid (combined top-down and bottom-up)"]
            selected_approach = st.selectbox(
                "Approach",
                options=approach_options,
                key="contribute_approach"
            )

        with col_6:
            sample_size = st.text_input(
                "Sample Size (optional)", 
                key="contribute_sample_size",
                placeholder="e.g., 50 buildings, 1000 households, 5 cities"
            )

        st.markdown("---")

        # Save button
        if st.button("Save", key="save_new_record"):
            if new_paragraph.strip():
                # Prepare data for insertion
                final_scale = new_scale if selected_scale == "Add new scale" else selected_scale
                
                if selected_climate != "Select climate":
                    if " - " in selected_climate:
                        final_climate = selected_climate.split(" - ")[0]
                        final_climate = ''.join([c for c in final_climate if c.isalnum()])
                    else:
                        final_climate = selected_climate
                else:
                    final_climate = None

                final_building_use = new_building_use if selected_building_use == "Add new building use" else selected_building_use
                final_approach = selected_approach if selected_approach != "Select approach" else None
                final_sample_size = sample_size if sample_size.strip() else None

                # Create record data
                record_data = {
                    'criteria': new_determinant or st.session_state.selected_determinant_choice,
                    'energy_method': new_energy_output or st.session_state.selected_energy_output_choice,
                    'direction': st.session_state.selected_selected_direction,
                    'paragraph': new_paragraph,
                    'status': 'pending',
                    'user': st.session_state.current_user,
                    'scale': final_scale if final_scale != "Select scale" else "Awaiting data",
                    'climate': final_climate,
                    'location': location if location else None,
                    'building_use': final_building_use if final_building_use != "Select building use" else None,
                    'approach': final_approach,
                    'sample_size': final_sample_size
                }

                # Insert using wrapper
                st.session_state.db.insert_record('energy_data', record_data)

                st.session_state.reset_form = True
                st.success("New record submitted successfully. Thank you for your contribution. Status: pending verification")
                time.sleep(2)
                st.rerun()
            else:
                st.warning("Please ensure the record is not empty before saving.")

def admin_import_and_match_studies_simple(uploaded_file):
    """
    Simplified study matching - ONLY matches study titles against paragraph content
    AUTOMATICALLY detects study column
    """
    # Generate a unique session ID for this import
    if "current_import_session" not in st.session_state:
        st.session_state.current_import_session = f"import_{int(time.time())}"
    
    session_id = st.session_state.current_import_session
    
    # Check if we already have results
    if f"matched_records_{session_id}" in st.session_state and f"unmatched_studies_{session_id}" in st.session_state:
        st.info("📋 Using existing match results. Upload a new file to start over.")
        
        display_admin_matching_review_fixed(
            st.session_state[f"matched_records_{session_id}"], 
            st.session_state[f"unmatched_studies_{session_id}"], 
            st.session_state.get(f"excel_df_{session_id}")
        )
        return st.session_state[f"matched_records_{session_id}"], st.session_state[f"unmatched_studies_{session_id}"]
    
    try:
        # Read Excel file
        df = pd.read_excel(uploaded_file, sheet_name=0)
        
        # Store the dataframe in session state
        st.session_state[f"excel_df_{session_id}"] = df
        
        # AUTOMATICALLY DETECT study column
        study_column = None
        for col in df.columns:
            col_lower = str(col).lower()
            if any(keyword in col_lower for keyword in ['study', 'title', 'paper', 'reference', 'citation']):
                study_column = col
                break
        
        if not study_column:
            study_column = df.columns[0]
            st.warning(f"⚠️ No obvious study column found. Using first column: '{study_column}'")
        
        st.session_state[f"study_column_{session_id}"] = study_column
        
        # Get study names
        study_names = df[study_column].dropna().unique()
        
        matched_records = []
        unmatched_studies = []
        
        st.info(f"🔍 Matching {len(study_names)} studies in database using title matching...")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, study_name in enumerate(study_names):
            if pd.isna(study_name) or not study_name:
                continue
                
            # Clean and normalize the study name
            clean_study = preprocess_study_name(study_name)
            
            status_text.text(f"Searching: {clean_study[:50]}...")
            
            # Search in database using wrapper
            search_results = st.session_state.db.search_energy_data(clean_study, limit=100)
            
            matches = []
            for record in search_results:
                # Check if the study name appears in the paragraph
                if clean_study.lower() in record.get('paragraph', '').lower():
                    matches.append({
                        'record_id': record['id'],
                        'paragraph': record['paragraph'],
                        'criteria': record['criteria'],
                        'energy_method': record['energy_method'],
                        'direction': record['direction'],
                        'scale': record.get('scale'),
                        'climate': record.get('climate'),
                        'location': record.get('location'),
                        'confidence': 'exact_match',
                        'match_position': record['paragraph'].lower().find(clean_study.lower()),
                        'match_percentage': 100,
                        'matching_text': clean_study
                    })
            
            if matches:
                for match_data in matches:
                    matched_records.append({
                        'excel_study': study_name,
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
                    'reason': 'No match found in paragraph field'
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
        
        # Store results
        st.session_state[f"matched_records_{session_id}"] = matched_records
        st.session_state[f"unmatched_studies_{session_id}"] = unmatched_studies
        
        display_admin_matching_review_fixed(matched_records, unmatched_studies, df)
        
        return matched_records, unmatched_studies
        
    except Exception as e:
        st.error(f"Error during import: {e}")
        import traceback
        st.error(f"Detailed error: {traceback.format_exc()}")
        return [], []

def import_location_climate_data_unique():
    """Import climate, location, scale, building use, approach and sample size data"""
    st.subheader("Import Climate, Location, Scale, Building use, Approach and Sample size data")
    
    # Add reset button section at the top
    col1, col2 = st.columns(2)
    with col1:
        st.warning("⚠️ **Reset Options**")
    with col2:
        if st.button("🗑️ Clear Data", key="clear_location_data_btn", use_container_width=True):
            reset_location_climate_scale_data()
    
    st.markdown("---")
    
    # File upload
    uploaded_file = st.file_uploader("Upload Excel file with study data", 
                                   type=["xlsx", "csv", "ods"],
                                   key="location_climate_import_unique")
    
    if uploaded_file is not None:
        try:
            df = pd.read_excel(uploaded_file, sheet_name=0)
            
            st.write("**Preview of data to import:**")
            st.dataframe(df.head(10))
            
            st.write(f"**Columns found in file:** {list(df.columns)}")
            
            # AUTOMATICALLY DETECT STUDY COLUMN
            study_column = None
            for col in df.columns:
                col_lower = str(col).lower()
                if any(keyword in col_lower for keyword in ['study', 'title', 'paper', 'reference', 'citation']):
                    study_column = col
                    break
            
            if study_column is None:
                study_column = df.columns[0]
                st.warning(f"⚠️ No obvious study title column found. Using first column: '{study_column}'")
            else:
                st.success(f"✅ Automatically detected study column: '{study_column}'")
            
            st.markdown("---")
            
            # SIMPLE IMPORT BUTTON
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("🔍 FIND AND MATCH STUDIES", type="primary", use_container_width=True, key="start_matching_button"):
                    
                    with st.spinner("Matching studies against database..."):
                        if "current_import_session" in st.session_state:
                            old_session = st.session_state.current_import_session
                            keys_to_delete = [k for k in st.session_state.keys() if old_session in k]
                            for key in keys_to_delete:
                                del st.session_state[key]
                        
                        session_id = f"import_{int(time.time())}"
                        st.session_state.current_import_session = session_id
                        st.session_state[f"excel_df_{session_id}"] = df
                        st.session_state[f"study_column_{session_id}"] = study_column
                        
                        matched_records, unmatched_studies = perform_study_matching(df, study_column)
                        
                        st.session_state[f"matched_records_{session_id}"] = matched_records
                        st.session_state[f"unmatched_studies_{session_id}"] = unmatched_studies
                        
                        st.success(f"✅ Found {len(matched_records)} matches and {len(unmatched_studies)} unmatched studies")
                        st.rerun()
            
            current_session = st.session_state.get("current_import_session")
            if current_session:
                matched_records = st.session_state.get(f"matched_records_{current_session}")
                unmatched_studies = st.session_state.get(f"unmatched_studies_{current_session}")
                excel_df = st.session_state.get(f"excel_df_{current_session}")
                
                if matched_records is not None and unmatched_studies is not None:
                    display_admin_matching_review_fixed(matched_records, unmatched_studies, excel_df, current_session)
                    
        except Exception as e:
            st.error(f"Error reading Excel file: {str(e)}")
            import traceback
            st.error(f"Detailed error: {traceback.format_exc()}")

def perform_study_matching(df, study_column):
    """Perform the actual matching and return results - EXACT MATCHES ONLY"""
    study_names = df[study_column].dropna().unique()
    
    matched_records = []
    unmatched_studies = []
    
    for study_name in study_names:
        if pd.isna(study_name) or not study_name:
            continue
            
        clean_study = preprocess_study_name(study_name)
        
        # Search in database
        search_results = st.session_state.db.search_energy_data(clean_study, limit=100)
        
        matches = []
        for record in search_results:
            if clean_study.lower() in record.get('paragraph', '').lower():
                matches.append({
                    'record_id': record['id'],
                    'paragraph': record['paragraph'],
                    'criteria': record['criteria'],
                    'energy_method': record['energy_method'],
                    'direction': record['direction'],
                    'scale': record.get('scale'),
                    'climate': record.get('climate'),
                    'location': record.get('location'),
                    'confidence': 'exact_match',
                    'match_position': record['paragraph'].lower().find(clean_study.lower()),
                    'match_percentage': 100,
                    'matching_text': clean_study
                })
        
        if matches:
            for match_data in matches:
                matched_records.append({
                    'excel_study': study_name,
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
                    'match_percentage': 100,
                    'matching_text': match_data['matching_text']
                })
        else:
            unmatched_studies.append({
                'study_name': study_name,
                'normalized_name': clean_study,
                'reason': 'No exact match found in paragraph field'
            })
    
    return matched_records, unmatched_studies

def display_admin_matching_review_fixed(matched_records, unmatched_studies, excel_df, session_id):
    """Display the matching review interface"""
    
    confirmations_key = f"match_confirmations_{session_id}"
    if confirmations_key not in st.session_state:
        st.session_state[confirmations_key] = {}
    
    select_all_key = f"select_all_active_{session_id}"
    if select_all_key not in st.session_state:
        st.session_state[select_all_key] = False
    
    page_key = f"match_page_{session_id}"
    if page_key not in st.session_state:
        st.session_state[page_key] = 0
    
    # Start Over button
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("🔄 Start Over", key=f"start_over_{session_id}"):
            keys_to_delete = [k for k in st.session_state.keys() if session_id in k]
            for key in keys_to_delete:
                del st.session_state[key]
            if st.session_state.get("current_import_session") == session_id:
                del st.session_state["current_import_session"]
            st.rerun()
    
    st.markdown("---")
    
    # FILTER TO EXACT MATCHES ONLY
    exact_matches = [m for m in matched_records if m['confidence'] == 'exact_match']
    other_matches = [m for m in matched_records if m['confidence'] != 'exact_match']
    
    st.write("**Match Results:**")
    st.write(f"🟢 Exact Matches: {len(exact_matches)}")
    if other_matches:
        st.warning(f"⚠️ {len(other_matches)} non-exact matches (strong/good) are not shown - only exact matches can be imported")
    
    if not exact_matches:
        st.error("❌ No exact matches found. Please check your study titles and try again.")
        if unmatched_studies:
            with st.expander("📋 View Unmatched Studies", expanded=False):
                for i, unmatched in enumerate(unmatched_studies[:20]):
                    st.write(f"**{i+1}.** {unmatched['study_name']}")
        return
    
    select_all = st.checkbox(
        f"Select All {len(exact_matches)} Exact Matches", 
        key=f"select_all_{session_id}",
        value=st.session_state[select_all_key]
    )
    
    if select_all != st.session_state[select_all_key]:
        st.session_state[select_all_key] = select_all
        confirmations = st.session_state[confirmations_key]
        for match in exact_matches:
            match_id = f"match_{match['db_record_id']}_{session_id}"
            confirmations[match_id] = select_all
        st.session_state[confirmations_key] = confirmations
        st.rerun()
    
    st.markdown("---")
    col1, col2 = st.columns([3, 1])
    with col1:
        if st.button("IMPORT SELECTED EXACT MATCHES", type="primary", use_container_width=True, key=f"import_main_{session_id}"):
            confirmed_matches = []
            confirmations = st.session_state[confirmations_key]
            
            for match in exact_matches:
                match_id = f"match_{match['db_record_id']}_{session_id}"
                if confirmations.get(match_id, False):
                    confirmed_matches.append(match)
            
            if confirmed_matches:
                if excel_df is not None:
                    with st.spinner(f"Importing {len(confirmed_matches)} exact matches..."):
                        updated_count = process_confirmed_matches(confirmed_matches, excel_df)
                        if updated_count > 0:
                            st.success(f"✅ Successfully updated {updated_count} records!")
                            st.session_state[confirmations_key] = {}
                            time.sleep(2)
                            st.rerun()
                else:
                    st.error("❌ Excel data not available.")
            else:
                st.warning("⚠️ No exact matches selected.")
    with col2:
        st.info(f"📊 {len(exact_matches)} exact matches available")
    
    st.markdown("---")
    
    # Pagination for exact matches
    MATCHES_PER_PAGE = 10
    total_pages = (len(exact_matches) + MATCHES_PER_PAGE - 1) // MATCHES_PER_PAGE
    
    if total_pages > 1:
        col_prev, col_page, col_next = st.columns([1, 2, 1])
        with col_prev:
            if st.button("◀ Previous", disabled=st.session_state[page_key] == 0, key=f"prev_{session_id}"):
                st.session_state[page_key] = max(0, st.session_state[page_key] - 1)
                st.rerun()
        with col_page:
            st.write(f"**Page {st.session_state[page_key] + 1} of {total_pages}**")
        with col_next:
            if st.button("Next ▶", disabled=st.session_state[page_key] >= total_pages - 1, key=f"next_{session_id}"):
                st.session_state[page_key] = min(total_pages - 1, st.session_state[page_key] + 1)
                st.rerun()
    
    start_idx = st.session_state[page_key] * MATCHES_PER_PAGE
    end_idx = min(start_idx + MATCHES_PER_PAGE, len(exact_matches))
    current_page_matches = exact_matches[start_idx:end_idx]
    
    confirmations = st.session_state[confirmations_key]
    
    for i, match in enumerate(current_page_matches):
        match_id = f"match_{match['db_record_id']}_{session_id}"
        
        if match_id not in confirmations:
            confirmations[match_id] = True
            st.session_state[confirmations_key] = confirmations
        
        paragraph_preview = match['matching_paragraph'][:80] + "..." if len(match['matching_paragraph']) > 80 else match['matching_paragraph']
        
        with st.expander(
            f"🟢 ID: {match['db_record_id']} | {match['excel_study'][:60]}... | 📄 {paragraph_preview}", 
            expanded=False
        ):
            col_check, col_study, col_para = st.columns([1, 2, 2])
            
            with col_check:
                confirmed = st.checkbox(
                    "✅ Import",
                    value=confirmations.get(match_id, True),
                    key=f"chk_{match_id}"
                )
                if confirmed != confirmations.get(match_id, False):
                    confirmations[match_id] = confirmed
                    st.session_state[confirmations_key] = confirmations
                
                st.markdown(f"**Record:** `{match['db_record_id']}`")
                st.markdown(f"**Confidence:** Exact")
            
            with col_study:
                st.markdown("**📥 Imported Study:**")
                st.info(match['excel_study'])
                
                st.markdown("**📊 Metadata:**")
                st.write(f"**Determinant:** {match['criteria']}")
                st.write(f"**Energy Output:** {match['energy_method']}")
                st.write(f"**Direction:** {match['direction']}")
            
            with col_para:
                st.markdown("**🗄️ Database Paragraph:**")
                paragraph = match['matching_paragraph']
                
                study_normalized = match.get('excel_study_normalized', match['excel_study'])
                if study_normalized.lower() in paragraph.lower():
                    start = paragraph.lower().index(study_normalized.lower())
                    end = start + len(study_normalized)
                    highlighted = (
                        paragraph[:start] + 
                        "**" + paragraph[start:end] + "**" + 
                        paragraph[end:]
                    )
                    st.markdown(highlighted)
                else:
                    st.write(paragraph)
                
                st.markdown("---")
                st.caption("📋 Select text above to copy or use Ctrl+C")
        
        st.markdown("---")
    
    if len(exact_matches) > MATCHES_PER_PAGE:
        st.markdown("---")
        if st.button("🚀 IMPORT SELECTED EXACT MATCHES", type="primary", use_container_width=True, key=f"import_bottom_{session_id}"):
            confirmed_matches = []
            confirmations = st.session_state[confirmations_key]
            
            for match in exact_matches:
                match_id = f"match_{match['db_record_id']}_{session_id}"
                if confirmations.get(match_id, False):
                    confirmed_matches.append(match)
            
            if confirmed_matches and excel_df:
                with st.spinner(f"Importing {len(confirmed_matches)} exact matches..."):
                    updated_count = process_confirmed_matches(confirmed_matches, excel_df)
                    if updated_count > 0:
                        st.success(f"✅ Successfully updated {updated_count} records!")
                        st.session_state[confirmations_key] = {}
                        time.sleep(2)
                        st.rerun()
            else:
                st.warning("⚠️ No exact matches selected.")
    
    if unmatched_studies:
        st.markdown("---")
        st.subheader("❌ Unmatched Studies")
        st.warning(f"**{len(unmatched_studies)} studies couldn't be automatically matched**")
        
        with st.expander("📋 View Unmatched Studies with Details", expanded=False):
            search_unmatched = st.text_input("🔍 Search unmatched studies", 
                                           placeholder="Enter keyword...", 
                                           key=f"search_unmatched_{session_id}")
            
            filtered_unmatched = unmatched_studies
            if search_unmatched:
                filtered_unmatched = [s for s in filtered_unmatched if search_unmatched.lower() in s['study_name'].lower()]
            
            for i, unmatched in enumerate(filtered_unmatched[:20]):
                with st.expander(f"❌ {unmatched['study_name'][:100]}...", expanded=False):
                    st.write(f"**Study:** {unmatched['study_name']}")
                    st.write(f"**Normalized:** {unmatched['normalized_name']}")
                    st.write(f"**Reason:** {unmatched.get('reason', 'No exact match found')}")
                    
                    st.code(unmatched['study_name'], language="text")
                    
                    if st.button(f"🔍 Search manually", key=f"manual_search_{i}_{session_id}"):
                        st.info("Copy the study title above and search in the database manually")
            
            if len(filtered_unmatched) > 20:
                st.write(f"... and {len(filtered_unmatched) - 20} more")

def reset_location_climate_scale_data():
    """Clear all imported data and reset to defaults"""
    try:
        # Get all records
        records = st.session_state.db.get_energy_data()
        
        updated_count = 0
        for record in records:
            update_data = {
                'location': None,
                'climate': None,
                'scale': 'Awaiting data',
                'building_use': None,
                'approach': None,
                'sample_size': None
            }
            st.session_state.db.update_record('energy_data', record['id'], update_data)
            updated_count += 1
        
        st.success(f"✅ All imported data cleared and reset! {updated_count} records updated.")
        
    except Exception as e:
        st.error(f"Error resetting data: {str(e)}")

    time.sleep(2)
    st.rerun()

def query_dominant_climate_options():
    """Get ONLY valid Köppen climate classifications with descriptions and color glyphs"""
    # Get distinct climate values from database
    climate_values = st.session_state.db.get_distinct_values('climate')
    
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
        'Cwa': 'Monsoon-influenced Humid Subtropical',
        'Cwb': 'Monsoon-influenced Subtropical Highland',
        'Cwc': 'Monsoon-influenced Cold Subtropical Highland',
        
        # Group D: Continental Climates
        'Dfa': 'Hot-summer Humid Continental',
        'Dfb': 'Warm-summer Humid Continental', 
        'Dfc': 'Subarctic',
        'Dfd': 'Extremely Cold Subarctic',
        'Dwa': 'Monsoon-influenced Hot-summer Humid Continental',
        'Dwb': 'Monsoon-influenced Warm-summer Humid Continental',
        'Dwc': 'Monsoon-influenced Subarctic',
        'Dwd': 'Monsoon-influenced Extremely Cold Subarctic',
        
        # Group E: Polar Climates
        'ET': 'Tundra',
        'EF': 'Ice Cap'
    }
    
    # Add special cases
    special_cases = {
        'Var': 'Varies / Multiple Climates'
    }
    
    # Color to emoji mapping
    color_to_emoji = {
        '#0000FE': '🟦',  # Af
        '#0077FD': '🟦',  # Am
        '#44A7F8': '🟦',  # Aw
        '#FD0000': '🟥',  # BWh
        '#F89292': '🟥',  # BWk
        '#F4A400': '🟧',  # BSh
        '#FEDA60': '🟨',  # BSk
        '#FFFE04': '🟨',  # Csa
        '#CDCE08': '🟨',  # Csb
        '#95FE97': '🟩',  # Cwa
        '#62C764': '🟩',  # Cwb
        '#379632': '🟩',  # Cwc
        '#C5FF4B': '🟩',  # Cfa
        '#64FD33': '🟩',  # Cfb
        '#36C901': '🟩',  # Cfc
        '#FE01FC': '🟪',  # Dsa
        '#CA03C2': '🟪',  # Dsb
        '#973396': '🟪',  # Dsc
        '#8C5D91': '🟪',  # Dsd
        '#A5ADFE': '🟦',  # Dwa
        '#4A78E7': '🟦',  # Dwb
        '#48DDB1': '🟦',  # Dwc
        '#32028A': '🟪',  # Dwd
        '#01FEFC': '🟦',  # Dfa
        '#3DC6FA': '🟦',  # Dfb
        '#037F7F': '🟦',  # Dfc
        '#004860': '🟦',  # Dfd
        '#AFB0AB': '⬜',  # ET
        '#686964': '⬛',  # EF
        '#999999': '⬜',  # Gray for special cases
    }
    
    # Filter to ONLY include valid Köppen classifications and special cases
    valid_climates = []
    seen_codes = set()
    
    for climate in climate_values:
        if not climate or pd.isna(climate) or str(climate).strip() == '':
            continue
            
        climate_clean = str(climate).strip()
        if " - " in climate_clean:
            climate_clean = climate_clean.split(" - ")[0]
        climate_clean = ''.join([c for c in climate_clean if c.isalnum()])
        
        if not climate_clean:
            continue
            
        climate_upper = climate_clean.upper()
        if climate_upper in koppen_climates_with_descriptions:
            if climate_clean not in seen_codes:
                seen_codes.add(climate_clean)
                description = koppen_climates_with_descriptions[climate_upper]
                color = get_climate_color(climate_clean)
                emoji = color_to_emoji.get(color, '⬜')
                formatted_climate = f"{emoji} {climate_clean} - {description}"
                valid_climates.append((climate_clean, formatted_climate, color))
        elif climate_upper in special_cases:
            if climate_clean not in seen_codes:
                seen_codes.add(climate_clean)
                description = special_cases[climate_upper]
                color = '#999999'
                emoji = '⬜'
                formatted_climate = f"{emoji} {climate_clean} - {description}"
                valid_climates.append((climate_clean, formatted_climate, color))
    
    # If no valid climates found, return default list
    if not valid_climates:
        all_climates = {**koppen_climates_with_descriptions, **special_cases}
        for climate_code, description in all_climates.items():
            color = get_climate_color(climate_code) if climate_code in koppen_climates_with_descriptions else '#999999'
            emoji = color_to_emoji.get(color, '⬜')
            formatted_climate = f"{emoji} {climate_code} - {description}"
            valid_climates.append((climate_code, formatted_climate, color))
    
    valid_climates.sort(key=lambda x: x[0])
    return [(formatted, color) for _, formatted, color in valid_climates]

def get_climate_color(climate_code):
    """Get color for climate code (handles both raw codes and formatted strings)"""
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
    
    # Tab interface for different admin functions
    tab1, tab2, tab3, tab4 = st.tabs(["Edit Records", "Review Pending Submissions", "Data Import", "Missing Data Review"])
    
    with tab1:
        manage_scale_climate_data()
    
    with tab2:
        review_pending_data()
        
    with tab3:
        import_location_climate_data_unique()
    
    with tab4:
        review_missing_data()
    
    return

def preprocess_study_name(study_name):
    """Clean and normalize study names - MINIMAL preprocessing"""
    if pd.isna(study_name) or not study_name:
        return ""
    
    clean_name = str(study_name).strip()
    clean_name = ' '.join(clean_name.split())
    
    return clean_name

def review_missing_data():
    """Review and edit records with missing data - LOADS NOTHING UNTIL SEARCH"""
    st.subheader("Missing Data Review")
    
    if "missing_data_search" not in st.session_state:
        st.session_state.missing_data_search = False
    if "missing_data_results" not in st.session_state:
        st.session_state.missing_data_results = None
    
    col1, col2 = st.columns([3, 3])
    with col1:
        if st.button("🔍 Find Records with Missing Data", type="primary", use_container_width=True):
            st.session_state.missing_data_search = True
            st.rerun()
    with col2:
        st.write("Click to find records with missing data.")
    
    if st.session_state.get("missing_data_search", False):
        with st.spinner("Analyzing database..."):
            # Get all non rejected records
            all_records = st.session_state.db.get_non_rejected_records(limit=5000)
            
            # Filter records with missing data
            records_with_missing = []
            for record in all_records:
                missing = []
                if not record.get('scale') or record.get('scale') in ['Awaiting data', 'Not Specified', '']:
                    missing.append('scale')
                if not record.get('climate') or record.get('climate') in ['Awaiting data', 'Not Specified', '']:
                    missing.append('climate')
                if not record.get('location'):
                    missing.append('location')
                
                if missing:
                    records_with_missing.append({
                        'record': (
                            record['id'],
                            record['criteria'],
                            record['energy_method'],
                            record['direction'],
                            record['paragraph'],
                            record.get('user'),
                            record.get('status'),
                            record.get('scale'),
                            record.get('climate'),
                            record.get('location'),
                            record.get('building_use'),
                            record.get('approach'),
                            record.get('sample_size')
                        ),
                        'missing_fields': missing
                    })
            
            st.write(f"**Found {len(records_with_missing)} records with missing data**")
            
            if not records_with_missing:
                st.success("✅ No records with missing data found!")
                if st.button("✕ Clear Results"):
                    st.session_state.missing_data_search = False
                    st.session_state.missing_data_results = None
                    st.rerun()
                return
            
            PER_PAGE = 10
            total_pages = (len(records_with_missing) + PER_PAGE - 1) // PER_PAGE
            
            if "missing_data_page" not in st.session_state:
                st.session_state.missing_data_page = 0
            
            if total_pages > 1:
                col1, col2, col3 = st.columns([1, 2, 1])
                with col1:
                    if st.button("◀ Previous", disabled=st.session_state.missing_data_page == 0, key="missing_prev"):
                        st.session_state.missing_data_page -= 1
                        st.rerun()
                with col2:
                    st.write(f"**Page {st.session_state.missing_data_page + 1}/{total_pages}**")
                with col3:
                    if st.button("Next ▶", disabled=st.session_state.missing_data_page >= total_pages - 1, key="missing_next"):
                        st.session_state.missing_data_page += 1
                        st.rerun()
            
            start_idx = st.session_state.missing_data_page * PER_PAGE
            end_idx = min(start_idx + PER_PAGE, len(records_with_missing))
            page_items = records_with_missing[start_idx:end_idx]
            
            for item in page_items:
                record = item['record']
                record_id, criteria, energy_method, direction, paragraph, user, status, scale, climate, location, building_use, approach, sample_size = record
                
                missing_fields = item['missing_fields']
                
                with st.expander(
                    f"📄 Record {record_id}: {criteria} → {energy_method} ({direction}) | Missing: {', '.join(missing_fields)}", 
                    expanded=False
                ):
                    col_meta1, col_meta2 = st.columns(2)
                    
                    with col_meta1:
                        st.markdown(f"**ID:** `{record_id}`")
                        st.markdown(f"**Determinant:** {criteria}")
                        st.markdown(f"**Energy Output:** {energy_method}")
                        st.markdown(f"**Direction:** {direction}")
                    
                    with col_meta2:
                        st.markdown("**❌ Missing Fields:**")
                        for field in missing_fields:
                            st.markdown(f"- 🔴 {field}")
                    
                    st.markdown("---")
                    
                    st.markdown("**Study Content:**")
                    paragraph_html = paragraph.replace('\n', '<br>').replace('\r', '')
                    
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
                            {paragraph_html}
                        </div>
                        ''',
                        unsafe_allow_html=True
                    )
                    
                    st.markdown("---")
                    
                    col_action1, col_action2, col_action3 = st.columns([3, 1, 1])
                    with col_action2:
                        if st.button("Edit Record", key=f"edit_missing_{record_id}", use_container_width=True):
                            st.session_state[f"edit_missing_record_{record_id}"] = True
                            st.session_state[f"edit_missing_data_{record_id}"] = record
                            st.session_state["current_editing_record_id"] = record_id
                            st.session_state["current_editing_from"] = "missing_data"
                            st.rerun()
                    
                    with col_action3:
                        if status != "pending":
                            if st.button("Mark for Review", key=f"pending_missing_{record_id}", use_container_width=True):
                                st.session_state.db.update_record('energy_data', record_id, {'status': 'pending'})
                                st.success(f"Record {record_id} marked for review")
                                time.sleep(1)
                                st.rerun()
                    
                    if st.session_state.get(f"edit_missing_record_{record_id}", False):
                        st.markdown("---")
                        st.markdown(f"### Editing Record {record_id}")
                        
                        record_data = {
                            'criteria': criteria,
                            'energy_method': energy_method,
                            'direction': direction,
                            'paragraph': paragraph,
                            'user': user,
                            'status': status,
                            'scale': scale,
                            'climate': climate,
                            'location': location,
                            'building_use': building_use,
                            'approach': approach,
                            'sample_size': sample_size
                        }
                        
                        def clear_edit_mode():
                            st.session_state[f"edit_missing_record_{record_id}"] = False
                            if f"edit_missing_data_{record_id}" in st.session_state:
                                del st.session_state[f"edit_missing_data_{record_id}"]
                            if "current_editing_record_id" in st.session_state:
                                del st.session_state["current_editing_record_id"]
                            if "current_editing_from" in st.session_state:
                                del st.session_state["current_editing_from"]
                        
                        saved = display_unified_edit_form(record_id, record_data, is_pending=False, 
                                                         clear_edit_callback=clear_edit_mode, from_missing_data=True)
                        if saved:
                            clear_edit_mode()
                            time.sleep(1)
                            st.rerun()
            
            if st.button("✕ Clear Results & Start Over"):
                st.session_state.missing_data_search = False
                st.session_state.missing_data_results = None
                st.rerun()

def convert_urls_to_links(text):
    """Convert URLs in text to clickable HTML links"""
    if not text:
        return text
    
    text = text.replace('\n', '<br>')
    
    patterns = [
        (r'\b(doi\.org/\S+)\b', r'<a href="https://\1" target="_blank" style="color: #0066cc; text-decoration: none;">\1</a>'),
    ]
    
    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    return text

def process_confirmed_matches(confirmed_matches, excel_df):
    """Process the user-confirmed matches with all data fields"""
    if excel_df is None:
        st.error("❌ No Excel data available for import.")
        return 0
    
    updated_count = 0
    not_found_in_excel = []
    
    for match in confirmed_matches:
        record_id = match['db_record_id']
        excel_study = match['excel_study']
        
        study_column = None
        for col in excel_df.columns:
            if 'study' in col.lower() or 'title' in col.lower():
                study_column = col
                break
        
        if study_column is None:
            st.error("❌ No study column found in Excel file.")
            return 0
        
        excel_match = None
        for idx, row in excel_df.iterrows():
            excel_study_name = str(row[study_column]).strip()
            if excel_study_name == excel_study:
                excel_match = row
                break
        
        if excel_match is not None:
            location = ''
            climate_text = ''
            scale = ''
            building_use = ''
            approach = ''
            sample_size = ''
            
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
            
            climate_code = extract_just_climate_code(climate_text)
            
            update_data = {
                'location': location,
                'climate': climate_code if climate_code else '',
                'scale': scale,
                'building_use': building_use,
                'approach': approach,
                'sample_size': sample_size
            }
            
            st.session_state.db.update_record('energy_data', record_id, update_data)
            updated_count += 1
            
        else:
            not_found_in_excel.append(excel_study)
    
    if not_found_in_excel:
        st.warning(f"⚠️ {len(not_found_in_excel)} studies not found in Excel file")
    
    return updated_count

def extract_just_climate_code(climate_text):
    """Extract ONLY the climate code from climate text"""
    if not climate_text or pd.isna(climate_text) or str(climate_text).strip() == '':
        return None
    
    climate_text = str(climate_text).strip()
    
    if '|' in climate_text:
        parts = climate_text.split('|')
        if len(parts) > 1:
            climate_text = parts[1].strip()
    
    import re
    match = re.search(r'([A-Z][A-Za-z]{1,2})', climate_text)
    
    if match:
        return match.group(1)
    
    return None

def display_unified_edit_form(record_id, record_data=None, is_pending=False, clear_edit_callback=None, from_missing_data=False):
    """Unified edit form for all admin editing interfaces"""
    
    if f"edit_session_{record_id}" not in st.session_state:
        import time
        import random
        st.session_state[f"edit_session_{record_id}"] = f"{int(time.time())}_{random.randint(1000, 9999)}"
    
    session_id = st.session_state[f"edit_session_{record_id}"]
    
    if not record_data:
        # Fetch record from database
        record = st.session_state.db.get_energy_data(filters={'id': record_id}, limit=1)
        if not record:
            st.error(f"Record {record_id} not found")
            return False
        
        record = record[0]
        record_data = {
            'criteria': record.get('criteria'),
            'energy_method': record.get('energy_method'),
            'direction': record.get('direction'),
            'paragraph': record.get('paragraph'),
            'user': record.get('user'),
            'status': record.get('status'),
            'scale': record.get('scale'),
            'climate': record.get('climate'),
            'location': record.get('location'),
            'building_use': record.get('building_use'),
            'approach': record.get('approach'),
            'sample_size': record.get('sample_size')
        }
    
    # Edit form layout
    col1, col2 = st.columns(2)
    
    with col1:
        new_criteria = st.text_input("Determinant", 
                                    value=record_data['criteria'], 
                                    key=f"unified_criteria_{record_id}_{session_id}")
        
        new_energy_method = st.text_input("Energy Output", 
                                        value=record_data['energy_method'], 
                                        key=f"unified_energy_method_{record_id}_{session_id}")
        
        new_direction = st.radio("Direction", ["Increase", "Decrease"], 
                                index=0 if record_data['direction'] == "Increase" else 1,
                                key=f"unified_direction_{record_id}_{session_id}", horizontal=True)
        
        try:
            scale_options_list = ["Select scale"] + query_dynamic_scale_options() + ["Add new scale"]
        except Exception as e:
            st.warning(f"Could not load scale options: {e}")
            scale_options_list = ["Select scale", "Awaiting data", "Add new scale"]
        
        current_scale = record_data['scale'] if record_data['scale'] else "Select scale"
        current_scale_index = 0
        if current_scale in scale_options_list:
            current_scale_index = scale_options_list.index(current_scale)
        
        selected_scale = st.selectbox("Scale", 
                                    options=scale_options_list,
                                    index=current_scale_index,
                                    key=f"unified_scale_{record_id}_{session_id}")
        
        new_scale = ""
        if selected_scale == "Add new scale":
            new_scale = st.text_input("Enter new scale", 
                                    value="", 
                                    key=f"unified_new_scale_{record_id}_{session_id}")
        
        new_location = st.text_input("Location", 
                                    value=record_data['location'] if record_data['location'] else "", 
                                    key=f"unified_location_{record_id}_{session_id}")
        
        building_use_options = ["Select building use", "Mixed use", "Residential", 
                               "Unspecified / Other", "Commercial", "Add new building use"]
        current_building_use = record_data['building_use'] if record_data['building_use'] else "Select building use"
        current_building_use_index = building_use_options.index(current_building_use) if current_building_use in building_use_options else 0
        
        selected_building_use = st.selectbox("Building Use", 
                                           options=building_use_options,
                                           index=current_building_use_index,
                                           key=f"unified_building_use_{record_id}_{session_id}")
        
        new_building_use = ""
        if selected_building_use == "Add new building use":
            new_building_use = st.text_input("Enter new building use", 
                                           value="", 
                                           key=f"unified_new_building_use_{record_id}_{session_id}")
    
    with col2:
        try:
            climate_options_raw = query_dominant_climate_options()
            climate_options_list = ["Select climate"] + [formatted for formatted, color in climate_options_raw]
        except Exception as e:
            st.warning(f"Could not load climate options: {e}")
            climate_options_list = ["Select climate"]
        
        current_climate = record_data['climate'] if record_data['climate'] else "Select climate"
        current_climate_index = 0
        
        if current_climate and current_climate.upper() == 'VAR':
            current_climate = 'Var - Varies / Multiple Climates'
        
        for i, opt in enumerate(climate_options_list):
            if opt == "Select climate":
                continue
            opt_code = opt.split(" - ")[0] if " - " in opt else opt
            opt_code = ''.join([c for c in opt_code if c.isalnum()])
            
            current_clean = current_climate
            if " - " in str(current_climate):
                current_clean = current_climate.split(" - ")[0]
            current_clean = ''.join([c for c in str(current_clean) if c.isalnum()])
            
            if current_clean and current_clean.upper() == opt_code.upper():
                current_climate_index = i
                break
        
        selected_climate = st.selectbox(
            "Climate", 
            options=climate_options_list,
            index=current_climate_index,
            key=f"unified_climate_{record_id}_{session_id}"
        )
        
        approach_options = ["Select approach", "Top-down", "Bottom-up", "Hybrid (combined top-down and bottom-up)"]
        current_approach = record_data['approach'] if record_data['approach'] else "Select approach"
        current_approach_index = approach_options.index(current_approach) if current_approach in approach_options else 0
        
        selected_approach = st.selectbox("Approach", 
                                       options=approach_options,
                                       index=current_approach_index,
                                       key=f"unified_approach_{record_id}_{session_id}")
        
        new_sample_size = st.text_input("Sample Size", 
                                        value=record_data['sample_size'] if record_data['sample_size'] else "", 
                                        key=f"unified_sample_size_{record_id}_{session_id}")
        
        if not is_pending:
            status_options = ["approved", "rejected", "pending"]
            current_status = record_data['status'] if record_data['status'] in status_options else "approved"
            new_status = st.selectbox("Status", 
                                    options=status_options,
                                    index=status_options.index(current_status),
                                    key=f"unified_status_{record_id}_{session_id}")
        else:
            new_status = "pending"
    
    st.write("**Study Content:**")
    new_paragraph = st.text_area("Content", 
                                value=record_data['paragraph'], 
                                height=150, 
                                key=f"unified_paragraph_{record_id}_{session_id}")
    
    col_save, col_cancel = st.columns(2)
    
    saved = False
    
    with col_save:
        if st.button("💾 Save Changes", key=f"unified_save_{record_id}_{session_id}", type="primary", use_container_width=True):
            final_scale = new_scale if selected_scale == "Add new scale" else (
                selected_scale if selected_scale != "Select scale" else record_data['scale'])
            
            final_climate = None
            if selected_climate != "Select climate":
                if " - " in selected_climate:
                    final_climate = selected_climate.split(" - ")[0]
                    final_climate = ''.join([c for c in final_climate if c.isalnum()])
                else:
                    final_climate = selected_climate
            
            final_building_use = new_building_use if selected_building_use == "Add new building use" else (
                selected_building_use if selected_building_use != "Select building use" else record_data['building_use'])
            
            final_approach = selected_approach if selected_approach != "Select approach" else record_data['approach']
            
            update_data = {
                'criteria': new_criteria,
                'energy_method': new_energy_method,
                'direction': new_direction,
                'paragraph': new_paragraph,
                'scale': final_scale if final_scale != "Select scale" else None,
                'climate': final_climate,
                'location': new_location if new_location else None,
                'building_use': final_building_use if final_building_use != "Select building use" else None,
                'approach': final_approach if final_approach != "Select approach" else None,
                'sample_size': new_sample_size if new_sample_size else None,
                'status': new_status
            }
            
            st.session_state.db.update_record('energy_data', record_id, update_data)
            saved = True
            st.success(f"✅ Record {record_id} updated successfully!")
    
    with col_cancel:
        if st.button("❌ Cancel", key=f"unified_cancel_{record_id}_{session_id}", use_container_width=True):
            if clear_edit_callback:
                clear_edit_callback()
            else:
                if f"edit_missing_record_{record_id}" in st.session_state:
                    st.session_state[f"edit_missing_record_{record_id}"] = False
                if f"admin_pending_edit_{record_id}" in st.session_state:
                    st.session_state[f"admin_pending_edit_{record_id}"] = False
                if f"admin_full_edit_{record_id}" in st.session_state:
                    st.session_state[f"admin_full_edit_{record_id}"] = False
                if f"edit_data_{record_id}" in st.session_state:
                    del st.session_state[f"edit_data_{record_id}"]
            
            if f"edit_session_{record_id}" in st.session_state:
                del st.session_state[f"edit_session_{record_id}"]
            
            st.session_state.current_tab = "tab3"
            st.rerun()
    
    if saved:
        if f"edit_session_{record_id}" in st.session_state:
            del st.session_state[f"edit_session_{record_id}"]
        
        if "admin_editing_in_missing_data" in st.session_state:
            del st.session_state["admin_editing_in_missing_data"]
        if "admin_current_edit_record_id" in st.session_state:
            del st.session_state["admin_current_edit_record_id"]
    
    return saved

def manage_scale_climate_data():
    """Edit Records - Search first, then select from results dropdown"""
    
    st.subheader("Edit Records - Full Record Management")
    
    if "admin_edit_search_performed" not in st.session_state:
        st.session_state.admin_edit_search_performed = False
    if "admin_edit_search_results" not in st.session_state:
        st.session_state.admin_edit_search_results = []
    if "admin_edit_search_query" not in st.session_state:
        st.session_state.admin_edit_search_query = ""
    if "admin_edit_selected_id" not in st.session_state:
        st.session_state.admin_edit_selected_id = None
    if "admin_edit_trigger_search" not in st.session_state:
        st.session_state.admin_edit_trigger_search = False
    
    st.session_state.current_tab = "tab3"
    
    def on_search_change():
        if st.session_state.admin_edit_search_input.strip():
            st.session_state.admin_edit_trigger_search = True
    
    search_query = st.text_input(
        "Search records",
        placeholder="Enter record ID, study title, location, climate code, sample size... (press Enter to search)",
        key="admin_edit_search_input",
        value=st.session_state.admin_edit_search_query,
        on_change=on_search_change
    )
    
    if st.session_state.admin_edit_trigger_search:
        search_query = st.session_state.admin_edit_search_input
        st.session_state.admin_edit_trigger_search = False
        st.session_state.admin_edit_search_query = search_query
        st.session_state.admin_edit_search_performed = True
        st.session_state.admin_edit_selected_id = None
        
        with st.spinner("Searching records..."):
            # Use wrapper's search method
            results = st.session_state.db.search_energy_data(search_query, limit=200)
            st.session_state.admin_edit_search_results = results
    
    if st.session_state.admin_edit_search_performed:
        col_clear = st.columns([1])[0]
        with col_clear:
            if st.button("✕ Clear Search Results", key="admin_edit_clear_btn", use_container_width=True):
                st.session_state.admin_edit_search_performed = False
                st.session_state.admin_edit_search_results = []
                st.session_state.admin_edit_search_query = ""
                st.session_state.admin_edit_selected_id = None
                st.session_state.current_tab = "tab3"
                st.rerun()
    
    st.markdown("---")
    
    if st.session_state.admin_edit_search_performed and not st.session_state.admin_edit_selected_id:
        results = st.session_state.admin_edit_search_results
        
        if not results:
            st.warning(f"No records found matching '{st.session_state.admin_edit_search_query}'")
            return
        
        st.success(f"Found {len(results)} records matching '{st.session_state.admin_edit_search_query}'")
        
        st.markdown("### Select a Record to Edit")
        
        edit_options = {}
        for record in results:
            record_id = record['id']
            criteria = record.get('criteria', 'N/A')
            energy_method = record.get('energy_method', 'N/A')
            direction = record.get('direction', 'N/A')
            location = record.get('location', '')
            climate = record.get('climate', '')
            
            location_str = f" | {location}" if location else ""
            climate_str = f" | {climate}" if climate else ""
            label = f"ID {record_id}: {criteria} → {energy_method} ({direction}){location_str}{climate_str}"
            
            if len(label) > 120:
                label = label[:117] + "..."
            
            edit_options[label] = record_id
        
        sorted_options = sorted(edit_options.items(), key=lambda x: x[1], reverse=True)
        
        if sorted_options:
            selected_option = st.selectbox(
                '',
                options=["-- Select a record --"] + [opt[0] for opt in sorted_options],
                key="admin_edit_record_selector"
            )
            
            if selected_option != "-- Select a record --":
                selected_id = edit_options[selected_option]
                
                if st.session_state.admin_edit_selected_id != selected_id:
                    st.session_state.admin_edit_selected_id = selected_id
                    st.session_state.current_tab = "tab3"
                    st.rerun()
            
            st.caption(f"Showing {len(results)} records. Select one to edit.")
    
    if st.session_state.admin_edit_selected_id:
        record_id = st.session_state.admin_edit_selected_id
        
        st.markdown("---")
        st.markdown(f"### Editing Record {record_id}")
        
        st.info("Editing mode active. The search results are hidden while editing. Cancel to return to results.")
        
        record = st.session_state.db.get_energy_data(filters={'id': record_id}, limit=1)
        
        if record:
            record = record[0]
            record_data = {
                'criteria': record.get('criteria'),
                'energy_method': record.get('energy_method'),
                'direction': record.get('direction'),
                'paragraph': record.get('paragraph'),
                'user': record.get('user'),
                'status': record.get('status'),
                'scale': record.get('scale'),
                'climate': record.get('climate'),
                'location': record.get('location'),
                'building_use': record.get('building_use'),
                'approach': record.get('approach'),
                'sample_size': record.get('sample_size')
            }
            
            def clear_edit_selection():
                st.session_state.admin_edit_selected_id = None
                st.session_state.current_tab = "tab3"
            
            saved = display_unified_edit_form(
                record_id, 
                record_data, 
                is_pending=False, 
                clear_edit_callback=clear_edit_selection,
                from_missing_data=False
            )
            
            if saved:
                st.session_state.admin_edit_selected_id = None
                st.session_state.current_tab = "tab3"
                st.rerun()
    
    elif not st.session_state.admin_edit_search_performed:
        st.info("Enter a search term above and press Enter to find records to edit")

def review_pending_data():
    """Review Pending Data Submissions"""
    st.subheader("Review Pending Data Submissions")
    
    debug_mode = False

    if "pending_action" in st.session_state:
        record_id = st.session_state.pending_action.get("record_id")
        action = st.session_state.pending_action.get("action")
        
        if record_id and action:
            try:
                if action == "approve":
                    st.session_state.db.update_record('energy_data', record_id, {'status': 'approved'})
                elif action == "reject":
                    st.session_state.db.update_record('energy_data', record_id, {'status': 'rejected'})
                
                del st.session_state.pending_action
                st.success(f"Record {record_id} {action}d successfully!")
                time.sleep(1)
                st.rerun()
                
            except Exception as e:
                st.error(f"Error processing {action} for record {record_id}: {str(e)}")
    
    def handle_button_click(record_id, action):
        st.session_state.pending_action = {
            "record_id": record_id,
            "action": action
        }
    
    # Get pending records
    pending_records = st.session_state.db.get_energy_data(filters={'status': 'pending'}, limit=500)
    
    st.write(f"**{len(pending_records)} pending submissions awaiting review**")
    
    if not pending_records:
        st.success("🎉 No pending submissions! All caught up.")
        return
    
    if st.button("🔄 Refresh List", key="refresh_top_main", use_container_width=True):
        for key in list(st.session_state.keys()):
            if key.startswith("admin_pending_edit_"):
                del st.session_state[key]
        st.rerun()
    
    st.markdown("---")
    
    for index, record in enumerate(pending_records):
        record_id = record['id']
        criteria = record.get('criteria')
        energy_method = record.get('energy_method')
        direction = record.get('direction')
        paragraph = record.get('paragraph')
        user = record.get('user')
        status = record.get('status')
        
        with st.container():
            st.markdown(f"### 📄 Record #{record_id}")
            
            col_info, col_actions = st.columns([3, 1])
            
            with col_info:
                st.write(f"**Submitted by:** {user}")
                st.write(f"**Determinant:** {criteria}")
                st.write(f"**Energy Output:** {energy_method}")
                st.write(f"**Direction:** {direction}")
            
            with col_actions:
                edit_mode = st.session_state.get(f"admin_pending_edit_{record_id}", False)
                
                if not edit_mode:
                    if st.button("✏️ Edit", key=f"edit_{record_id}_{index}", use_container_width=True):
                        st.session_state[f"admin_pending_edit_{record_id}"] = True
                        st.rerun()
                else:
                    if st.button("❌ Cancel Edit", key=f"cancel_edit_{record_id}_{index}", use_container_width=True):
                        st.session_state[f"admin_pending_edit_{record_id}"] = False
                        st.rerun()
            
            if st.session_state.get(f"admin_pending_edit_{record_id}"):
                edit_data = {
                    'criteria': criteria,
                    'energy_method': energy_method,
                    'direction': direction,
                    'paragraph': paragraph,
                    'user': user,
                    'status': status,
                    'scale': None,
                    'climate': None,
                    'location': None,
                    'building_use': None,
                    'approach': None,
                    'sample_size': None
                }
                
                def clear_pending_edit_mode():
                    st.session_state[f"admin_pending_edit_{record_id}"] = False
                
                saved = display_unified_edit_form(record_id, edit_data, is_pending=True, clear_edit_callback=clear_pending_edit_mode)
                if saved:
                    st.session_state[f"admin_pending_edit_{record_id}"] = False
                    time.sleep(1)
                    st.rerun()
                    
            else:
                st.markdown("**Submitted text:**")
                st.text_area("Content", value=paragraph, height=150, 
                           key=f"content_{record_id}", disabled=True, label_visibility="collapsed")
                
                col_approve, col_reject, col_status = st.columns([1, 1, 2])
                
                with col_approve:
                    if st.button(f"✅ Approve", key=f"approve_{record_id}_{index}", 
                               use_container_width=True, type="primary"):
                        handle_button_click(record_id, "approve")
                        st.rerun()
                
                with col_reject:
                    if st.button(f"❌ Reject", key=f"reject_{record_id}_{index}", 
                               use_container_width=True):
                        handle_button_click(record_id, "reject")
                        st.rerun()
            
            st.markdown("---")
    
    st.markdown("---")
    
    # Show statistics
    all_records = st.session_state.db.get_energy_data(limit=5000)
    pending_count = len([r for r in all_records if r.get('status') == 'pending'])
    approved_count = len([r for r in all_records if r.get('status') == 'approved'])
    rejected_count = len([r for r in all_records if r.get('status') == 'rejected'])
    
    with st.expander("📊 Status Statistics", expanded=False):
        st.write(f"**Pending:** {pending_count}")
        st.write(f"**Approved:** {approved_count}")
        st.write(f"**Rejected:** {rejected_count}")

def user_dashboard():
    """Review Your Submissions"""
    st.subheader("Review Your Submissions")

    # Fetch all records created by the current user
    all_records = st.session_state.db.get_energy_data(limit=1000)
    records = [r for r in all_records if r.get('user') == st.session_state.current_user]

    if not records:
        st.write("No records found.")
    else:
        for record in records:
            record_id = record['id']
            criteria = record.get('criteria')
            energy_method = record.get('energy_method')
            direction = record.get('direction')
            paragraph = record.get('paragraph')
            user = record.get('user')
            status = record.get('status')
            
            st.write(f"**Record ID:** {record_id}, **created by:** {user}, **Status:** {status}")
            st.markdown(f"<p>The following pending study shows that a {direction} (or presence) in {criteria} leads to <i>{'higher' if direction == 'Increase' else 'lower'}</i> {energy_method}.</p>", unsafe_allow_html=True)
            st.write(f"**Submitted text:** {paragraph}")

            col1, col2 = st.columns(2)
            with col2:
                if st.button(f"Remove this submission {record_id}"):
                    try:
                        st.session_state.db.delete_record('energy_data', record_id)
                        st.success(f"Submission {record_id} has been removed.")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to remove record {record_id}: {e}")

            st.markdown("---")

def logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

def render_enhanced_papers_tab():
    """Enhanced Studies tab"""
    
    is_admin = st.session_state.get("user_role") == "admin"
    
    if is_admin:
        render_papers_tab()
    else:
        view_tab1, view_tab2 = st.tabs(["Search Studies", "Statistics"])
        
        with view_tab1:
            render_papers_tab()
    
        with view_tab2:
            st.subheader("Database Statistics")
            
            all_records = st.session_state.db.get_energy_data(limit=1000)
            
            if all_records:
                total_records = len(all_records)
                unique_determinants = len(set(r.get('criteria') for r in all_records if r.get('criteria')))
                unique_outputs = len(set(r.get('energy_method') for r in all_records if r.get('energy_method')))
                unique_locations = len(set(r.get('location') for r in all_records if r.get('location')))
                unique_climates = len(set(r.get('climate') for r in all_records if r.get('climate')))
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Total Records", total_records)
                    st.metric("Unique Determinants", unique_determinants)
                
                with col2:
                    st.metric("Total Studies", total_records)
                    st.metric("Unique Locations", unique_locations)
                
                with col3:
                    st.metric("Unique Energy Outputs", unique_outputs)
                    st.metric("Unique Climates", unique_climates)
                
                # Show climate distribution
                st.subheader("Climate Code Distribution")
                
                climate_counts = {}
                for record in all_records:
                    climate = record.get('climate')
                    if climate and climate not in ['Awaiting data', '']:
                        climate_counts[climate] = climate_counts.get(climate, 0) + 1
                
                if climate_counts:
                    for climate, count in sorted(climate_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
                        color = get_climate_color(climate)
                        st.markdown(
                            f"<div style='display: flex; align-items: center; margin: 5px 0;'>"
                            f"<span style='background-color: {color}; width: 20px; height: 20px; border-radius: 4px; margin-right: 10px;'></span>"
                            f"<span style='flex: 1;'>{climate}</span>"
                            f"<span style='font-weight: bold;'>{count}</span>"
                            f"</div>",
                            unsafe_allow_html=True
                        )
                else:
                    st.info("No climate data available")
            else:
                st.info("No data available for statistics")

def render_papers_tab():
    """Render the Studies tab with search functionality"""
    st.title("Research Studies Database")
    
    st.markdown("""Use the search box below to browse all studies in the SpatialBuild Energy database.""")
    
    st.markdown("---")
    
    if "papers_search_performed" not in st.session_state:
        st.session_state.papers_search_performed = False
    
    if "papers_current_results" not in st.session_state:
        st.session_state.papers_current_results = None
    
    if "papers_current_page" not in st.session_state:
        st.session_state.papers_current_page = 0
    
    if "papers_search_query" not in st.session_state:
        st.session_state.papers_search_query = ""
    
    if "papers_sort_ascending" not in st.session_state:
        st.session_state.papers_sort_ascending = True
    
    st.markdown("""
    <style>
    div[data-testid="column"]:has(button[key*="papers_prev"]),
    div[data-testid="column"]:has(button[key*="papers_next"]) {
        display: flex;
        justify-content: center;
        align-items: center;
    }
    
    div[data-testid="column"]:has(p:contains("Page")) {
        display: flex;
        justify-content: center;
        align-items: center;
        text-align: center;
    }
    
    button[key*="papers_prev"], button[key*="papers_next"] {
        width: 100px !important;
    }
    
    button[key="papers_sort_direction"] {
        font-size: 20px !important;
        font-weight: bold !important;
        padding: 0px 10px !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([3, 1.8, 0.5])
    
    with col1:
        st.markdown("**Search Studies**")
        
        def on_search_change():
            if st.session_state.papers_search_input:
                st.session_state.papers_search_triggered = True
                st.session_state.papers_search_query = st.session_state.papers_search_input
            else:
                st.session_state.papers_search_triggered = False
                st.session_state.papers_search_query = ""
                st.session_state.papers_current_results = []
                st.session_state.papers_search_performed = False
                st.session_state.papers_last_query = ""
                st.session_state.papers_current_page = 0
        
        search_query = st.text_input(
            "Search studies",
            placeholder="Type to search by title, author, determinant, climate...",
            key="papers_search_input",
            label_visibility="collapsed",
            on_change=on_search_change,
            value=st.session_state.get("papers_search_query", "")
        )
    
    with col2:
        st.markdown("**Sort by**")
        sort_order = st.selectbox(
            "Sort results by",
            ["Determinant", 
             "Location", 
             "Building Use", 
             "Scale", 
             "Climate", 
             "Approach"],
            key="papers_sort",
            label_visibility="collapsed"
        )
    
    with col3:
        st.markdown("**Order**")
        sort_direction_label = "↑" if st.session_state.papers_sort_ascending else "↓"
        if st.button(sort_direction_label, key="papers_sort_direction", 
                    help="Toggle sort direction (Ascending/Descending)", 
                    use_container_width=True):
            st.session_state.papers_sort_ascending = not st.session_state.papers_sort_ascending
            st.rerun()
    
    current_search = st.session_state.get("papers_search_input", "")
    
    if st.session_state.get("papers_search_triggered", False) and current_search:
        search_query = current_search
        st.session_state.papers_search_triggered = False
        st.session_state.papers_search_query = search_query
        st.session_state.papers_last_query = search_query
        st.session_state.papers_search_performed = True
        
        with st.spinner(f"Searching for '{search_query}'..."):
            results = st.session_state.db.search_energy_data(search_query, limit=500)
            st.session_state.papers_current_results = results
            st.session_state.papers_current_page = 0
            st.rerun()
    
    if (st.session_state.get("papers_search_performed", False) and 
        st.session_state.get("papers_last_query", "") and 
        st.session_state.papers_current_results is not None):
        
        results = st.session_state.papers_current_results
        search_query = st.session_state.get("papers_last_query", "")
        
        def get_sort_key(record):
            if sort_order == "Determinant":
                value = str(record.get('criteria') or '').lower()
            elif sort_order == "Location":
                value = str(record.get('location') or '').lower()
            elif sort_order == "Building Use":
                value = str(record.get('building_use') or '').lower()
            elif sort_order == "Scale":
                value = str(record.get('scale') or '').lower()
            elif sort_order == "Climate":
                value = str(record.get('climate') or '').lower()
            elif sort_order == "Approach":
                value = str(record.get('approach') or '').lower()
            else:
                value = str(record.get('criteria') or '').lower()
            return value
        
        results.sort(key=get_sort_key, reverse=not st.session_state.papers_sort_ascending)
        direction_indicator = "↑" if st.session_state.papers_sort_ascending else "↓"
        
        col_header, col_clear = st.columns([4, 1])
        
        with col_header:
            if len(results) == 1:
                st.success(f"Found {len(results)} study matching '{search_query}'")
            elif len(results) > 1:
                st.success(f"Found {len(results)} studies matching '{search_query}'")
            else:
                st.warning(f"No results found for '{search_query}'")
        
        with col_clear:
            if st.button("✕ Clear", key=f"clear_btn_{st.session_state.get('papers_clear_counter', 0)}", 
                       help="Clear search", use_container_width=True):
                st.session_state.papers_clear_counter = st.session_state.get('papers_clear_counter', 0) + 1
                st.session_state.papers_search_query = ""
                st.session_state.papers_current_results = []
                st.session_state.papers_search_performed = False
                st.session_state.papers_search_triggered = False
                st.session_state.papers_current_page = 0
                st.session_state.papers_last_query = ""
                st.rerun()
        
        if len(results) > 0:
            PAPERS_PER_PAGE = 10
            total_pages = (len(results) + PAPERS_PER_PAGE - 1) // PAPERS_PER_PAGE
            
            if total_pages > 1:
                col_prev, col_page, col_next = st.columns([1, 1, 1])
                
                with col_prev:
                    if st.button("◀ Previous", disabled=st.session_state.papers_current_page == 0, 
                               key="papers_prev_top", use_container_width=True):
                        st.session_state.papers_current_page = max(0, st.session_state.papers_current_page - 1)
                        st.rerun()
                
                with col_page:
                    st.markdown(f"<div style='text-align: center; font-weight: 500;'>Page {st.session_state.papers_current_page + 1} of {total_pages}</div>", 
                              unsafe_allow_html=True)
                
                with col_next:
                    if st.button("Next ▶", disabled=st.session_state.papers_current_page >= total_pages - 1, 
                               key="papers_next_top", use_container_width=True):
                        st.session_state.papers_current_page = min(total_pages - 1, st.session_state.papers_current_page + 1)
                        st.rerun()
            
            start_idx = st.session_state.papers_current_page * PAPERS_PER_PAGE
            end_idx = min(start_idx + PAPERS_PER_PAGE, len(results))
            page_results = results[start_idx:end_idx]
            
            st.markdown(f"<div style='text-align: right; color: #666; font-size: 0.9em;'>Showing {start_idx + 1}-{end_idx} of {len(results)} records • Sorted by {sort_order} {direction_indicator}</div>", 
                      unsafe_allow_html=True)
            
            for record in page_results:
                record_id = record['id']
                paragraph = record.get('paragraph', '')
                criteria = record.get('criteria', '')
                energy_method = record.get('energy_method', '')
                direction = record.get('direction', '')
                scale = record.get('scale', '')
                climate = record.get('climate', '')
                location = record.get('location', '')
                building_use = record.get('building_use', '')
                approach = record.get('approach', '')
                sample_size = record.get('sample_size', '')
                
                st.markdown("---")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    clean_criteria = sanitize_metadata_text(criteria)
                    clean_energy_method = sanitize_metadata_text(energy_method)
                    
                    st.write(f"**{clean_criteria}** → **{clean_energy_method}** ({direction})")
                    st.write(f"**Record ID:** {record_id}")
                    if location:
                        st.write(f"**Location:** {sanitize_metadata_text(location)}")
                    if building_use:
                        st.write(f"**Building Use:** {sanitize_metadata_text(building_use)}")
                                
                with col2:
                    st.write(f"**Scale:** {scale if scale else 'Not specified'}")
                    if climate:
                        color = get_climate_color(climate)
                        
                        climate_descriptions = {
                            'Af': 'Tropical Rainforest', 'Am': 'Tropical Monsoon', 'Aw': 'Tropical Savanna',
                            'BWh': 'Hot Desert', 'BWk': 'Cold Desert', 'BSh': 'Hot Semi-arid', 'BSk': 'Cold Semi-arid',
                            'Cfa': 'Humid Subtropical', 'Cfb': 'Oceanic', 'Cfc': 'Subpolar Oceanic',
                            'Csa': 'Hot-summer Mediterranean', 'Csb': 'Warm-summer Mediterranean',
                            'Cwa': 'Monsoon-influenced Humid Subtropical',
                            'Dfa': 'Hot-summer Humid Continental', 'Dfb': 'Warm-summer Humid Continental', 
                            'Dfc': 'Subarctic', 'Dfd': 'Extremely Cold Subarctic',
                            'Dwa': 'Monsoon-influenced Hot-summer Humid Continental',
                            'Dwb': 'Monsoon-influenced Warm-summer Humid Continental',
                            'Dwc': 'Monsoon-influenced Subarctic',
                            'Dwd': 'Monsoon-influenced Extremely Cold Subarctic',
                            'ET': 'Tundra', 'EF': 'Ice Cap',
                            'Var': 'Varies / Multiple Climates'
                        }
                        
                        climate_code = climate
                        if " - " in str(climate):
                            climate_code = climate.split(" - ")[0]
                        climate_code = ''.join([c for c in str(climate_code) if c.isalnum()])
                        
                        description = climate_descriptions.get(climate_code, '')
                        
                        if description:
                            climate_display = f"{climate_code} - {description}"
                        else:
                            climate_display = climate_code
                            
                        st.markdown(
                            f"**Climate:** <span style='background-color: {color}; padding: 2px 8px; border-radius: 10px; color: black;'>{climate_display}</span>", 
                            unsafe_allow_html=True
                        )
                    if approach:
                        st.write(f"**Approach:** {approach}")
                    if sample_size:
                        st.write(f"**Sample Size:** {sample_size}")
                
                highlighted_paragraph = paragraph
                if search_query:
                    import re
                    
                    url_pattern = r'https?://\S+|doi\.org/\S+|www\.\S+'
                    urls = re.findall(url_pattern, paragraph, re.IGNORECASE)
                    
                    placeholders = {}
                    temp_text = paragraph
                    for i, url in enumerate(urls):
                        placeholder = f"__URL_PLACEHOLDER_{i}__"
                        placeholders[placeholder] = url
                        temp_text = temp_text.replace(url, placeholder)
                    
                    pattern = re.compile(re.escape(search_query), re.IGNORECASE)
                    highlighted_temp = pattern.sub(
                        lambda m: f"<span style='background-color: #FFFF00; font-weight: bold;'>{m.group()}</span>", 
                        temp_text
                    )
                    
                    highlighted_paragraph = highlighted_temp
                    for placeholder, url in placeholders.items():
                        highlighted_paragraph = highlighted_paragraph.replace(placeholder, url)
                
                paragraph_with_links = convert_urls_to_links(highlighted_paragraph)
                
                st.markdown(
                    f'''
                    <div style="
                        border: 1px solid #e0e0e0;
                        padding: 15px;
                        border-radius: 8px;
                        background-color: #f9f9fb;
                        max-height: 250px;
                        overflow-y: auto;
                        font-family: Arial, sans-serif;
                        line-height: 1.5;
                        font-size: 14px;
                        user-select: text;
                        -webkit-user-select: text;
                        cursor: text;
                    ">
                        {paragraph_with_links}
                    </div>
                    ''',
                    unsafe_allow_html=True
                )
                
                st.markdown("<br>", unsafe_allow_html=True)
            
            if total_pages > 1:
                st.markdown("---")
                
                col_prev_bottom, col_page_bottom, col_next_bottom = st.columns([1, 1, 1])
                
                with col_prev_bottom:
                    if st.button("◀ Previous", disabled=st.session_state.papers_current_page == 0, 
                               key="papers_prev_bottom", use_container_width=True):
                        st.session_state.papers_current_page = max(0, st.session_state.papers_current_page - 1)
                        st.rerun()
                
                with col_page_bottom:
                    st.markdown(f"<div style='text-align: center; font-weight: 500;'>Page {st.session_state.papers_current_page + 1} of {total_pages}</div>", 
                              unsafe_allow_html=True)
                
                with col_next_bottom:
                    if st.button("Next ▶", disabled=st.session_state.papers_current_page >= total_pages - 1, 
                               key="papers_next_bottom", use_container_width=True):
                        st.session_state.papers_current_page = min(total_pages - 1, st.session_state.papers_current_page + 1)
                        st.rerun()
                
                st.markdown(f"<div style='text-align: right; color: #666; font-size: 0.9em; margin-top: 5px;'>Showing {start_idx + 1}-{end_idx} of {len(results)} records • Sorted by {sort_order} {direction_indicator}</div>", 
                          unsafe_allow_html=True)
    
    elif not st.session_state.papers_search_performed:
        st.info("Enter a search term above and press Enter to find studies in the database.")

def query_dynamic_scale_options():
    """Get unique scale values from the database"""
    return st.session_state.db.get_distinct_values('scale')

def render_contribute_tab():
    """Render the Contribute tab content"""
    st.title("Contribute to the SpatialBuild Energy project.")
    whats_next_html = ("""
    Sign up or log in to add your study or reference, sharing determinants, energy outputs and their relationships. If approved your contribution will be added to the database. Your help will improve this resource for designers, urban planners, developers, and policymakers.</p>
    """
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
            user = st.session_state.db.get_user(username)
            
            if user and bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
                st.session_state.logged_in = True
                st.session_state.current_user = username
                st.session_state.user_role = user['role']
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
                    st.session_state.db.create_user(username, hashed_password, 'user')
                    st.success("Account created successfully!")
                except Exception as e:
                    if "duplicate key" in str(e).lower():
                        st.error("Username already exists.")
                    else:
                        st.error(f"Error creating account: {e}")
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
    guest_info = "Log in or sign up to contribute to the SpatialBuild Energy project."
    st.sidebar.write(guest_info, unsafe_allow_html=True)

def render_spatialbuild_tab(enable_editing=False):
    """Render the main SpatialBuild Energy tab with welcome message and search"""
    st.title("Welcome to SpatialBuild Energy")
    welcome_html = ("""<h7>This tool distills insights from over 200 studies on building energy consumption across meso and macro scales, spanning neighborhood, urban, state, regional, national, and global levels. It maps more than 100 factors influencing energy use, showing whether each increases or decreases energy outputs like total consumption, energy use intensity, or heating demand. Designed for urban planners and policymakers, the tool provides insights to craft smarter energy reduction strategies.</p><p><h7>"""
    )
    st.markdown(welcome_html, unsafe_allow_html=True)

    how_it_works_html = ("""
    1. Pick Your Focus: Choose the determinant you want to explore.<br>
    2. Select Energy Outputs: For example energy use intensity or heating demand.<br>
    3. Filter your results and access the relevant study via links provided."""
    )
    st.markdown(how_it_works_html, unsafe_allow_html=True)
    
    render_unified_search_interface(enable_editing=enable_editing)

def query_energy_method_counts(selected_criteria):
    """Get energy methods with counts for specific criteria (including NULL status)"""
    all_records = st.session_state.db.get_energy_data(limit=5000)
    
    # Filter for this criteria and exclude rejected
    records = []
    for record in all_records:
        if record.get('criteria') == selected_criteria and record.get('status') != 'rejected':
            records.append(record)
    
    counts = {}
    for record in records:
        method = record.get('energy_method')
        if method:
            counts[method] = counts.get(method, 0) + 1
    
    return [(method, count) for method, count in sorted(counts.items())]

def query_direction_counts(selected_criteria, selected_method):
    """Get direction counts for specific criteria and method (including NULL status)"""
    all_records = st.session_state.db.get_energy_data(limit=5000)
    
    # Filter for criteria and method, exclude rejected
    records = []
    for record in all_records:
        if (record.get('criteria') == selected_criteria and 
            record.get('energy_method') == selected_method and
            record.get('status') != 'rejected'):
            records.append(record)
    
    # Initialize counts with zeros
    counts = {'Increase': 0, 'Decrease': 0}
    
    # Count directions
    for record in records:
        direction = record.get('direction')
        if direction in counts:
            counts[direction] += 1
    
    return counts

def query_paragraphs(selected_criteria, selected_method, selected_direction, selected_scales=None, selected_climates=None):
    """Query paragraphs with filters - returns list of (id, paragraph) tuples"""
    all_records = st.session_state.db.get_energy_data(limit=5000)
    
    # Start with all records
    records = all_records
    
    # Apply status filter (exclude rejected)
    records = [r for r in records if r.get('status') != 'rejected']
    
    # Apply criteria filter
    if selected_criteria and selected_criteria != "Select a determinant":
        records = [r for r in records if r.get('criteria') == selected_criteria]
    
    # Apply method filter
    if selected_method and selected_method != "Select an output":
        records = [r for r in records if r.get('energy_method') == selected_method]
    
    # Apply direction filter
    if selected_direction:
        clean_direction = selected_direction.split(" [")[0] if " [" in selected_direction else selected_direction
        records = [r for r in records if r.get('direction') == clean_direction]
    
    # Apply scale filter
    if selected_scales and selected_scales != ["All"] and selected_scales:
        records = [r for r in records if r.get('scale') in selected_scales]
    
    # Apply climate filter
    if selected_climates and selected_climates != ["All"] and selected_climates:
        selected_upper = [c.upper() for c in selected_climates]
        records = [r for r in records if r.get('climate') and r.get('climate').upper() in selected_upper]
    
    # Return list of (id, paragraph) for valid paragraphs
    results = []
    for r in records:
        paragraph = r.get('paragraph')
        if paragraph and paragraph not in ['0', '0.0', '', None]:
            results.append((r['id'], paragraph))
    
    return results

def query_scale_options_with_counts(criteria=None, energy_method=None, direction=None, selected_climates=None, selected_locations=None):
    """Get scale options with counts filtered by current search criteria"""
    # Get all records
    all_records = st.session_state.db.get_energy_data(limit=5000)
    
    # Filter out rejected records (keep NULL, approved, pending)
    records = [r for r in all_records if r.get('status') != 'rejected']
    
    # Apply criteria filter
    if criteria and criteria != "Select a determinant":
        records = [r for r in records if r.get('criteria') == criteria]
    
    # Apply energy method filter
    if energy_method and energy_method != "Select an output":
        records = [r for r in records if r.get('energy_method') == energy_method]
    
    # Apply direction filter
    if direction and direction not in ["Select a direction", None]:
        clean_direction = direction.split(" [")[0] if " [" in direction else direction
        records = [r for r in records if r.get('direction') == clean_direction]
    
    # Apply climate filter
    if selected_climates and selected_climates != ["All"]:
        selected_upper = [c.upper() for c in selected_climates]
        records = [r for r in records if r.get('climate') and r.get('climate').upper() in selected_upper]
    
    # Apply location filter
    if selected_locations and selected_locations != ["All"]:
        records = [r for r in records if r.get('location') in selected_locations]
    
    # Count scales
    scale_counts = {}
    for record in records:
        scale = record.get('scale')
        if scale and scale not in ['Awaiting data', '']:
            scale_counts[scale] = scale_counts.get(scale, 0) + 1
    
    return [(scale, count) for scale, count in sorted(scale_counts.items())]


def query_climate_options_with_counts(criteria=None, energy_method=None, direction=None, selected_scales=None):
    """Get climate options with counts filtered by current search criteria"""
    # Get all records
    all_records = st.session_state.db.get_energy_data(limit=5000)
    
    # Filter out rejected records (keep NULL, approved, pending)
    records = [r for r in all_records if r.get('status') != 'rejected']
    
    # Apply criteria filter
    if criteria and criteria != "Select a determinant":
        records = [r for r in records if r.get('criteria') == criteria]
    
    # Apply energy method filter
    if energy_method and energy_method != "Select an output":
        records = [r for r in records if r.get('energy_method') == energy_method]
    
    # Apply direction filter
    if direction and direction not in ["Select a direction", None]:
        clean_direction = direction.split(" [")[0] if " [" in direction else direction
        records = [r for r in records if r.get('direction') == clean_direction]
    
    # Apply scale filter
    if selected_scales and selected_scales != ["All"]:
        records = [r for r in records if r.get('scale') in selected_scales]
    
    # Count climates
    climate_counts = {}
    for record in records:
        climate = record.get('climate')
        if climate and climate not in ['Awaiting data', '']:
            climate_counts[climate] = climate_counts.get(climate, 0) + 1
    
    # Get formatted climate options
    climate_options_raw = query_dominant_climate_options()
    
    # Create a lookup dictionary for climate formatting
    climate_format_lookup = {}
    for item in climate_options_raw:
        if len(item) == 3:
            code, formatted, color = item
            climate_format_lookup[code] = (formatted, color)
        elif len(item) == 2:
            formatted, color = item
            # Try to extract code from formatted string
            # Format is typically "🟦 Csa - Description" or "Csa - Description"
            import re
            code_match = re.search(r'([A-Z][A-Za-z]{1,2})', formatted)
            if code_match:
                code = code_match.group(1)
                climate_format_lookup[code] = (formatted, color)
            else:
                # Fallback: use formatted string as key
                climate_format_lookup[formatted] = (formatted, color)
    
    result = []
    for climate, count in climate_counts.items():
        # Try to find matching format
        found = False
        for code, (formatted, color) in climate_format_lookup.items():
            if code.upper() == climate.upper() or formatted == climate:
                result.append((f"{formatted} [{count}]", color, count))
                found = True
                break
        if not found:
            # No formatted version found, use raw climate code
            color = get_climate_color(climate)
            result.append((f"{climate} [{count}]", color, count))
    
    return sorted(result, key=lambda x: x[0])


def query_location_options_with_counts(criteria=None, energy_method=None, direction=None, selected_scales=None, selected_climates=None):
    """Get location options with counts filtered by current search criteria"""
    # Get all records
    all_records = st.session_state.db.get_energy_data(limit=5000)
    
    # Filter out rejected records (keep NULL, approved, pending)
    records = [r for r in all_records if r.get('status') != 'rejected']
    
    # Apply criteria filter
    if criteria and criteria != "Select a determinant":
        records = [r for r in records if r.get('criteria') == criteria]
    
    # Apply energy method filter
    if energy_method and energy_method != "Select an output":
        records = [r for r in records if r.get('energy_method') == energy_method]
    
    # Apply direction filter
    if direction and direction not in ["Select a direction", None]:
        clean_direction = direction.split(" [")[0] if " [" in direction else direction
        records = [r for r in records if r.get('direction') == clean_direction]
    
    # Apply scale filter
    if selected_scales and selected_scales != ["All"]:
        records = [r for r in records if r.get('scale') in selected_scales]
    
    # Apply climate filter
    if selected_climates and selected_climates != ["All"]:
        selected_upper = [c.upper() for c in selected_climates]
        records = [r for r in records if r.get('climate') and r.get('climate').upper() in selected_upper]
    
    # Count locations
    location_counts = {}
    for record in records:
        location = record.get('location')
        if location:
            location_counts[location] = location_counts.get(location, 0) + 1
    
    return [(location, count) for location, count in sorted(location_counts.items())]


def query_building_use_options_with_counts(criteria=None, energy_method=None, direction=None, selected_scales=None, selected_climates=None, selected_locations=None):
    """Get building use options with counts filtered by current search criteria"""
    # Get all records
    all_records = st.session_state.db.get_energy_data(limit=5000)
    
    # Filter out rejected records (keep NULL, approved, pending)
    records = [r for r in all_records if r.get('status') != 'rejected']
    
    # Apply criteria filter
    if criteria and criteria != "Select a determinant":
        records = [r for r in records if r.get('criteria') == criteria]
    
    # Apply energy method filter
    if energy_method and energy_method != "Select an output":
        records = [r for r in records if r.get('energy_method') == energy_method]
    
    # Apply direction filter
    if direction and direction not in ["Select a direction", None]:
        clean_direction = direction.split(" [")[0] if " [" in direction else direction
        records = [r for r in records if r.get('direction') == clean_direction]
    
    # Apply scale filter
    if selected_scales and selected_scales != ["All"]:
        records = [r for r in records if r.get('scale') in selected_scales]
    
    # Apply climate filter
    if selected_climates and selected_climates != ["All"]:
        selected_upper = [c.upper() for c in selected_climates]
        records = [r for r in records if r.get('climate') and r.get('climate').upper() in selected_upper]
    
    # Apply location filter
    if selected_locations and selected_locations != ["All"]:
        records = [r for r in records if r.get('location') in selected_locations]
    
    # Count building uses
    building_use_counts = {}
    for record in records:
        building_use = record.get('building_use')
        if building_use:
            building_use_counts[building_use] = building_use_counts.get(building_use, 0) + 1
    
    return [(use, count) for use, count in sorted(building_use_counts.items())]


def query_approach_options_with_counts(criteria=None, energy_method=None, direction=None, selected_scales=None, selected_climates=None, selected_locations=None, selected_building_uses=None):
    """Get approach options with counts filtered by current search criteria"""
    # Get all records
    all_records = st.session_state.db.get_energy_data(limit=5000)
    
    # Filter out rejected records (keep NULL, approved, pending)
    records = [r for r in all_records if r.get('status') != 'rejected']
    
    # Apply criteria filter
    if criteria and criteria != "Select a determinant":
        records = [r for r in records if r.get('criteria') == criteria]
    
    # Apply energy method filter
    if energy_method and energy_method != "Select an output":
        records = [r for r in records if r.get('energy_method') == energy_method]
    
    # Apply direction filter
    if direction and direction not in ["Select a direction", None]:
        clean_direction = direction.split(" [")[0] if " [" in direction else direction
        records = [r for r in records if r.get('direction') == clean_direction]
    
    # Apply scale filter
    if selected_scales and selected_scales != ["All"]:
        records = [r for r in records if r.get('scale') in selected_scales]
    
    # Apply climate filter
    if selected_climates and selected_climates != ["All"]:
        selected_upper = [c.upper() for c in selected_climates]
        records = [r for r in records if r.get('climate') and r.get('climate').upper() in selected_upper]
    
    # Apply location filter
    if selected_locations and selected_locations != ["All"]:
        records = [r for r in records if r.get('location') in selected_locations]
    
    # Apply building use filter
    if selected_building_uses and selected_building_uses != ["All"]:
        records = [r for r in records if r.get('building_use') in selected_building_uses]
    
    # Count approaches
    approach_counts = {}
    for record in records:
        approach = record.get('approach')
        if approach:
            approach_counts[approach] = approach_counts.get(approach, 0) + 1
    
    return [(approach, count) for approach, count in sorted(approach_counts.items())]

def render_unified_search_interface(enable_editing=False):
    """Unified search interface used by both main app and admin"""
    
        # Get all records that are NOT rejected (includes NULL, approved, pending)
    all_records = st.session_state.db.get_energy_data(limit=5000)  # Get all records

    # Filter out rejected records in Python
    valid_records = []
    for record in all_records:
        status = record.get('status')
        # Include if status is not 'rejected' (includes NULL, 'approved', 'pending')
        if status != 'rejected':
            valid_records.append(record)

    print(f"Total valid records (excluding rejected): {len(valid_records)}")

    # Get counts for determinants from valid records
    criteria_counts = {}
    for record in valid_records:
        criteria = record.get('criteria')
        if criteria:
            criteria_counts[criteria] = criteria_counts.get(criteria, 0) + 1

    print(f"Unique criteria found: {len(criteria_counts)}")

    criteria_list = ["Select a determinant"] + [f"{criteria} [{count}]" for criteria, count in sorted(criteria_counts.items())]

    # Initialize filter variables
    selected_scales = []
    selected_climates = []
    selected_locations = []
    selected_building_uses = []
    selected_approaches = []
    selected_direction = None
    actual_method = None

    # UNIFIED FILTER LAYOUT
    selected_criteria = st.selectbox("Determinant", criteria_list, key="unified_criteria")
    actual_criteria = selected_criteria.split(" [")[0] if selected_criteria != "Select a determinant" else None

    if actual_criteria:
        # Filter valid_records to get energy methods for this criteria
        criteria_records = [r for r in valid_records if r.get('criteria') == actual_criteria]
        
        # Get energy method counts
        method_counts = {}
        for record in criteria_records:
            method = record.get('energy_method')
            if method:
                method_counts[method] = method_counts.get(method, 0) + 1
        
        method_list = ["Select an output"] + [f"{method} [{count}]" for method, count in sorted(method_counts.items())]
        
        selected_method = st.selectbox("Energy Output(s)", method_list, key="unified_method")
        actual_method = selected_method.split(" [")[0] if selected_method != "Select an output" else None
        
        if actual_method:
            direction_counts = query_direction_counts(actual_criteria, actual_method)
            
            # Ensure direction_counts is a dictionary with default values
            if not isinstance(direction_counts, dict):
                direction_counts = {'Increase': 0, 'Decrease': 0}
            
            increase_count = direction_counts.get('Increase', 0)
            decrease_count = direction_counts.get('Decrease', 0)
            
            selected_direction = st.radio(
                "Please select the direction of the relationship",
                [f"Increase [{increase_count}]", f"Decrease [{decrease_count}]"],
                index=None,
                key="unified_direction"
            )
        else:
            # No energy output selected - don't show direction options at all
            selected_direction = None

        # Add debug to see what's being selected
        if selected_direction:
            #st.sidebar.write(f"Selected direction: {selected_direction}")
            if selected_direction:
                # Filters
                col_scale, col_climate = st.columns(2)
                
                with col_scale:
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
                        actual_criteria, actual_method, selected_direction, 
                        current_climate_filter, current_location_filter
                    )
                    
                    if scale_options_with_counts:
                        if 'unified_selected_scale' not in st.session_state:
                            st.session_state.unified_selected_scale = "All"
                        
                        scale_options_formatted = ["All"] + [f"{scale} [{count}]" for scale, count in scale_options_with_counts]
                        
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
                    current_scale_filter = []
                    if 'unified_selected_scale' in st.session_state and st.session_state.unified_selected_scale != "All":
                        scale_name = st.session_state.unified_selected_scale.split(" [")[0]
                        current_scale_filter = [scale_name]
                    
                    current_location_filter = []
                    if 'unified_selected_location' in st.session_state and st.session_state.unified_selected_location != "All":
                        location_name = st.session_state.unified_selected_location.split(" [")[0]
                        current_location_filter = [location_name]
                    
                    climate_options_with_counts = query_climate_options_with_counts(
                        actual_criteria,
                        actual_method,
                        selected_direction,
                        current_scale_filter
                    )
                    
                    if climate_options_with_counts:
                        if 'unified_selected_climate' not in st.session_state:
                            st.session_state.unified_selected_climate = "All"
                        
                        climate_options_formatted = ["All"] + [formatted for formatted, color, count in climate_options_with_counts]
                        
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

                # Location and Building Use filters
                col_location, col_building_use = st.columns(2)
                
                with col_location:
                    current_direction = selected_direction.split(" [")[0] if " [" in selected_direction else selected_direction
                    
                    location_options_with_counts = query_location_options_with_counts(
                        actual_criteria, actual_method, current_direction, 
                        selected_scales, selected_climates
                    )
                    
                    if location_options_with_counts:
                        if 'unified_selected_location' not in st.session_state:
                            st.session_state.unified_selected_location = "All"
                        
                        location_options_formatted = ["All"] + [f"{location} [{count}]" for location, count in location_options_with_counts]
                        
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
                    building_use_options_with_counts = query_building_use_options_with_counts(
                        actual_criteria, actual_method, current_direction,
                        selected_scales, selected_climates, selected_locations
                    )
                    
                    if building_use_options_with_counts:
                        if 'unified_selected_building_use' not in st.session_state:
                            st.session_state.unified_selected_building_use = "All"
                        
                        building_use_options_formatted = ["All"] + [f"{use} [{count}]" for use, count in building_use_options_with_counts]
                        
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

                # Approach filter
                col_approach = st.columns(1)[0]
                
                with col_approach:
                    approach_options_with_counts = query_approach_options_with_counts(
                        actual_criteria, actual_method, current_direction,
                        selected_scales, selected_climates, selected_locations, selected_building_uses
                    )
                    
                    if approach_options_with_counts:
                        if 'unified_selected_approach' not in st.session_state:
                            st.session_state.unified_selected_approach = "All"
                        
                        approach_options_formatted = ["All"] + [f"{approach} [{count}]" for approach, count in approach_options_with_counts]
                        
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
    filtered_records = all_records
    if actual_criteria:
        filtered_records = [r for r in filtered_records if r.get('criteria') == actual_criteria]
    if actual_method:
        filtered_records = [r for r in filtered_records if r.get('energy_method') == actual_method]
    if selected_direction:
        clean_direction = selected_direction.split(" [")[0] if selected_direction else None
        filtered_records = [r for r in filtered_records if r.get('direction') == clean_direction]
    if selected_scales:
        filtered_records = [r for r in filtered_records if r.get('scale') in selected_scales]
    if selected_climates:
        selected_climates_upper = [c.upper() for c in selected_climates]
        filtered_records = [r for r in filtered_records if r.get('climate') and r.get('climate').upper() in selected_climates_upper]
    if selected_locations:
        filtered_records = [r for r in filtered_records if r.get('location') in selected_locations]
    if selected_building_uses:
        filtered_records = [r for r in filtered_records if r.get('building_use') in selected_building_uses]
    if selected_approaches:
        filtered_records = [r for r in filtered_records if r.get('approach') in selected_approaches]

    # ============= RESULTS DISPLAY =============
    if actual_criteria and actual_method and selected_direction:
        if len(filtered_records) == 1:
            st.markdown(f"<p><b>The following study shows that an increase (or presence) in {actual_criteria} leads to <i>{'higher' if 'Increase' in selected_direction else 'lower'}</i> {actual_method}.</b></p>", unsafe_allow_html=True)
        else:
            st.markdown(f"<p><b>The following {len(filtered_records)} studies show that an increase (or presence) in {actual_criteria} leads to <i>{'higher' if 'Increase' in selected_direction else 'lower'}</i> {actual_method}.</b></p>", unsafe_allow_html=True)

        # PAGINATION
        RECORDS_PER_PAGE = 10
        if len(filtered_records) > RECORDS_PER_PAGE:
            if "results_page" not in st.session_state:
                st.session_state.results_page = 0
            
            total_pages = (len(filtered_records) + RECORDS_PER_PAGE - 1) // RECORDS_PER_PAGE
            
            col_prev, col_page, col_next = st.columns([1, 2, 1])
            with col_prev:
                if st.button("◀ Previous", disabled=st.session_state.results_page == 0, key="prev_results_page"):
                    st.session_state.results_page = max(0, st.session_state.results_page - 1)
                    st.rerun()
            with col_page:
                st.write(f"**Page {st.session_state.results_page + 1} of {total_pages}**")
            with col_next:
                if st.button("Next ▶", disabled=st.session_state.results_page >= total_pages - 1, key="next_results_page"):
                    st.session_state.results_page = min(total_pages - 1, st.session_state.results_page + 1)
                    st.rerun()
            
            start_idx = st.session_state.results_page * RECORDS_PER_PAGE
            end_idx = min(start_idx + RECORDS_PER_PAGE, len(filtered_records))
            display_records = filtered_records[start_idx:end_idx]
            st.write(f"**Showing {start_idx + 1}-{end_idx} of {len(filtered_records)} records**")
        else:
            display_records = filtered_records
            if len(filtered_records) > 0:
                st.write(f"**Showing all {len(filtered_records)} records**")

        # DISPLAY EACH RECORD
        for count, record in enumerate(display_records, start=1):
            # Access dictionary values by key instead of tuple unpacking
            record_id = record['id']
            criteria = record.get('criteria', '')
            energy_method = record.get('energy_method', '')
            direction = record.get('direction', '')
            paragraph = record.get('paragraph', '')
            user = record.get('user', '')
            status = record.get('status', '')
            scale = record.get('scale', '')
            climate = record.get('climate', '')
            location = record.get('location', '')
            building_use = record.get('building_use', '')
            approach = record.get('approach', '')
            sample_size = record.get('sample_size', '')
            
            st.markdown("---")
                    
            col1, col2 = st.columns(2)
            
            with col1:
                clean_criteria = sanitize_metadata_text(criteria)
                clean_energy_method = sanitize_metadata_text(energy_method)
                clean_location = sanitize_metadata_text(location) if location else None
                clean_building_use = sanitize_metadata_text(building_use) if building_use else None
                
                st.write(f"**{clean_criteria}** → **{clean_energy_method}** ({direction})")
                st.write(f"**Record ID:** `{record_id}`")
                if clean_location:
                    st.write(f"**Location:** {clean_location}")
                if clean_building_use:
                    st.write(f"**Building Use:** {clean_building_use}")
            
            with col2:
                st.write(f"**Scale:** {scale}")
                if climate:
                    color = get_climate_color(climate)
                    
                    climate_descriptions = {
                        'Af': 'Tropical Rainforest', 'Am': 'Tropical Monsoon', 'Aw': 'Tropical Savanna',
                        'BWh': 'Hot Desert', 'BWk': 'Cold Desert', 'BSh': 'Hot Semi-arid', 'BSk': 'Cold Semi-arid',
                        'Cfa': 'Humid Subtropical', 'Cfb': 'Oceanic', 'Cfc': 'Subpolar Oceanic',
                        'Csa': 'Hot-summer Mediterranean', 'Csb': 'Warm-summer Mediterranean',
                        'Cwa': 'Monsoon-influenced Humid Subtropical',
                        'Dfa': 'Hot-summer Humid Continental', 'Dfb': 'Warm-summer Humid Continental', 
                        'Dfc': 'Subarctic', 'Dfd': 'Extremely Cold Subarctic',
                        'Dwa': 'Monsoon-influenced Hot-summer Humid Continental',
                        'Dwb': 'Monsoon-influenced Warm-summer Humid Continental',
                        'Dwc': 'Monsoon-influenced Subarctic',
                        'Dwd': 'Monsoon-influenced Extremely Cold Subarctic',
                        'ET': 'Tundra', 'EF': 'Ice Cap',
                        'Var': 'Varies / Multiple Climates'
                    }
                    
                    climate_code = climate
                    if " - " in str(climate):
                        climate_code = climate.split(" - ")[0]
                    climate_code = ''.join([c for c in str(climate_code) if c.isalnum()])
                    
                    description = climate_descriptions.get(climate_code, '')
                    
                    if description:
                        climate_display = f"{climate_code} - {description}"
                    else:
                        climate_display = climate_code
                        
                    st.markdown(
                        f"**Climate:** <span style='background-color: {color}; padding: 2px 8px; border-radius: 10px; color: black;'>{climate_display}</span>", 
                        unsafe_allow_html=True
                    )
                
                if approach:
                    st.write(f"**Approach:** {approach}")
                if sample_size:
                    st.write(f"**Sample Size:** {sample_size}")

            # STUDY CONTENT
            highlighted_paragraph = paragraph
            if actual_criteria:
                import re
                pattern = re.compile(re.escape(actual_criteria), re.IGNORECASE)
                highlighted_paragraph = pattern.sub(
                    lambda m: f"<span style='background-color: #FFFF00; font-weight: bold;'>{m.group()}</span>", 
                    highlighted_paragraph
                )
            if actual_method:
                pattern = re.compile(re.escape(actual_method), re.IGNORECASE)
                highlighted_paragraph = pattern.sub(
                    lambda m: f"<span style='background-color: #FFFF00; font-weight: bold;'>{m.group()}</span>", 
                    highlighted_paragraph
                )
            
            paragraph_with_links = convert_urls_to_links(highlighted_paragraph)
            
            st.markdown(
                f'''
                <div style="
                    border: 1px solid #e0e0e0;
                    padding: 15px;
                    border-radius: 8px;
                    background-color: #f9f9fb;
                    max-height: 250px;
                    overflow-y: auto;
                    font-family: Arial, sans-serif;
                    line-height: 1.5;
                    font-size: 14px;
                    user-select: text;
                    -webkit-user-select: text;
                    cursor: text;
                ">
                    {paragraph_with_links}
                </div>
                ''',
                unsafe_allow_html=True
            )
    
    elif actual_criteria or actual_method or selected_direction:
        st.warning("Please select a determinant, energy output, and direction to see results")
    else:
        st.info("Use the filters above to explore the database")

# MAIN APP LAYOUT
if "current_tab" not in st.session_state:
    st.session_state.current_tab = "tab0"

if st.session_state.logged_in:
    if st.session_state.current_user == "admin":
        # Admin view
        tab_labels = ["SpatialBuild Energy", "Studies", "Contribute", "Edit/Review"]
        tabs = st.tabs(tab_labels)
        tab0, tab1, tab2, tab3 = tabs
        
        with tab0:
            render_spatialbuild_tab(enable_editing=False)
            st.session_state.current_tab = "tab0"
        
        with tab1:
            render_enhanced_papers_tab()
            st.session_state.current_tab = "tab1"
        
        with tab2:
            render_contribute_tab()
            st.session_state.current_tab = "tab2"
        
        with tab3:
            if st.session_state.get("admin_editing_in_missing_data", False):
                if st.button("← Back to Missing Data Review"):
                    record_id = st.session_state.get("admin_current_edit_record_id")
                    if record_id and f"edit_missing_record_{record_id}" in st.session_state:
                        st.session_state[f"edit_missing_record_{record_id}"] = False
                    if "admin_editing_in_missing_data" in st.session_state:
                        del st.session_state["admin_editing_in_missing_data"]
                    if "admin_current_edit_record_id" in st.session_state:
                        del st.session_state["admin_current_edit_record_id"]
                    st.rerun()
                st.markdown("---")
            
            admin_dashboard()
            st.session_state.current_tab = "tab3"
        
        render_admin_sidebar()

    else:  
        # Regular user view
        tab_labels = ["SpatialBuild Energy", "Studies", "Contribute", "Your Contributions"]
        tabs = st.tabs(tab_labels)
        tab0, tab1, tab2, tab3 = tabs
        
        with tab0:
            render_spatialbuild_tab(enable_editing=False)
            st.session_state.current_tab = "tab0"
        
        with tab1:
            render_enhanced_papers_tab()
            st.session_state.current_tab = "tab1"
        
        with tab2:
            render_contribute_tab()
            st.session_state.current_tab = "tab2"
        
        with tab3:
            user_dashboard()
            st.session_state.current_tab = "tab3"
        
        render_user_sidebar()

else:  
    # Not logged in view
    tab_labels = ["SpatialBuild Energy", "Studies", "Contribute"]
    tabs = st.tabs(tab_labels)
    tab0, tab1, tab2 = tabs
    
    with tab0:
        render_spatialbuild_tab(enable_editing=False)
        st.session_state.current_tab = "tab0"
    
    with tab1:
        render_enhanced_papers_tab()
        st.session_state.current_tab = "tab1"
    
    with tab2:
        render_contribute_tab()
        st.session_state.current_tab = "tab2"
    
    render_guest_sidebar()

# Footer
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