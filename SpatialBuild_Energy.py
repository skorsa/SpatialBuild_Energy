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
if "papers_page" not in st.session_state:
    st.session_state.papers_page = 0


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

def safe_rerun(target_tab="tab3"):
    """Safely rerun while preserving the target tab"""
    st.session_state.current_tab = target_tab
    st.rerun()

def check_button_clicks():
    """Debug function to check if buttons are being clicked"""
    if 'button_clicks' not in st.session_state:
        st.session_state.button_clicks = {}
    
    # Add to your reject button callback:
    # st.session_state.button_clicks[f'reject_{record_id}'] = time.time()
    
    st.sidebar.write("Button click history:")
    for btn, timestamp in st.session_state.button_clicks.items():
        st.sidebar.write(f"{btn}: {datetime.fromtimestamp(timestamp).strftime('%H:%M:%S')}")

def sanitize_metadata_text(text):
    """Remove markdown formatting characters from metadata text"""
    if not text or pd.isna(text):
        return text
    
    text = str(text)
    
    # Remove markdown formatting characters
    # Bold: **text** or __text__
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # Remove ** **
    text = re.sub(r'__(.*?)__', r'\1', text)      # Remove __ __
    
    # Italic: *text* or _text_
    text = re.sub(r'\*(.*?)\*', r'\1', text)      # Remove * *
    text = re.sub(r'_(.*?)_', r'\1', text)        # Remove _ _
    
    # Remove any remaining asterisks that might be hanging
    text = text.replace('**', '').replace('*', '')
    
    return text.strip()

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

        st.markdown("---")
        st.subheader("Additional Information (Optional)")

        # First row: Scale, Climate, and Location
        col_1, col_2, col_3 = st.columns(3)

        with col_1:
            scale_options = query_dynamic_scale_options(conn)
            selected_scale = st.selectbox(
                "Scale",
                options=["Select scale"] + scale_options + ["Add new scale"],
                key="contribute_scale"
            )
            
            new_scale = ""
            if selected_scale == "Add new scale":
                new_scale = st.text_input("Enter new scale", key="contribute_new_scale")

        with col_2:
            # Get ONLY valid Köppen climate options - NO "Add new climate" option
            climate_options_data = query_dominant_climate_options(conn)
            climate_options = [formatted for formatted, color in climate_options_data]
            
            # REMOVED "Add new climate" - only valid Köppen codes
            selected_climate = st.selectbox(
                "Climate",
                options=["Select climate"] + climate_options,  # No "Add new climate"
                key="contribute_climate"
            )
            
            # NO new_climate input field - removed entirely
            final_climate = None
            if selected_climate != "Select climate":
                # Clean climate code if it's formatted
                if " - " in selected_climate:
                    final_climate = selected_climate.split(" - ")[0]
                    # Remove emoji if present
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
            # Building Use dropdown
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
            # Approach dropdown (3 specific options)
            approach_options = ["Select approach", "Top-down", "Bottom-up", "Hybrid (combined top-down and bottom-up)"]
            selected_approach = st.selectbox(
                "Approach",
                options=approach_options,
                key="contribute_approach"
            )

        with col_6:
            # Sample Size text field
            sample_size = st.text_input(
                "Sample Size (optional)", 
                key="contribute_sample_size",
                placeholder="e.g., 50 buildings, 1000 households, 5 cities"
            )

        st.markdown("---")

        # Save button
        if st.button("Save", key="save_new_record"):
            # Save record only if text is provided
            if new_paragraph.strip():
                cursor = conn.cursor()

                # Prepare scale and climate values
                final_scale = new_scale if selected_scale == "Add new scale" else selected_scale
                
                # Climate - only from dropdown, no free text
                if selected_climate != "Select climate":
                    if " - " in selected_climate:
                        final_climate = selected_climate.split(" - ")[0]
                        # Remove emoji if present
                        final_climate = ''.join([c for c in final_climate if c.isalnum()])
                    else:
                        final_climate = selected_climate
                else:
                    final_climate = None  # Don't store "Select climate" as a value

                # Prepare building use value
                final_building_use = new_building_use if selected_building_use == "Add new building use" else selected_building_use
                
                # Prepare approach value
                final_approach = selected_approach if selected_approach != "Select approach" else None
                
                # Prepare sample size value
                final_sample_size = sample_size if sample_size.strip() else None

                # Save the record with all fields
                cursor.execute('''
                    INSERT INTO energy_data (criteria, energy_method, direction, paragraph, status, user, 
                                           scale, climate, location, building_use, approach, sample_size)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    new_determinant or st.session_state.selected_determinant_choice,
                    new_energy_output or st.session_state.selected_energy_output_choice,
                    st.session_state.selected_selected_direction,
                    new_paragraph,
                    "pending",
                    st.session_state.current_user,
                    final_scale if final_scale != "Select scale" else "Awaiting data",
                    final_climate,  # Now properly handles None
                    location if location else None,
                    final_building_use if final_building_use != "Select building use" else None,
                    final_approach,
                    final_sample_size
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

def admin_import_and_match_studies_simple(uploaded_file):
    """
    Simplified study matching - ONLY matches study titles against paragraph content
    AUTOMATICALLY detects study column
    """
    global conn
    
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
            # Fallback to first column
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

        cursor = conn.cursor()
        
        for i, study_name in enumerate(study_names):
            if pd.isna(study_name) or not study_name:
                continue
                
            # Clean and normalize the study name
            clean_study = preprocess_study_name(study_name)
            
            status_text.text(f"Searching: {clean_study[:50]}...")
            
            # Find matches
            matches = find_study_matches_in_paragraph(cursor, clean_study, study_name)
            
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


def find_all_study_matches_in_paragraph(cursor, clean_study, original_study):
    """
    Find ALL matches using multiple title-based strategies - ONLY against paragraph field
    Returns ALL matching database records, not just the first one
    """
    all_matches = []
    
    # Strategy 1: Exact substring match in paragraph - get ALL matches
    exact_matches = find_all_exact_substring_matches_in_paragraph(cursor, clean_study, original_study)
    all_matches.extend(exact_matches)
    
    # Only try other strategies if no exact matches found
    if not all_matches:
        # Strategy 2: Significant portion matching (80% of title) - get ALL matches
        significant_matches = find_all_significant_portion_matches_in_paragraph(cursor, clean_study, original_study)
        all_matches.extend(significant_matches)
    
    if not all_matches:
        # Strategy 3: Keyword matching with significant words - get ALL matches
        keyword_matches = find_all_keyword_based_matches_in_paragraph(cursor, clean_study, original_study)
        all_matches.extend(keyword_matches)
    
    return all_matches


def find_exact_substring_matches_in_paragraph(cursor, clean_study, original_study):
    """Find exact or near-exact substring matches - ONLY in paragraph field"""
    matches = []
    
    # Try different variations of the study title
    search_terms = [
        clean_study,
        original_study,  # Try original first
    ]
    
    # Remove duplicates and short terms
    search_terms = list(dict.fromkeys([term for term in search_terms if term and len(term) > 10]))
    
    for term in search_terms:
        try:
            # ONLY search in paragraph field
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
                    match_percentage = (len(term) / len(paragraph)) * 100 if len(paragraph) > 0 else 0
                    
                    # Determine confidence level based on match quality
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


def find_all_significant_portion_matches_in_paragraph(cursor, clean_study, original_study):
    """Find ALL matches using significant portions of the study title - ONLY in paragraph field"""
    matches = []
    
    # Try different portions of the title
    portions_to_try = []
    
    # If title is long, try first 80% and last 80%
    if len(clean_study) > 30:
        portion_80 = int(len(clean_study) * 0.8)
        if portion_80 > 15:
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
            # Get ALL matching records
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
                    match_percentage = (len(portion) / len(clean_study)) * 100 if len(clean_study) > 0 else 0
                    
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
    
    # Remove duplicate record IDs
    unique_matches = []
    seen_ids = set()
    for match in matches:
        if match['record_id'] not in seen_ids:
            unique_matches.append(match)
            seen_ids.add(match['record_id'])
    
    return unique_matches

def find_all_study_matches_in_paragraph(cursor, clean_study, original_study):
    """
    Find ALL matches using multiple title-based strategies - ONLY against paragraph field
    Returns ALL matching database records, not just the first one
    """
    all_matches = []
    
    # Strategy 1: Exact substring match in paragraph - get ALL matches
    exact_matches = find_all_exact_substring_matches_in_paragraph(cursor, clean_study, original_study)
    all_matches.extend(exact_matches)
    
    # Only try other strategies if no exact matches found
    if not all_matches:
        # Strategy 2: Significant portion matching (80% of title) - get ALL matches
        significant_matches = find_all_significant_portion_matches_in_paragraph(cursor, clean_study, original_study)
        all_matches.extend(significant_matches)
    
    if not all_matches:
        # Strategy 3: Keyword matching with significant words - get ALL matches
        keyword_matches = find_all_keyword_based_matches_in_paragraph(cursor, clean_study, original_study)
        all_matches.extend(keyword_matches)
    
    return all_matches

def find_all_keyword_based_matches_in_paragraph(cursor, clean_study, original_study):
    """Find ALL matches based on significant keywords from the title - ONLY in paragraph field"""
    matches = []
    
    # Extract meaningful keywords (excluding common words)
    keywords = extract_significant_keywords(clean_study)
    
    if len(keywords) >= 2:  # Need at least 2 significant keywords
        # Search for each keyword individually and combine results
        potential_matches = {}
        
        for keyword in keywords[:5]:  # Limit to first 5 keywords
            try:
                # Get ALL matching records for this keyword
                cursor.execute('''
                    SELECT id, paragraph, criteria, energy_method, direction, scale, climate, location
                    FROM energy_data 
                    WHERE LOWER(paragraph) LIKE LOWER(?)
                ''', (f'%{keyword}%',))
                
                results = cursor.fetchall()
                
                for result in results:
                    record_id = result[0]
                    
                    if record_id not in potential_matches:
                        potential_matches[record_id] = {
                            'record': result,
                            'keywords_found': 0,
                            'paragraph': result[1]
                        }
                    
                    potential_matches[record_id]['keywords_found'] += 1
            except Exception as e:
                # Skip this keyword if it causes SQL errors
                continue
        
        # Keep ALL records that found multiple keywords
        for record_id, match_data in potential_matches.items():
            if match_data['keywords_found'] >= 2:  # At least 2 keywords found
                record_id, paragraph, criteria, energy_method, direction, scale, climate, location = match_data['record']
                confidence_score = (match_data['keywords_found'] / min(len(keywords), 5)) * 100
                
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
                        'matching_text': f"Keywords: {', '.join(keywords[:3])}"
                    })
    
    # Remove duplicate record IDs
    unique_matches = []
    seen_ids = set()
    for match in matches:
        if match['record_id'] not in seen_ids:
            unique_matches.append(match)
            seen_ids.add(match['record_id'])
    
    return unique_matches

def import_location_climate_data_unique():
    """Import climate, location, scale, building use, approach and sample size data - LOADS NOTHING UNTIL CONFIRMATION"""
    global conn
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
    uploaded_file = st.file_uploader("Upload Excel file with location/climate data", 
                                   type=["xlsx", "csv", "ods"],
                                   key="location_climate_import_unique")
    
    if uploaded_file is not None:
        try:
            # Read the file ONCE to show preview
            df = pd.read_excel(uploaded_file, sheet_name=0)
            
            # Show preview
            st.write("**Preview of data to import:**")
            st.dataframe(df.head(10))
            
            # Show column names
            st.write(f"**Columns found in file:** {list(df.columns)}")
            
            # Column mapping interface
            st.subheader("Map Columns")
            st.write("Select which column in your Excel file corresponds to each database field:")
            
            col_mapper1, col_mapper2 = st.columns(2)
            
            with col_mapper1:
                study_column = st.selectbox(
                    "📄 Study Title Column (REQUIRED)",
                    options=["-- Select column --"] + list(df.columns),
                    key="map_study_column"
                )
                
                location_column = st.selectbox(
                    "📍 Location Column",
                    options=["-- None --"] + list(df.columns),
                    key="map_location_column"
                )
                
                climate_column = st.selectbox(
                    "🌍 Climate Column",
                    options=["-- None --"] + list(df.columns),
                    key="map_climate_column"
                )
                
                scale_column = st.selectbox(
                    "📏 Scale Column",
                    options=["-- None --"] + list(df.columns),
                    key="map_scale_column"
                )
            
            with col_mapper2:
                building_use_column = st.selectbox(
                    "🏢 Building Use Column",
                    options=["-- None --"] + list(df.columns),
                    key="map_building_use_column"
                )
                
                approach_column = st.selectbox(
                    "🔬 Approach Column",
                    options=["-- None --"] + list(df.columns),
                    key="map_approach_column"
                )
                
                sample_size_column = st.selectbox(
                    "📊 Sample Size Column",
                    options=["-- None --"] + list(df.columns),
                    key="map_sample_size_column"
                )
            
            # Import options
            st.markdown("---")
            st.subheader("Import Options")
            
            import_method = st.radio(
                "Choose import method:",
                ["🔍 Enhanced Matching (recommended)", "⚡ Direct Import (simple)"],
                key="import_method_choice"
            )
            
            # PROCESS BUTTON - This is the ONLY place we do the matching
            if st.button("🔍 FIND MATCHES", type="primary", key="find_matches_button"):
                
                if study_column == "-- Select column --":
                    st.error("❌ Please select a Study Title column")
                    return
                
                with st.spinner("Processing import..."):
                    # Clear ALL existing import session state
                    keys_to_delete = [k for k in st.session_state.keys() if 
                                    k.startswith("import_session_") or 
                                    k.startswith("match_confirmations_") or
                                    k.startswith("select_all_active_") or
                                    k.startswith("match_page_") or
                                    k.startswith("matched_records_") or
                                    k.startswith("unmatched_studies_") or
                                    k.startswith("excel_df_")]
                    for key in keys_to_delete:
                        if key in st.session_state:
                            del st.session_state[key]
                    
                    # Create new session ID
                    session_id = f"import_{int(time.time())}"
                    st.session_state[f"import_session_{session_id}"] = True
                    st.session_state.current_import_session = session_id
                    
                    # Store the dataframe
                    uploaded_file.seek(0)
                    df_full = pd.read_excel(uploaded_file, sheet_name=0)
                    st.session_state[f"excel_df_{session_id}"] = df_full
                    st.session_state[f"study_column_{session_id}"] = study_column
                    
                    if "🔍 Enhanced Matching" in import_method:
                        # Perform matching ONCE and store results
                        matched_records, unmatched_studies = perform_study_matching(df_full, study_column)
                        
                        # Store results in session state
                        st.session_state[f"matched_records_{session_id}"] = matched_records
                        st.session_state[f"unmatched_studies_{session_id}"] = unmatched_studies
                        
                        st.success(f"✅ Found {len(matched_records)} matches and {len(unmatched_studies)} unmatched studies")
                        st.rerun()
                    else:
                        # Direct import code
                        pass
            
            # DISPLAY RESULTS - This runs on every rerun, but only shows stored results
            # Check if we have a current import session with results
            current_session = st.session_state.get("current_import_session")
            if current_session:
                matched_records = st.session_state.get(f"matched_records_{current_session}")
                unmatched_studies = st.session_state.get(f"unmatched_studies_{current_session}")
                excel_df = st.session_state.get(f"excel_df_{current_session}")
                
                if matched_records is not None and unmatched_studies is not None:
                    # Display the matching review with stored data
                    display_admin_matching_review_fixed(matched_records, unmatched_studies, excel_df, current_session)
                elif "🔍 Enhanced Matching" in import_method:
                    st.info("👆 Click 'FIND MATCHES' to start the matching process")
            else:
                if "🔍 Enhanced Matching" in import_method:
                    st.info("👆 Click 'FIND MATCHES' to start the matching process")
                        
        except Exception as e:
            st.error(f"Error reading Excel file: {str(e)}")
            import traceback
            st.error(f"Detailed error: {traceback.format_exc()}")

def perform_study_matching(df, study_column):
    """Perform the actual matching and return results - EXACT MATCHES ONLY"""
    global conn
    
    # Get study names
    study_names = df[study_column].dropna().unique()
    
    matched_records = []
    unmatched_studies = []
    
    cursor = conn.cursor()
    
    for study_name in study_names:
        if pd.isna(study_name) or not study_name:
            continue
            
        # Clean and normalize the study name
        clean_study = preprocess_study_name(study_name)
        
        # Find matches - exact only
        matches = find_study_matches_in_paragraph(cursor, clean_study, study_name)
        
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
                    'match_percentage': 100,  # Set to 100 for exact matches
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
    """
    Display the matching review interface - EXACT MATCHES ONLY with paragraph preview
    """
    
    # Initialize session state for this session if not exists
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
            # Clear this session's data
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
    
    # Display match statistics
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
    
    # Select All checkbox for exact matches only
    select_all = st.checkbox(
        f"Select All {len(exact_matches)} Exact Matches", 
        key=f"select_all_{session_id}",
        value=st.session_state[select_all_key]
    )
    
    # Update select all state
    if select_all != st.session_state[select_all_key]:
        st.session_state[select_all_key] = select_all
        confirmations = st.session_state[confirmations_key]
        for match in exact_matches:
            match_id = f"match_{match['db_record_id']}_{session_id}"
            confirmations[match_id] = select_all
        st.session_state[confirmations_key] = confirmations
        st.rerun()
    
    # IMPORT BUTTON
    st.markdown("---")
    col1, col2 = st.columns([3, 1])
    with col1:
        if st.button("IMPORT SELECTED EXACT MATCHES", type="primary", use_container_width=True, key=f"import_main_{session_id}"):
            # Collect confirmed exact matches
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
                            # Clear confirmations after successful import
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
    
    # Display current page exact matches
    start_idx = st.session_state[page_key] * MATCHES_PER_PAGE
    end_idx = min(start_idx + MATCHES_PER_PAGE, len(exact_matches))
    current_page_matches = exact_matches[start_idx:end_idx]
    
    confirmations = st.session_state[confirmations_key]
    
    for i, match in enumerate(current_page_matches):
        match_id = f"match_{match['db_record_id']}_{session_id}"
        
        # Initialize confirmation state if not exists
        if match_id not in confirmations:
            confirmations[match_id] = True  # Default to True for exact matches
            st.session_state[confirmations_key] = confirmations
        
        # EXPANDER WITH PARAGRAPH PREVIEW IN TITLE
        paragraph_preview = match['matching_paragraph'][:80] + "..." if len(match['matching_paragraph']) > 80 else match['matching_paragraph']
        
        with st.expander(
            f"🟢 ID: {match['db_record_id']} | {match['excel_study'][:60]}... | 📄 {paragraph_preview}", 
            expanded=False  # Start collapsed to save space
        ):
            # THREE COLUMN LAYOUT: Import checkbox + Study + Paragraph Preview
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
                
                # Highlight the match
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
                
                # Add copy button for paragraph
                st.markdown("---")
                st.caption("📋 Select text above to copy or use Ctrl+C")
        
        st.markdown("---")
    
    # Bottom import button for exact matches
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
    
    # Unmatched studies section with more detail
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
                    
                    # Add copy button
                    st.code(unmatched['study_name'], language="text")
                    
                    # Optional: Quick search button
                    if st.button(f"🔍 Search manually", key=f"manual_search_{i}_{session_id}"):
                        st.info("Copy the study title above and search in the database manually")
            
            if len(filtered_unmatched) > 20:
                st.write(f"... and {len(filtered_unmatched) - 20} more")

def reset_location_climate_scale_data():
    """Clear all climate, location, scale, building use, approach and sample size data and reset to defaults"""
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
        st.success("✅ All imported data cleared and reset! (climate, location, scale, building use, approach and sample size data)")
        
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
    """Get ONLY valid Köppen climate classifications with descriptions and color glyphs"""
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
        # Tropical - Blues
        '#0000FE': '🟦',  # Af
        '#0077FD': '🟦',  # Am
        '#44A7F8': '🟦',  # Aw
        
        # Arid - Reds/Oranges/Yellows
        '#FD0000': '🟥',  # BWh
        '#F89292': '🟥',  # BWk
        '#F4A400': '🟧',  # BSh
        '#FEDA60': '🟨',  # BSk
        
        # Temperate - Greens/Yellows
        '#FFFE04': '🟨',  # Csa
        '#CDCE08': '🟨',  # Csb
        '#95FE97': '🟩',  # Cwa
        '#62C764': '🟩',  # Cwb
        '#379632': '🟩',  # Cwc
        '#C5FF4B': '🟩',  # Cfa
        '#64FD33': '🟩',  # Cfb
        '#36C901': '🟩',  # Cfc
        
        # Continental - Purples/Blues
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
        
        # Polar - Grays
        '#AFB0AB': '⬜',  # ET
        '#686964': '⬛',  # EF
        
        # Special cases
        '#999999': '⬜',  # Gray for special cases
    }
    
    # Filter to ONLY include valid Köppen classifications and special cases
    valid_climates = []
    seen_codes = set()
    
    for climate in climates:
        if not climate or pd.isna(climate) or str(climate).strip() == '':
            continue
            
        # Clean the climate code
        climate_clean = str(climate).strip()
        if " - " in climate_clean:
            climate_clean = climate_clean.split(" - ")[0]
        climate_clean = ''.join([c for c in climate_clean if c.isalnum()])
        
        # Skip if empty after cleaning
        if not climate_clean:
            continue
            
        # Check if it's a valid Köppen code or special case
        climate_upper = climate_clean.upper()
        if climate_upper in koppen_climates_with_descriptions:
            if climate_clean not in seen_codes:  # Avoid duplicates
                seen_codes.add(climate_clean)
                description = koppen_climates_with_descriptions[climate_upper]
                color = get_climate_color(climate_clean)
                emoji = color_to_emoji.get(color, '⬜')
                formatted_climate = f"{emoji} {climate_clean} - {description}"
                valid_climates.append((climate_clean, formatted_climate, color))
        elif climate_upper in special_cases:
            if climate_clean not in seen_codes:  # Avoid duplicates
                seen_codes.add(climate_clean)
                description = special_cases[climate_upper]
                color = '#999999'  # Gray for special cases
                emoji = '⬜'
                formatted_climate = f"{emoji} {climate_clean} - {description}"
                valid_climates.append((climate_clean, formatted_climate, color))
    
    # If no valid climates found in database, return the full list of all Köppen codes plus special cases
    if not valid_climates:
        all_climates = {**koppen_climates_with_descriptions, **special_cases}
        for climate_code, description in all_climates.items():
            color = get_climate_color(climate_code) if climate_code in koppen_climates_with_descriptions else '#999999'
            emoji = color_to_emoji.get(color, '⬜')
            formatted_climate = f"{emoji} {climate_code} - {description}"
            valid_climates.append((climate_code, formatted_climate, color))
    
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
    
    # Always show the dashboard title
    st.subheader("Admin Dashboard")
    
    # Tab interface for different admin functions
    tab1, tab2, tab3, tab4 = st.tabs(["Edit Records", "Review Pending Submissions", "Data Import", "Missing Data Review"])
    
    with tab1:
        manage_scale_climate_data()
    
    with tab2:
        review_pending_data()
        
    with tab3:
        # Make sure this doesn't auto-load
        import_location_climate_data_unique()
    
    with tab4:
        review_missing_data()
    
    return


def preprocess_study_name(study_name):
    """Clean and normalize study names - MINIMAL preprocessing"""
    if pd.isna(study_name) or not study_name:
        return ""
    
    # Convert to string and strip
    clean_name = str(study_name).strip()
    
    # Remove extra whitespace and newlines ONLY
    clean_name = ' '.join(clean_name.split())
    
    # DO NOT remove any prefixes - keep the title as intact as possible
    # DO NOT lowercase here - we do case-insensitive matching in SQL
    
    return clean_name

def show_edit_modal(record_id, from_missing_data=False):
    """Show a modal-like edit form at the top of the page"""
    st.subheader(f"Editing Record {record_id}")
    
    # Add a back button at the top
    # col_back, _ = st.columns([1, 3])
    # with col_back:
    #     if st.button("← Back to Missing Data Review", key=f"back_from_edit_{record_id}"):
    #         # Clear edit mode
    #         if f"edit_missing_record_{record_id}" in st.session_state:
    #             st.session_state[f"edit_missing_record_{record_id}"] = False
    #         if f"edit_missing_data_{record_id}" in st.session_state:
    #             del st.session_state[f"edit_missing_data_{record_id}"]
    #         if "current_editing_record_id" in st.session_state:
    #             del st.session_state["current_editing_record_id"]
    #         if "current_editing_from" in st.session_state:
    #             del st.session_state["current_editing_from"]
    #         st.rerun()
    
    # st.markdown("---")
    
    # Get record data from session state or database
    if f"edit_missing_data_{record_id}" in st.session_state:
        record = st.session_state[f"edit_missing_data_{record_id}"]
    else:
        # Fetch from database
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, criteria, energy_method, direction, paragraph, user, status, 
                   scale, climate, location, building_use, approach, sample_size
            FROM energy_data 
            WHERE id = ?
        ''', (record_id,))
        record = cursor.fetchone()
        
        if not record:
            st.error(f"Record {record_id} not found")
            return
    
    # Convert record tuple to dict
    _, criteria, energy_method, direction, paragraph, user, status, scale, climate, location, building_use, approach, sample_size = record
    
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
    
    # Use the unified edit form with the correct dropdowns
    # Define callback to clear edit mode
    def clear_edit_mode():
        if f"edit_missing_record_{record_id}" in st.session_state:
            st.session_state[f"edit_missing_record_{record_id}"] = False
        if f"edit_missing_data_{record_id}" in st.session_state:
            del st.session_state[f"edit_missing_data_{record_id}"]
        if "current_editing_record_id" in st.session_state:
            del st.session_state["current_editing_record_id"]
        if "current_editing_from" in st.session_state:
            del st.session_state["current_editing_from"]
    
    # Use from_missing_data=True to maintain proper context
    saved = display_unified_edit_form(record_id, record_data, is_pending=False, 
                                     clear_edit_callback=clear_edit_mode, from_missing_data=True)
    
    if saved:
        # Clear edit mode on successful save
        clear_edit_mode()
        time.sleep(1)
        st.rerun()

def fix_auto_increment():
    global conn
    cursor = conn.cursor()
    
    # Check if id column exists and has AUTOINCREMENT
    cursor.execute("PRAGMA table_info(energy_data)")
    columns = cursor.fetchall()
    
    id_col = None
    for col in columns:
        if col[1] == 'id':
            id_col = col
            break
    
    if id_col:
        # Check if it's INTEGER PRIMARY KEY (SQLite auto-increments these)
        if 'INTEGER' in str(id_col[2]).upper() and id_col[5] == 1:
            st.success("id column is already INTEGER PRIMARY KEY (auto-increments in SQLite)")
            return True
        else:
            # Need to recreate the table
            st.warning("id column exists but not configured for auto-increment")
    
    # If no id column or not auto-increment, add one
    # First, check if we have data
    cursor.execute("SELECT COUNT(*) FROM energy_data")
    count = cursor.fetchone()[0]
    
    if count > 0:
        # We have data, need to preserve it
        cursor.execute("ALTER TABLE energy_data RENAME TO energy_data_old")
        
        # Create new table with auto-increment id
        cursor.execute('''
            CREATE TABLE energy_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT,
                criteria TEXT,
                energy_method TEXT,
                direction TEXT,
                paragraph TEXT,
                status TEXT,
                user TEXT,
                scale TEXT,
                climate TEXT,
                location TEXT,
                building_use TEXT,
                climate_multi TEXT,
                approach TEXT,
                sample_size TEXT
            )
        ''')
        
        # Copy all data except id (let SQLite assign new ones)
        cursor.execute('''
            INSERT INTO energy_data (
                group_id, criteria, energy_method, direction, paragraph,
                status, user, scale, climate, location, building_use,
                climate_multi, approach, sample_size
            )
            SELECT 
                group_id, criteria, energy_method, direction, paragraph,
                status, user, scale, climate, location, building_use,
                climate_multi, approach, sample_size
            FROM energy_data_old
        ''')
        
        cursor.execute("DROP TABLE energy_data_old")
        conn.commit()
        st.success(f"Table restructured! {count} records migrated with new auto-increment IDs.")
    else:
        # No data, just recreate the table
        cursor.execute("DROP TABLE energy_data")
        cursor.execute('''
            CREATE TABLE energy_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT,
                criteria TEXT,
                energy_method TEXT,
                direction TEXT,
                paragraph TEXT,
                status TEXT DEFAULT 'pending',
                user TEXT,
                scale TEXT,
                climate TEXT,
                location TEXT,
                building_use TEXT,
                climate_multi TEXT,
                approach TEXT,
                sample_size TEXT
            )
        ''')
        conn.commit()
        st.success("Table created with auto-increment ID column.")
    
    return True

#fix_auto_increment()

def display_simple_edit_form(record_id, record_data, from_missing_data=False):
    """Simplified edit form that avoids key conflicts"""
    global conn
    import time  # ADD THIS IMPORT HERE
    import random  # ADD THIS TOO FOR CONSISTENCY
    
    # Use a unique session key for this edit form
    if f"edit_form_session_{record_id}" not in st.session_state:
        import time
        import random
        st.session_state[f"edit_form_session_{record_id}"] = f"{int(time.time())}_{random.randint(1000, 9999)}"
    
    session_key = st.session_state[f"edit_form_session_{record_id}"]
    
    # Edit form layout
    col1, col2 = st.columns(2)
    
    with col1:
        # Determinant
        new_criteria = st.text_input("Determinant", 
                                    value=record_data['criteria'], 
                                    key=f"simple_criteria_{record_id}_{session_key}")
        
        # Energy Output
        new_energy_method = st.text_input("Energy Output", 
                                        value=record_data['energy_method'], 
                                        key=f"simple_energy_{record_id}_{session_key}")
        
        # Direction
        new_direction = st.radio("Direction", ["Increase", "Decrease"], 
                                index=0 if record_data['direction'] == "Increase" else 1,
                                key=f"simple_direction_{record_id}_{session_key}", horizontal=True)
        
        # Scale (simplified - just text input)
        new_scale = st.text_input("Scale", 
                                value=record_data['scale'] if record_data['scale'] else "", 
                                key=f"simple_scale_{record_id}_{session_key}")
        
        # Location
        new_location = st.text_input("Location", 
                                    value=record_data['location'] if record_data['location'] else "", 
                                    key=f"simple_location_{record_id}_{session_key}")
        
        # Building Use
        new_building_use = st.text_input("Building Use", 
                                        value=record_data['building_use'] if record_data['building_use'] else "", 
                                        key=f"simple_building_use_{record_id}_{session_key}")
    
    with col2:
        # Climate (simplified - just text input)
        new_climate = st.text_input("Climate Code", 
                                  value=record_data['climate'] if record_data['climate'] else "", 
                                  key=f"simple_climate_{record_id}_{session_key}")
        
        # Approach
        approach_options = ["Select approach", "Top-down", "Bottom-up", "Hybrid (combined top-down and bottom-up)"]
        current_approach = record_data['approach'] if record_data['approach'] else "Select approach"
        current_approach_index = approach_options.index(current_approach) if current_approach in approach_options else 0
        
        selected_approach = st.selectbox("Approach", 
                                       options=approach_options,
                                       index=current_approach_index,
                                       key=f"simple_approach_{record_id}_{session_key}")
        
        # Sample Size
        new_sample_size = st.text_input("Sample Size", 
                                       value=record_data['sample_size'] if record_data['sample_size'] else "", 
                                       key=f"simple_sample_size_{record_id}_{session_key}")
        
        # Status
        status_options = ["approved", "rejected", "pending"]
        current_status = record_data['status'] if record_data['status'] in status_options else "approved"
        new_status = st.selectbox("Status", 
                                options=status_options,
                                index=status_options.index(current_status),
                                key=f"simple_status_{record_id}_{session_key}")
    
    # Paragraph content
    st.write("**Study Content:**")
    new_paragraph = st.text_area("Content", 
                                value=record_data['paragraph'], 
                                height=150, 
                                key=f"simple_paragraph_{record_id}_{session_key}")
    
    # Action buttons
    col_save, col_cancel = st.columns(2)
    
    with col_save:
        if st.button("💾 Save Changes", key=f"simple_save_{record_id}_{session_key}", type="primary", use_container_width=True):
            # Save to database
            cursor = conn.cursor()
            cursor.execute('''
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
                new_scale,
                new_climate,
                new_location,
                new_building_use,
                selected_approach if selected_approach != "Select approach" else None,
                new_sample_size,
                new_status,
                record_id
            ))
            
            conn.commit()
            
            # Clear session state
            if f"edit_form_session_{record_id}" in st.session_state:
                del st.session_state[f"edit_form_session_{record_id}"]
            if f"edit_missing_record_{record_id}" in st.session_state:
                st.session_state[f"edit_missing_record_{record_id}"] = False
            if f"edit_missing_data_{record_id}" in st.session_state:
                del st.session_state[f"edit_missing_data_{record_id}"]
            if "current_editing_record_id" in st.session_state:
                del st.session_state["current_editing_record_id"]
            if "current_editing_from" in st.session_state:
                del st.session_state["current_editing_from"]
            
            st.success(f"✅ Record {record_id} updated successfully!")
            time.sleep(1)
            st.rerun()
    
    with col_cancel:
        if st.button("❌ Cancel", key=f"simple_cancel_{record_id}_{session_key}", use_container_width=True):
            # Clear session state
            if f"edit_form_session_{record_id}" in st.session_state:
                del st.session_state[f"edit_form_session_{record_id}"]
            if f"edit_missing_record_{record_id}" in st.session_state:
                st.session_state[f"edit_missing_record_{record_id}"] = False
            if f"edit_missing_data_{record_id}" in st.session_state:
                del st.session_state[f"edit_missing_data_{record_id}"]
            if "current_editing_record_id" in st.session_state:
                del st.session_state["current_editing_record_id"]
            if "current_editing_from" in st.session_state:
                del st.session_state["current_editing_from"]
            
            st.rerun()

def display_missing_record(item, category):
    """Display a record with missing data and edit options"""
    record = item['record']
    record_id, criteria, energy_method, direction, paragraph, user, status, scale, climate, location, building_use, approach, sample_size = record
    
    with st.expander(f"Record {record_id}: {criteria} → {energy_method} ({direction})", expanded=False):
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.write(f"**Missing:** {', '.join(item['missing_fields'])}")
            st.write(f"**Scale:** {scale if scale else '❌ Missing'}")
            st.write(f"**Climate:** {climate if climate else '❌ Missing'}")
            st.write(f"**Location:** {location if location else '❌ Missing'}")
            st.write(f"**Building Use:** {building_use if building_use else '❌ Missing'}")
            st.write(f"**Approach:** {approach if approach else '❌ Missing'}")
            st.write(f"**Sample Size:** {sample_size if sample_size else '❌ Missing'}")
            st.write(f"**Status:** {status}")
            st.write(f"**Submitted by:** {user}")
        
        with col2:
            # Edit button - Use modal approach
            unique_key = f"edit_missing_{record_id}_{category}_{hash(str(record))}"
            if st.button("✏️ Edit", key=unique_key, use_container_width=True):
                # Store the record data and set edit mode
                st.session_state[f"edit_missing_data_{record_id}"] = record
                # Store a flag to indicate which record is being edited
                st.session_state["current_editing_record_id"] = record_id
                st.session_state["current_editing_from"] = "missing_data"
                st.rerun()
            
            # Mark as pending review button
            pending_key = f"pending_missing_{record_id}_{category}_{hash(str(record))}"
            if status != "pending":
                if st.button("⏳ Mark for Review", key=pending_key, use_container_width=True):
                    cursor_edit = conn.cursor()
                    cursor_edit.execute("UPDATE energy_data SET status = 'pending' WHERE id = ?", (record_id,))
                    conn.commit()
                    st.success(f"Record {record_id} marked for review")
                    time.sleep(1)
                    st.rerun()


def review_missing_data():
    """Review and edit records with missing data - LOADS NOTHING UNTIL SEARCH"""
    global conn
    st.subheader(" Missing Data Review")
    
    # Initialize session state
    if "missing_data_search" not in st.session_state:
        st.session_state.missing_data_search = False
    if "missing_data_results" not in st.session_state:
        st.session_state.missing_data_results = None
    
    # Simple search button
    col1, col2 = st.columns([3, 3])
    with col1:
        if st.button("🔍 Find Records with Missing Data", type="primary", use_container_width=True):
            st.session_state.missing_data_search = True
            st.rerun()
    with col2:
        st.write("Click to find records with missing data.")
    
    # ONLY load data when search is clicked
    if st.session_state.get("missing_data_search", False):
        with st.spinner("Analyzing database..."):
            cursor = conn.cursor()
            
            # Single query with LIMIT to prevent overload
            cursor.execute('''
                SELECT id, criteria, energy_method, direction, paragraph, user, status, 
                       scale, climate, location, building_use, approach, sample_size
                FROM energy_data 
                WHERE status NOT IN ("pending", "rejected")
                  AND paragraph IS NOT NULL 
                  AND paragraph != '' 
                  AND paragraph != '0' 
                  AND paragraph != '0.0'
                  AND paragraph != 'None'
                  AND LENGTH(TRIM(paragraph)) > 0
                  AND (
                      scale IN ("Awaiting data", "Not Specified", "", NULL) OR
                      scale IS NULL OR
                      climate IN ("Awaiting data", "Not Specified", "", NULL) OR
                      climate IS NULL OR
                      location IN ("", NULL)
                  )
                ORDER BY id DESC
                LIMIT 200
            ''')
            
            records = cursor.fetchall()
            st.session_state.missing_data_results = records
            
            st.write(f"**Found {len(records)} records with missing data**")
            
            if not records:
                st.success("✅ No records with missing data found!")
                if st.button("✕ Clear Results"):
                    st.session_state.missing_data_search = False
                    st.session_state.missing_data_results = None
                    st.rerun()
                return
            
            # Display results with pagination
            PER_PAGE = 10
            total_pages = (len(records) + PER_PAGE - 1) // PER_PAGE
            
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
            end_idx = min(start_idx + PER_PAGE, len(records))
            page_records = records[start_idx:end_idx]
            
            for record in page_records:
                record_id, criteria, energy_method, direction, paragraph, user, status, scale, climate, location, building_use, approach, sample_size = record
                
                missing_fields = []
                if not scale or scale in ["Awaiting data", "Not Specified", ""]:
                    missing_fields.append("Scale")
                if not climate or climate in ["Awaiting data", "Not Specified", ""]:
                    missing_fields.append("Climate")
                if not location:
                    missing_fields.append("Location")
                
                # SINGLE COLUMN LAYOUT - Metadata then Paragraph then Actions
                with st.expander(
                    f"📄 Record {record_id}: {criteria} → {energy_method} ({direction}) | Missing: {', '.join(missing_fields)}", 
                    expanded=False
                ):
                    # METADATA SECTION - Two columns for compact display
                    col_meta1, col_meta2 = st.columns(2)
                    
                    with col_meta1:
                        st.markdown(f"**ID:** `{record_id}`")
                        st.markdown(f"**Determinant:** {criteria}")
                        st.markdown(f"**Energy Output:** {energy_method}")
                        st.markdown(f"**Direction:** {direction}")
                        # st.markdown(f"**User:** {user}")
                        # st.markdown(f"**Status:** {status}")
                    
                    with col_meta2:
                        st.markdown("**❌ Missing Fields:**")
                        for field in missing_fields:
                            st.markdown(f"- 🔴 {field}")
                        
                        # st.markdown("**✅ Existing Data:**")
                        # if scale and scale not in ["Awaiting data", "Not Specified", ""]:
                        #     st.markdown(f"- 📏 Scale: {scale}")
                        # if climate and climate not in ["Awaiting data", "Not Specified", ""]:
                        #     st.markdown(f"- 🌍 Climate: {climate}")
                        # if location:
                        #     st.markdown(f"- 📍 Location: {location}")
                        # if building_use:
                        #     st.markdown(f"- 🏢 Building Use: {building_use}")
                        # if approach:
                        #     st.markdown(f"- 🔬 Approach: {approach}")
                        # if sample_size:
                        #     st.markdown(f"- 📊 Sample Size: {sample_size}")
                        # if not any([scale not in ["Awaiting data", "Not Specified", ""] and scale,
                        #           climate not in ["Awaiting data", "Not Specified", ""] and climate,
                        #           location, building_use, approach, sample_size]):
                        #     st.markdown("*No existing data*")
                    
                    st.markdown("---")
                    
                    # PARAGRAPH SECTION - Full width
                    st.markdown("**Study Content:**")
                    
                    # Fix: Preserve line breaks by converting \n to <br> tags
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
                    
                    # ACTION BUTTONS - Bottom right
                    col_action1, col_action2, col_action3 = st.columns([3, 1, 1])
                    with col_action2:
                        # Edit button
                        if st.button("Edit Record", key=f"edit_missing_{record_id}", use_container_width=True):
                            st.session_state[f"edit_missing_record_{record_id}"] = True
                            st.session_state[f"edit_missing_data_{record_id}"] = record
                            st.session_state["current_editing_record_id"] = record_id
                            st.session_state["current_editing_from"] = "missing_data"
                            st.rerun()
                    
                    with col_action3:
                        # Mark as pending button
                        if status != "pending":
                            if st.button("Mark for Review", key=f"pending_missing_{record_id}", use_container_width=True):
                                cursor_edit = conn.cursor()
                                cursor_edit.execute("UPDATE energy_data SET status = 'pending' WHERE id = ?", (record_id,))
                                conn.commit()
                                st.success(f"Record {record_id} marked for review")
                                time.sleep(1)
                                st.rerun()
                    
                    # EDIT FORM (if in edit mode) - Full width
                    if st.session_state.get(f"edit_missing_record_{record_id}", False):
                        st.markdown("---")
                        st.markdown(f"###Editing Record {record_id}")
                        
                        # Get record data
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
            
            # Clear results button
            if st.button("✕ Clear Results & Start Over"):
                st.session_state.missing_data_search = False
                st.session_state.missing_data_results = None
                st.rerun()

def show_complete_statistics(all_records, missing_scale, missing_climate, missing_location, 
                           missing_building_use, missing_approach, missing_sample_size, missing_multiple):
    """Display comprehensive statistics"""
    total_records = len(all_records)
    
    # Calculate percentages
    def calc_percent(count):
        return round((count / total_records) * 100, 1) if total_records > 0 else 0
    
    st.subheader("📊 Complete Database Statistics")
    
    # Metrics in columns
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Records", total_records)
        st.metric("Missing Scale", f"{len(missing_scale)} ({calc_percent(len(missing_scale))}%)")
        st.metric("Missing Climate", f"{len(missing_climate)} ({calc_percent(len(missing_climate))}%)")
    with col2:
        st.metric("Missing Location", f"{len(missing_location)} ({calc_percent(len(missing_location))}%)")
        st.metric("Missing Building Use", f"{len(missing_building_use)} ({calc_percent(len(missing_building_use))}%)")
        st.metric("Missing Approach", f"{len(missing_approach)} ({calc_percent(len(missing_approach))}%)")
    with col3:
        st.metric("Missing Sample Size", f"{len(missing_sample_size)} ({calc_percent(len(missing_sample_size))}%)")
        st.metric("Multiple Missing", f"{len(missing_multiple)} ({calc_percent(len(missing_multiple))}%)")
        st.metric("Complete Records", f"{total_records - len(missing_scale) - len(missing_climate) - len(missing_location) - len(missing_building_use) - len(missing_approach) - len(missing_sample_size)}")
    
    # Progress bars
    st.subheader("Data Completion Progress")
    
    completion_data = {
        "Scale": 100 - calc_percent(len(missing_scale)),
        "Climate": 100 - calc_percent(len(missing_climate)),
        "Location": 100 - calc_percent(len(missing_location)),
        "Building Use": 100 - calc_percent(len(missing_building_use)),
        "Approach": 100 - calc_percent(len(missing_approach)),
        "Sample Size": 100 - calc_percent(len(missing_sample_size)),
    }
    
    for field, percent in completion_data.items():
        st.progress(percent/100, text=f"{field}: {percent}% complete")

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
    """Display study content in an adjustable text area with clickable URLs"""
    # Convert URLs to clickable HTML links
    paragraph_with_links = convert_urls_to_links(paragraph)
    
    # Use markdown with HTML to create a scrollable, resizable container with clickable links
    st.markdown(
        f'''
        <div style="
            border: 1px solid #e0e0e0;
            padding: 15px;
            border-radius: 8px;
            background-color: #f8f9fa;
            max-height: 300px;
            overflow-y: auto;
            font-family: Arial, sans-serif;
            line-height: 1.5;
            font-size: 14px;
            resize: vertical;
            min-height: 100px;
        ">
            {paragraph_with_links}
        </div>
        ''',
        unsafe_allow_html=True
    )
    
def find_study_matches_in_paragraph(cursor, clean_study, original_study):
    """
    Find matches using exact substring matching - ONLY against paragraph field
    Returns ONLY exact matches
    """
    matches = []
    
    # Strategy: Exact substring match in paragraph - get ALL matches
    exact_matches = find_all_exact_substring_matches_in_paragraph(cursor, clean_study, original_study)
    matches.extend(exact_matches)
    
    # NO other strategies - exact matches only
    
    return matches

def find_study_matches_by_title(cursor, clean_study, original_study):
    """Find matches using multiple title-based strategies"""
    matches = []
    
    # Strategy 1: Exact substring match
    exact_matches = find_exact_substring_matches(cursor, clean_study, original_study)
    matches.extend(exact_matches)
    
    if not matches:
        # Strategy 2: Significant portion matching (80% of title)
        significant_matches = find_all_significant_portion_matches_in_paragraph(cursor, clean_study, original_study)
        matches.extend(significant_matches)
    
    if not matches:
        # Strategy 3: Keyword matching with significant words
        keyword_matches = find_keyword_based_matches(cursor, clean_study, original_study)
        matches.extend(keyword_matches)
    
    return matches

def find_all_exact_substring_matches_in_paragraph(cursor, clean_study, original_study):
    """Find ALL exact substring matches - ONLY in paragraph field, NO percentage threshold"""
    matches = []
    
    # Try different variations of the study title
    search_terms = [
        clean_study,
        original_study,  # Try original first
    ]
    
    # Also try a shorter version - first 40 chars (enough to be unique)
    if len(original_study) > 40:
        search_terms.append(original_study[:40])
    
    # Remove duplicates
    search_terms = list(dict.fromkeys([term for term in search_terms if term and len(term) > 15]))
    # ^ Lowered threshold from 10 to 15? Actually, let's just remove the length restriction entirely
    # for the primary search terms
    
    for term in search_terms:
        if not term or len(term) < 10:  # Only filter extremely short terms
            continue
            
        try:
            # Get ALL matching records
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
                
                # ONLY exact substring matches
                if term_lower in paragraph_lower:
                    matches.append({
                        'record_id': record_id,
                        'paragraph': paragraph,
                        'criteria': criteria,
                        'energy_method': energy_method,
                        'direction': direction,
                        'scale': scale,
                        'climate': climate,
                        'location': location,
                        'confidence': 'exact_match',
                        'match_position': paragraph_lower.find(term_lower),
                        'match_percentage': 100,
                        'matching_text': term
                    })
        except Exception as e:
            continue
    
    # Remove duplicate record IDs
    unique_matches = []
    seen_ids = set()
    for match in matches:
        if match['record_id'] not in seen_ids:
            unique_matches.append(match)
            seen_ids.add(match['record_id'])
    
    return unique_matches

def debug_study_matching(study_name, paragraph):
    """Debug why a study isn't matching"""
    st.write("--- DEBUG ---")
    st.write(f"**Original study:** {study_name}")
    
    clean = preprocess_study_name(study_name)
    st.write(f"**Cleaned study:** {clean}")
    
    st.write(f"**Paragraph excerpt:** {paragraph[:100]}...")
    
    # Check if cleaned version is in paragraph
    if clean.lower() in paragraph.lower():
        st.success(f"✓ Cleaned version found in paragraph")
    else:
        st.error(f"✗ Cleaned version NOT found in paragraph")
        
        # Try to find what's different
        para_lower = paragraph.lower()
        clean_lower = clean.lower()
        
        # Check first 20 chars
        if clean_lower[:20] in para_lower:
            st.info(f"First 20 chars match: '{clean[:20]}'")
        else:
            st.warning(f"First 20 chars don't match: '{clean[:20]}'")
            
        # Check last 20 chars
        if clean_lower[-20:] in para_lower:
            st.info(f"Last 20 chars match: '{clean[-20:]}'")
        else:
            st.warning(f"Last 20 chars don't match: '{clean[-20:]}'")

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
    FIXED: Proper session state management with session-specific keys
    """
    
    # Get the current session ID
    session_id = st.session_state.get("current_import_session", f"import_{int(time.time())}")
    
    # Initialize match confirmations dictionary in session state if not exists
    confirmations_key = f"match_confirmations_{session_id}"
    if confirmations_key not in st.session_state:
        st.session_state[confirmations_key] = {}
    
    # Initialize select all state
    select_all_key = f"select_all_active_{session_id}"
    if select_all_key not in st.session_state:
        st.session_state[select_all_key] = False
    
    # Initialize page state
    page_key = f"match_page_{session_id}"
    if page_key not in st.session_state:
        st.session_state[page_key] = 0
    
    # Add a "Start Over" button to clear session state
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("🔄 Start Over", key=f"start_over_{session_id}"):
            # Clear all session state for this import
            keys_to_delete = [k for k in st.session_state.keys() if session_id in k]
            for key in keys_to_delete:
                del st.session_state[key]
            if "current_import_session" in st.session_state:
                del st.session_state["current_import_session"]
            st.rerun()
    
    with col2:
        st.info(f"Session: {session_id[-6:]}")
    
    st.markdown("---")
    
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
    
    filter_key = f"quality_filter_{session_id}"
    selected_qualities = st.multiselect(
        "Select confidence levels to show:",
        options=quality_options,
        format_func=lambda x: quality_descriptions.get(x, x),
        default=quality_options,
        key=filter_key
    )
    
    # Filter matches by quality
    filtered_matches = [m for m in matched_records if m['confidence'] in selected_qualities]
    
    # Quick select all checkbox at the top
    select_all = st.checkbox(
        "Select All Filtered Matches", 
        key=f"select_all_{session_id}",
        value=st.session_state[select_all_key]
    )
    
    # Update select all state and all confirmations if changed
    if select_all != st.session_state[select_all_key]:
        st.session_state[select_all_key] = select_all
        # Update all confirmation states
        confirmations = st.session_state[confirmations_key]
        for i, match in enumerate(filtered_matches):
            match_id = f"match_{i}_{match['db_record_id']}_{session_id}"
            confirmations[match_id] = select_all
        st.session_state[confirmations_key] = confirmations
        st.rerun()
    
    # IMPORT BUTTON - ALWAYS VISIBLE AT TOP
    st.markdown("---")
    col1, col2 = st.columns([3, 1])
    with col1:
        import_top_key = f"import_main_{session_id}"
        if st.button("🚀 IMPORT SELECTED MATCHES", type="primary", use_container_width=True, key=import_top_key):
            # Collect all confirmed matches
            confirmed_matches = []
            confirmations = st.session_state[confirmations_key]
            
            for i, match in enumerate(filtered_matches):
                match_id = f"match_{i}_{match['db_record_id']}_{session_id}"
                if confirmations.get(match_id, False):
                    confirmed_matches.append(match)
            
            if confirmed_matches:
                current_excel_df = st.session_state.get(f"excel_df_{session_id}")
                if current_excel_df is not None:
                    with st.spinner(f"Importing {len(confirmed_matches)} matches..."):
                        updated_count = process_confirmed_matches(confirmed_matches, current_excel_df)
                        if updated_count > 0:
                            st.success(f"✅ Successfully updated {updated_count} records!")
                            # Don't clear session state - keep the matches for further imports
                            # Just show success message
                            time.sleep(2)
                            st.rerun()
                else:
                    st.error("❌ Excel data not available. Please re-upload the file.")
            else:
                st.warning("⚠️ No matches selected. Please check the boxes next to the matches you want to import.")
    with col2:
        st.info(f"📊 {len(filtered_matches)} matches shown")
    
    st.markdown("---")
    
    # PAGINATION
    MATCHES_PER_PAGE = 10
    total_pages = (len(filtered_matches) + MATCHES_PER_PAGE - 1) // MATCHES_PER_PAGE
    
    # Page navigation
    if total_pages > 1:
        col_prev, col_page, col_next = st.columns([1, 2, 1])
        with col_prev:
            prev_key = f"prev_{session_id}"
            if st.button("◀ Previous", disabled=st.session_state[page_key] == 0, key=prev_key):
                st.session_state[page_key] = max(0, st.session_state[page_key] - 1)
                st.rerun()
        with col_page:
            st.write(f"**Page {st.session_state[page_key] + 1} of {total_pages}**")
        with col_next:
            next_key = f"next_{session_id}"
            if st.button("Next ▶", disabled=st.session_state[page_key] >= total_pages - 1, key=next_key):
                st.session_state[page_key] = min(total_pages - 1, st.session_state[page_key] + 1)
                st.rerun()
    
    # Calculate current page slice
    start_idx = st.session_state[page_key] * MATCHES_PER_PAGE
    end_idx = min(start_idx + MATCHES_PER_PAGE, len(filtered_matches))
    current_page_matches = filtered_matches[start_idx:end_idx]
    
    # Display current page matches
    for i, match in enumerate(current_page_matches):
        global_index = start_idx + i
        match_id = f"match_{global_index}_{match['db_record_id']}_{session_id}"
        
        # Get confirmations dictionary
        confirmations = st.session_state[confirmations_key]
        
        # Initialize confirmation state if not exists
        if match_id not in confirmations:
            confirmations[match_id] = match['confidence'] == 'exact_match'
            st.session_state[confirmations_key] = confirmations
        
        with st.expander(
            f"{'🟢' if match['confidence'] == 'exact_match' else '🟡' if match['confidence'] == 'strong_match' else '🟠'} "
            f"Match {global_index + 1} | Record ID: {match['db_record_id']} | "
            f"{match['excel_study'][:50]}...", 
            expanded=True
        ):
            col1, col2 = st.columns([4, 1])
            
            with col1:
                # Study title
                st.markdown("**📥 Imported Study Title:**")
                st.info(match['excel_study'])
                
                # Database content
                st.markdown("**🗄️ Database Record Content:**")
                paragraph = match['matching_paragraph']
                
                # Try to highlight the match
                study_normalized = match.get('excel_study_normalized', match['excel_study'])
                study_lower = study_normalized.lower()
                paragraph_lower = paragraph.lower()
                
                if study_lower in paragraph_lower:
                    start = paragraph_lower.index(study_lower)
                    end = start + len(study_normalized)
                    highlighted = (
                        paragraph[:start] + 
                        "**" + paragraph[start:end] + "**" + 
                        paragraph[end:]
                    )
                    st.markdown(highlighted)
                else:
                    st.text_area("", value=paragraph, height=150, key=f"para_{match_id}", disabled=True)
                
                # Match metadata
                col_meta1, col_meta2 = st.columns(2)
                with col_meta1:
                    st.write(f"**Determinant:** {match['criteria']}")
                    st.write(f"**Energy Output:** {match['energy_method']}")
                with col_meta2:
                    st.write(f"**Direction:** {match['direction']}")
                    st.write(f"**Confidence:** {match['confidence']}")
            
            with col2:
                # Checkbox for confirmation
                confirmed = st.checkbox(
                    "✅ Import this match",
                    value=confirmations.get(match_id, False),
                    key=f"chk_{match_id}"
                )
                # Update session state
                if confirmed != confirmations.get(match_id, False):
                    confirmations[match_id] = confirmed
                    st.session_state[confirmations_key] = confirmations
                
                # Show confidence badge
                confidence_colors = {
                    'exact_match': '🟢',
                    'strong_match': '🟡',
                    'good_match': '🟠'
                }
                st.markdown(f"**{confidence_colors.get(match['confidence'], '⚪')} {match['confidence']}**")
        
        st.markdown("---")
    
    # Bottom import button for long lists
    if len(filtered_matches) > MATCHES_PER_PAGE:
        st.markdown("---")
        import_bottom_key = f"import_bottom_{session_id}"
        if st.button("🚀 IMPORT SELECTED MATCHES", type="primary", use_container_width=True, key=import_bottom_key):
            # Collect all confirmed matches
            confirmed_matches = []
            confirmations = st.session_state[confirmations_key]
            
            for i, match in enumerate(filtered_matches):
                match_id = f"match_{i}_{match['db_record_id']}_{session_id}"
                if confirmations.get(match_id, False):
                    confirmed_matches.append(match)
            
            if confirmed_matches:
                current_excel_df = st.session_state.get(f"excel_df_{session_id}")
                if current_excel_df is not None:
                    with st.spinner(f"Importing {len(confirmed_matches)} matches..."):
                        updated_count = process_confirmed_matches(confirmed_matches, current_excel_df)
                        if updated_count > 0:
                            st.success(f"✅ Successfully updated {updated_count} records!")
                            # Don't clear session state
                            time.sleep(2)
                            st.rerun()
                else:
                    st.error("❌ Excel data not available. Please re-upload the file.")
            else:
                st.warning("⚠️ No matches selected. Please check the boxes next to the matches you want to import.")
    
    # UNMATCHED STUDIES SECTION
    if unmatched_studies:
        st.markdown("---")
        st.subheader("❌ Unmatched Studies")
        st.warning(f"**{len(unmatched_studies)} studies couldn't be automatically matched**")
        
        with st.expander("📊 View Unmatched Studies", expanded=False):
            # Search filter
            search_unmatched_key = f"search_unmatched_{session_id}"
            search_unmatched = st.text_input("🔍 Search unmatched studies", placeholder="Enter keyword...", key=search_unmatched_key)
            
            # Filter studies
            filtered_unmatched = unmatched_studies
            if search_unmatched:
                filtered_unmatched = [s for s in filtered_unmatched if search_unmatched.lower() in s['study_name'].lower()]
            
            # Display unmatched studies
            for i, unmatched in enumerate(filtered_unmatched[:20]):
                st.write(f"**{i+1}.** {unmatched['study_name']}")
                search_db_key = f"search_db_{i}_{session_id}"
                if st.button(f"🔍 Search DB for this study", key=search_db_key):
                    similar_results = quick_database_search_unmatched(conn, unmatched['study_name'])
                    if similar_results:
                        st.success(f"Found {len(similar_results)} potential matches")
                        for sim in similar_results[:3]:
                            st.write(f"- ID {sim['id']}: {sim['paragraph'][:100]}...")
                    else:
                        st.error("No similar records found")
            
            if len(filtered_unmatched) > 20:
                st.write(f"... and {len(filtered_unmatched) - 20} more")
            
            # Export option
            export_key = f"export_unmatched_{session_id}"
            if st.button("📤 Export Unmatched Studies", key=export_key):
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
            
            # Extract climate code
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
                location if location else None,
                climate_code if climate_code else None,
                scale if scale else None,
                building_use if building_use else None,
                approach if approach else None,
                sample_size if sample_size else None,
                record_id
            ))
            
            updated_count += 1
            
        else:
            not_found_in_excel.append(excel_study)
    
    conn.commit()
    
    if not_found_in_excel:
        st.warning(f"⚠️ {len(not_found_in_excel)} studies not found in Excel file")
    
    return updated_count


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
    
    # Now extract just the climate code
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
    """Import climate, location, scale, building use, approach and sample size data - SIMPLIFIED"""
    global conn
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
            # Read the file
            df = pd.read_excel(uploaded_file, sheet_name=0)
            
            # Show preview
            st.write("**Preview of data to import:**")
            st.dataframe(df.head(10))
            
            # Show column names
            st.write(f"**Columns found in file:** {list(df.columns)}")
            
            # AUTOMATICALLY DETECT STUDY COLUMN
            study_column = None
            for col in df.columns:
                col_lower = str(col).lower()
                if any(keyword in col_lower for keyword in ['study', 'title', 'paper', 'reference', 'citation']):
                    study_column = col
                    break
            
            if study_column is None:
                # If no obvious study column, use first column
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
                        # Clear any existing import session
                        if "current_import_session" in st.session_state:
                            old_session = st.session_state.current_import_session
                            keys_to_delete = [k for k in st.session_state.keys() if old_session in k]
                            for key in keys_to_delete:
                                del st.session_state[key]
                        
                        # Create new session ID
                        session_id = f"import_{int(time.time())}"
                        st.session_state.current_import_session = session_id
                        st.session_state[f"excel_df_{session_id}"] = df
                        st.session_state[f"study_column_{session_id}"] = study_column
                        
                        # Perform matching
                        matched_records, unmatched_studies = perform_study_matching(df, study_column)
                        
                        # Store results
                        st.session_state[f"matched_records_{session_id}"] = matched_records
                        st.session_state[f"unmatched_studies_{session_id}"] = unmatched_studies
                        
                        st.success(f"✅ Found {len(matched_records)} matches and {len(unmatched_studies)} unmatched studies")
                        st.rerun()
            
            # DISPLAY RESULTS
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
    
# UNIFIED EDIT FORM FUNCTION
def display_unified_edit_form(record_id, record_data=None, is_pending=False, clear_edit_callback=None, from_missing_data=False, conn=None):
    """
    Unified edit form for all admin editing interfaces
    from_missing_data: Flag to indicate if we're editing from the Missing Data Review tab
    conn: Optional database connection (if not provided, creates a new one)
    """
    
    # Generate a unique session ID for this edit session to avoid key conflicts
    if f"edit_session_{record_id}" not in st.session_state:
        import time
        import random
        st.session_state[f"edit_session_{record_id}"] = f"{int(time.time())}_{random.randint(1000, 9999)}"
    
    session_id = st.session_state[f"edit_session_{record_id}"]
    
    if not record_data:
        # Fetch record from database if not provided - create local connection
        conn_local = sqlite3.connect(db_file)
        cursor = conn_local.cursor()
        cursor.execute('''  
            SELECT id, criteria, energy_method, direction, paragraph, user, status, 
                   scale, climate, location, building_use, approach, sample_size
            FROM energy_data 
            WHERE id = ?
        ''', (record_id,))
        
        record = cursor.fetchone()
        conn_local.close()
        
        if not record:
            st.error(f"Record {record_id} not found")
            return False
            
        record_data = {
            'criteria': record[1],
            'energy_method': record[2],
            'direction': record[3],
            'paragraph': record[4],
            'user': record[5],
            'status': record[6],
            'scale': record[7],
            'climate': record[8],
            'location': record[9],
            'building_use': record[10],
            'approach': record[11],
            'sample_size': record[12]
        }
    
    # Edit form layout - ALL KEYS NOW INCLUDE SESSION ID
    col1, col2 = st.columns(2)
    
    with col1:
        # Determinant (free text input for flexibility)
        new_criteria = st.text_input("Determinant", 
                                    value=record_data['criteria'], 
                                    key=f"unified_criteria_{record_id}_{session_id}")
        
        # Energy Output (free text input for flexibility)
        new_energy_method = st.text_input("Energy Output", 
                                        value=record_data['energy_method'], 
                                        key=f"unified_energy_method_{record_id}_{session_id}")
        
        # Direction
        new_direction = st.radio("Direction", ["Increase", "Decrease"], 
                                index=0 if record_data['direction'] == "Increase" else 1,
                                key=f"unified_direction_{record_id}_{session_id}", horizontal=True)
        
        # Scale (editable with dropdown)
        try:
            # Create a local connection for querying scale options
            conn_local = sqlite3.connect(db_file)
            scale_options_list = ["Select scale"] + query_dynamic_scale_options(conn_local) + ["Add new scale"]
            conn_local.close()
        except Exception as e:
            st.warning(f"Could not load scale options: {e}")
            scale_options_list = ["Select scale", "Awaiting data", "Add new scale"]
        
        # Find current scale in options
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
        
        # Location (editable)
        new_location = st.text_input("Location", 
                                    value=record_data['location'] if record_data['location'] else "", 
                                    key=f"unified_location_{record_id}_{session_id}")
        
        # Building Use (editable with dropdown)
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
        # Climate - Get ALL valid climate options using the same function as papers_tab
        try:
            # Create a local connection for querying climate options
            conn_local = sqlite3.connect(db_file)
            
            # Use the same function that works in papers_tab
            climate_options_raw = query_dominant_climate_options(conn_local)
            
            # Extract just the formatted strings for display
            climate_options_list = ["Select climate"] + [formatted for formatted, color in climate_options_raw]
            
            conn_local.close()
        except Exception as e:
            st.warning(f"Could not load climate options: {e}")
            climate_options_list = ["Select climate"]
        
        # Find current climate in options
        current_climate = record_data['climate'] if record_data['climate'] else "Select climate"
        current_climate_index = 0
        
        # If current climate is 'Var', create a proper formatted version
        if current_climate and current_climate.upper() == 'VAR':
            current_climate = 'Var - Varies / Multiple Climates'
        
        # Try to match the climate (handle both code only and formatted strings)
        for i, opt in enumerate(climate_options_list):
            if opt == "Select climate":
                continue
            opt_code = opt.split(" - ")[0] if " - " in opt else opt
            opt_code = ''.join([c for c in opt_code if c.isalnum()])
            
            # Handle current climate - could be code only or formatted
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
        
        # NO new_climate input - removed entirely
        # NO free text entry for climate
        
        # Approach (editable with specific options)
        approach_options = ["Select approach", "Top-down", "Bottom-up", "Hybrid (combined top-down and bottom-up)"]
        current_approach = record_data['approach'] if record_data['approach'] else "Select approach"
        current_approach_index = approach_options.index(current_approach) if current_approach in approach_options else 0
        
        selected_approach = st.selectbox("Approach", 
                                       options=approach_options,
                                       index=current_approach_index,
                                       key=f"unified_approach_{record_id}_{session_id}")
        
        # Sample Size (editable)
        new_sample_size = st.text_input("Sample Size", 
                                        value=record_data['sample_size'] if record_data['sample_size'] else "", 
                                        key=f"unified_sample_size_{record_id}_{session_id}")
        
        # Status (editable) - only for non-pending records
        if not is_pending:
            status_options = ["approved", "rejected", "pending"]
            current_status = record_data['status'] if record_data['status'] in status_options else "approved"
            new_status = st.selectbox("Status", 
                                    options=status_options,
                                    index=status_options.index(current_status),
                                    key=f"unified_status_{record_id}_{session_id}")
        else:
            new_status = "pending"  # Keep as pending for pending records
    
    # Paragraph content
    st.write("**Study Content:**")
    new_paragraph = st.text_area("Content", 
                                value=record_data['paragraph'], 
                                height=150, 
                                key=f"unified_paragraph_{record_id}_{session_id}")
    
    # Action buttons - also include session ID
    col_save, col_cancel = st.columns(2)
    
    saved = False
    
    with col_save:
        if st.button("💾 Save Changes", key=f"unified_save_{record_id}_{session_id}", type="primary", use_container_width=True):
            # Prepare final values
            final_scale = new_scale if selected_scale == "Add new scale" else (
                selected_scale if selected_scale != "Select scale" else record_data['scale'])
            
            # Climate - only from dropdown, no free text
            final_climate = None
            if selected_climate != "Select climate":
                if " - " in selected_climate:
                    final_climate = selected_climate.split(" - ")[0]
                    final_climate = ''.join([c for c in final_climate if c.isalnum()])
                else:
                    final_climate = selected_climate
            
            # Prepare building use value
            final_building_use = new_building_use if selected_building_use == "Add new building use" else (
                selected_building_use if selected_building_use != "Select building use" else record_data['building_use'])
            
            # Prepare approach value
            final_approach = selected_approach if selected_approach != "Select approach" else record_data['approach']
            
            # Save to database - create new connection
            conn_local = sqlite3.connect(db_file)
            cursor = conn_local.cursor()
            cursor.execute('''
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
                final_scale if final_scale != "Select scale" else None,
                final_climate,  # Now properly handles None
                new_location if new_location else None,
                final_building_use if final_building_use != "Select building use" else None,
                final_approach if final_approach != "Select approach" else None,
                new_sample_size if new_sample_size else None,
                new_status,
                record_id
            ))
            
            conn_local.commit()
            conn_local.close()
            saved = True
            st.success(f"✅ Record {record_id} updated successfully!")
    
    with col_cancel:
        if st.button("❌ Cancel", key=f"unified_cancel_{record_id}_{session_id}", use_container_width=True):
            # Clear edit mode - use callback if provided
            if clear_edit_callback:
                clear_edit_callback()  # This sets admin_edit_selected_id = None and preserves tab
            else:
                # Default behavior: clear session state flags
                if f"edit_missing_record_{record_id}" in st.session_state:
                    st.session_state[f"edit_missing_record_{record_id}"] = False
                if f"admin_pending_edit_{record_id}" in st.session_state:
                    st.session_state[f"admin_pending_edit_{record_id}"] = False
                if f"admin_full_edit_{record_id}" in st.session_state:
                    st.session_state[f"admin_full_edit_{record_id}"] = False
                if f"edit_data_{record_id}" in st.session_state:
                    del st.session_state[f"edit_data_{record_id}"]
            
            # Clear the session ID
            if f"edit_session_{record_id}" in st.session_state:
                del st.session_state[f"edit_session_{record_id}"]
            
            # CRITICAL: Preserve tab state
            st.session_state.current_tab = "tab3"
            
            # Force rerun
            st.rerun()
    
    # If we saved, clear edit flags and session ID
    if saved:
        # Clear the session ID
        if f"edit_session_{record_id}" in st.session_state:
            del st.session_state[f"edit_session_{record_id}"]
        
        # Clear the global edit flags if we're in missing data review
        if "admin_editing_in_missing_data" in st.session_state:
            del st.session_state["admin_editing_in_missing_data"]
        if "admin_current_edit_record_id" in st.session_state:
            del st.session_state["admin_current_edit_record_id"]
    
    return saved

def manage_scale_climate_data():
    """Edit Records - Search first, then select from results dropdown"""
    
    st.subheader("Edit Records - Full Record Management")
    
    # ============= SEARCH INTERFACE =============
    # st.markdown("### 🔍 Search for Records to Edit")
    st.markdown("Search all records by keyword.")
    
    # Initialize search state
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
    
    # Force the current tab to be Edit/Review
    st.session_state.current_tab = "tab3"
    
    # Search input - triggers on Enter (no rerun in callback)
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
    
    # Process search if triggered
    if st.session_state.admin_edit_trigger_search:
        search_query = st.session_state.admin_edit_search_input
        st.session_state.admin_edit_trigger_search = False
        st.session_state.admin_edit_search_query = search_query
        st.session_state.admin_edit_search_performed = True
        st.session_state.admin_edit_selected_id = None
        
        with st.spinner("Searching records..."):
            # Create a NEW connection for this thread
            conn_local = sqlite3.connect(db_file)
            cursor = conn_local.cursor()
            search_pattern = f'%{search_query}%'
            
            # Search across all relevant fields
            cursor.execute('''
                SELECT 
                    id, 
                    criteria, 
                    energy_method, 
                    direction, 
                    paragraph,
                    scale,
                    climate,
                    location,
                    building_use,
                    approach,
                    sample_size,
                    user,
                    status
                FROM energy_data 
                WHERE paragraph IS NOT NULL 
                  AND paragraph != '' 
                  AND paragraph != '0' 
                  AND paragraph != '0.0'
                  AND paragraph != 'None'
                  AND LENGTH(TRIM(paragraph)) > 0
                  AND (
                      CAST(id AS TEXT) LIKE ? OR
                      LOWER(criteria) LIKE LOWER(?) OR
                      LOWER(energy_method) LIKE LOWER(?) OR
                      LOWER(direction) LIKE LOWER(?) OR
                      LOWER(paragraph) LIKE LOWER(?) OR
                      LOWER(scale) LIKE LOWER(?) OR
                      LOWER(climate) LIKE LOWER(?) OR
                      LOWER(location) LIKE LOWER(?) OR
                      LOWER(building_use) LIKE LOWER(?) OR
                      LOWER(approach) LIKE LOWER(?) OR
                      LOWER(sample_size) LIKE LOWER(?) OR
                      LOWER(user) LIKE LOWER(?)
                  )
                ORDER BY id DESC
                LIMIT 200
            ''', (search_pattern, search_pattern, search_pattern, search_pattern, 
                  search_pattern, search_pattern, search_pattern, search_pattern,
                  search_pattern, search_pattern, search_pattern, search_pattern))
            
            results = cursor.fetchall()
            conn_local.close()
            
            st.session_state.admin_edit_search_results = results
    
    # Clear search button
    if st.session_state.admin_edit_search_performed:
        col_clear = st.columns([1])[0]
        with col_clear:
            if st.button("✕ Clear Search Results", key="admin_edit_clear_btn", use_container_width=True):
                # Clear all search-related state
                st.session_state.admin_edit_search_performed = False
                st.session_state.admin_edit_search_results = []
                st.session_state.admin_edit_search_query = ""
                st.session_state.admin_edit_selected_id = None
                st.session_state.current_tab = "tab3"
                st.rerun()
    
    st.markdown("---")
    
    # ============= RESULTS AND SELECTION =============
    if st.session_state.admin_edit_search_performed and not st.session_state.admin_edit_selected_id:
        results = st.session_state.admin_edit_search_results
        
        if not results:
            st.warning(f"No records found matching '{st.session_state.admin_edit_search_query}'")
            return
        
        st.success(f"Found {len(results)} records matching '{st.session_state.admin_edit_search_query}'")
        
        # Create dropdown of search results
        st.markdown("###  Select Record to Edit")
        
        # Format options for dropdown
        edit_options = {}
        for record in results:
            record_id = record[0]
            criteria = record[1] if record[1] else "N/A"
            energy_method = record[2] if record[2] else "N/A"
            direction = record[3] if record[3] else "N/A"
            location = record[7] if record[7] else ""
            climate = record[6] if record[6] else ""
            
            # Create a descriptive label
            location_str = f" | {location}" if location else ""
            climate_str = f" | {climate}" if climate else ""
            label = f"ID {record_id}: {criteria} → {energy_method} ({direction}){location_str}{climate_str}"
            
            # Truncate if too long
            if len(label) > 120:
                label = label[:117] + "..."
            
            edit_options[label] = record_id
        
        # Sort options by ID (descending)
        sorted_options = sorted(edit_options.items(), key=lambda x: x[1], reverse=True)
        
        # Dropdown for selection
        if sorted_options:
            selected_option = st.selectbox(
                "Choose a record to edit:",
                options=["-- Select a record --"] + [opt[0] for opt in sorted_options],
                key="admin_edit_record_selector"
            )
            
            # When a record is selected
            if selected_option != "-- Select a record --":
                selected_id = edit_options[selected_option]
                
                # Update selected ID if changed
                if st.session_state.admin_edit_selected_id != selected_id:
                    st.session_state.admin_edit_selected_id = selected_id
                    st.session_state.current_tab = "tab3"
                    st.rerun()
            
            # Show record count
            st.caption(f"Showing {len(results)} records. Select one to edit.")
    
    # ============= EDIT FORM FOR SELECTED RECORD =============
    if st.session_state.admin_edit_selected_id:
        record_id = st.session_state.admin_edit_selected_id
        
        st.markdown("---")
        st.markdown(f"###  Editing Record {record_id}")
        
        # Add a note that editing will hide the search results
        st.info("Editing mode active. The search results are hidden while editing. Cancel to return to results.")
        
        # Create a NEW connection for fetching the record
        conn_local = sqlite3.connect(db_file)
        cursor = conn_local.cursor()
        cursor.execute('''
            SELECT criteria, energy_method, direction, paragraph, user, status,
                   scale, climate, location, building_use, approach, sample_size
            FROM energy_data WHERE id = ?
        ''', (record_id,))
        edit_record = cursor.fetchone()
        conn_local.close()
        
        if edit_record:
            # Use the unified edit form
            record_data = {
                'criteria': edit_record[0],
                'energy_method': edit_record[1],
                'direction': edit_record[2],
                'paragraph': edit_record[3],
                'user': edit_record[4],
                'status': edit_record[5],
                'scale': edit_record[6],
                'climate': edit_record[7],
                'location': edit_record[8],
                'building_use': edit_record[9],
                'approach': edit_record[10],
                'sample_size': edit_record[11]
            }
            
            # Define callback to clear selection after save/cancel
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
                # Clear selection and stay on this tab
                st.session_state.admin_edit_selected_id = None
                st.session_state.current_tab = "tab3"
                st.rerun()
    
    # If no search performed yet, show hint
    elif not st.session_state.admin_edit_search_performed:
        st.info(" Enter a search term above and press Enter to find records to edit")

def review_pending_data():
    global conn
    st.subheader("Review Pending Data Submissions")
    
    # DEBUG: Add debug mode toggle
    #debug_mode = st.sidebar.checkbox("🔧 Debug Mode", value=False)
    debug_mode = False

    # Check if we have a pending action to execute
    if "pending_action" in st.session_state:
        record_id = st.session_state.pending_action.get("record_id")
        action = st.session_state.pending_action.get("action")
        
        if record_id and action:
            try:
                cursor = conn.cursor()
                if action == "approve":
                    cursor.execute("UPDATE energy_data SET status = 'approved' WHERE id = ?", (record_id,))
                    if debug_mode:
                        st.sidebar.success(f"✅ Approved record {record_id}")
                elif action == "reject":
                    cursor.execute("UPDATE energy_data SET status = 'rejected' WHERE id = ?", (record_id,))
                    if debug_mode:
                        st.sidebar.success(f"❌ Rejected record {record_id}")
                
                conn.commit()
                
                # Verify the update
                cursor.execute("SELECT status FROM energy_data WHERE id = ?", (record_id,))
                updated_status = cursor.fetchone()[0]
                if debug_mode:
                    st.sidebar.info(f"Verified: Record {record_id} status = {updated_status}")
                
                # Clear the pending action
                del st.session_state.pending_action
                
                # Show success message
                st.success(f"Record {record_id} {action}d successfully!")
                
                # Rerun to refresh
                time.sleep(1)
                st.rerun()
                
            except Exception as e:
                st.error(f"Error processing {action} for record {record_id}: {str(e)}")
                if debug_mode:
                    st.sidebar.error(f"Error details: {e}")
    
    # Function to handle button clicks
    def handle_button_click(record_id, action):
        """Store the action in session state for execution after rerun"""
        st.session_state.pending_action = {
            "record_id": record_id,
            "action": action
        }
        if debug_mode:
            st.sidebar.write(f"📝 Button clicked: {action} for record {record_id}")
    
    # Use the global connection directly
    cursor = conn.cursor()
    
    # Fetch only pending records
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
        return
    
    # Display a clear debug panel if enabled
    if debug_mode:
        with st.sidebar.expander("🔍 Debug Info", expanded=True):
            st.write("Session state keys:", list(st.session_state.keys()))
            if "pending_action" in st.session_state:
                st.write("Pending action:", st.session_state.pending_action)
    
    # Create a refresh button at the top
    if st.button("🔄 Refresh List", key="refresh_top_main", use_container_width=True):
        # Clear any edit modes
        for key in list(st.session_state.keys()):
            if key.startswith("admin_pending_edit_"):
                del st.session_state[key]
        st.rerun()
    
    st.markdown("---")
    
    # Display each record
    for index, record in enumerate(pending_records):
        record_id, criteria, energy_method, direction, paragraph, user, status = record
        
        # Create a container for each record
        with st.container():
            st.markdown(f"### 📄 Record #{record_id}")
            
            # Header with basic info
            col_info, col_actions = st.columns([3, 1])
            
            with col_info:
                st.write(f"**Submitted by:** {user}")
                st.write(f"**Determinant:** {criteria}")
                st.write(f"**Energy Output:** {energy_method}")
                st.write(f"**Direction:** {direction}")
            
            with col_actions:
                # Edit button with callback
                edit_mode = st.session_state.get(f"admin_pending_edit_{record_id}", False)
                
                if not edit_mode:
                    if st.button("✏️ Edit", key=f"edit_{record_id}_{index}", use_container_width=True):
                        st.session_state[f"admin_pending_edit_{record_id}"] = True
                        if debug_mode:
                            st.sidebar.write(f"📝 Entering edit mode for record {record_id}")
                        st.rerun()
                else:
                    if st.button("❌ Cancel Edit", key=f"cancel_edit_{record_id}_{index}", use_container_width=True):
                        st.session_state[f"admin_pending_edit_{record_id}"] = False
                        st.rerun()
            
            # Edit mode or view mode
            if st.session_state.get(f"admin_pending_edit_{record_id}"):
                # Edit Mode
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
                # View Mode - Display the content
                st.markdown("**Submitted text:**")
                st.text_area("Content", value=paragraph, height=150, 
                           key=f"content_{record_id}", disabled=True, label_visibility="collapsed")
                
                # Approval/Rejection buttons with callbacks
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
                
                # with col_status:
                #     status_badge_color = {
                #         'pending': '🟡 Pending',
                #         'approved': '🟢 Approved',
                #         'rejected': '🔴 Rejected'
                #     }
                #     badge = status_badge_color.get(status, '⚪ Unknown')
                #     st.markdown(f"**Status:** {badge}")
            
            st.markdown("---")
    
    # Statistics section
    st.markdown("---")
    
    # Show statistics
    cursor.execute("SELECT COUNT(*) FROM energy_data WHERE status = 'pending'")
    pending_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM energy_data WHERE status = 'approved'")
    approved_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM energy_data WHERE status = 'rejected'")
    rejected_count = cursor.fetchone()[0]
    
    with st.expander("📊 Status Statistics", expanded=False):
        st.write(f"**Pending:** {pending_count}")
        st.write(f"**Approved:** {approved_count}")
        st.write(f"**Rejected:** {rejected_count}")
    
    # Add a database health check
    if debug_mode and st.sidebar.button("🔍 Check Database Health"):
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            st.sidebar.write("Tables:", tables)
            
            cursor.execute("PRAGMA table_info(energy_data)")
            columns = cursor.fetchall()
            st.sidebar.write("Energy_data columns:", columns)
            
            # Check if status column exists
            status_column_exists = any(col[1] == 'status' for col in columns)
            st.sidebar.write(f"Status column exists: {status_column_exists}")
            
        except Exception as e:
            st.sidebar.error(f"Database error: {e}")

# Add this debug function
def debug_record_status(record_id):
    global conn
    cursor = conn.cursor()
    cursor.execute("SELECT id, status FROM energy_data WHERE id = ?", (record_id,))
    result = cursor.fetchone()
    if result:
        st.sidebar.write(f"Debug - Record {result[0]}: status = {result[1]}")
    else:
        st.sidebar.write(f"Debug - Record {record_id} not found")

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

# Add this new function to query all papers from the database
def query_all_papers(conn):
    """Query all unique papers/studies from the database with their metadata"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 
            id,
            paragraph as study_text,
            criteria,
            energy_method,
            direction,
            scale,
            climate,
            location,
            building_use,
            approach,
            sample_size,
            status,
            user
        FROM energy_data 
        WHERE paragraph IS NOT NULL 
          AND paragraph != '' 
          AND paragraph != '0' 
          AND paragraph != '0.0'
          AND paragraph != 'None'
          AND LENGTH(TRIM(paragraph)) > 0
          AND status NOT IN ("rejected")
        ORDER BY id DESC
    ''')
    
    papers = cursor.fetchall()
    return papers

def render_papers_tab():
    """Render the Studies tab with search functionality - LOADS NOTHING UNTIL SEARCH"""
    st.title("Research Studies Database")
    
    st.markdown("""Use the search box below to browse all studies in the SpatialBuild Energy database.""")
    
    st.markdown("---")
    
    # ============= CLEAN SESSION STATE =============
    if "papers_search_performed" not in st.session_state:
        st.session_state.papers_search_performed = False
    
    if "papers_current_results" not in st.session_state:
        st.session_state.papers_current_results = None
    
    if "papers_current_page" not in st.session_state:
        st.session_state.papers_current_page = 0
    
    if "papers_search_query" not in st.session_state:
        st.session_state.papers_search_query = ""
    
    # ============= CUSTOM CSS FOR PAGINATION =============
    st.markdown("""
    <style>
    /* Center pagination controls */
    div[data-testid="column"]:has(button[key*="papers_prev"]),
    div[data-testid="column"]:has(button[key*="papers_next"]) {
        display: flex;
        justify-content: center;
        align-items: center;
    }
    
    /* Center the page counter text */
    div[data-testid="column"]:has(p:contains("Page")) {
        display: flex;
        justify-content: center;
        align-items: center;
        text-align: center;
    }
    
    /* Make pagination buttons consistent */
    button[key*="papers_prev"], button[key*="papers_next"] {
        width: 100px !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # ============= SEARCH INTERFACE =============
    
    # Search row with two columns
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.markdown("**Search Studies**")
        
        # Function to handle search on Enter
        def on_search_change():
            if st.session_state.papers_search_input:
                st.session_state.papers_search_triggered = True
                st.session_state.papers_search_query = st.session_state.papers_search_input
            else:
                # If search is cleared, reset everything
                st.session_state.papers_search_triggered = False
                st.session_state.papers_search_query = ""
                st.session_state.papers_current_results = []
                st.session_state.papers_search_performed = False
                st.session_state.papers_last_query = ""
                st.session_state.papers_current_page = 0
        
        # The text input
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
            ["Determinant (A-Z)", 
             "Location (A-Z)", 
             "Building Use (A-Z)", 
             "Scale (A-Z)", 
             "Climate (A-Z)", 
             "Approach (A-Z)"],
            key="papers_sort",
            label_visibility="collapsed"
        )
    
    # Get current search query from widget
    current_search = st.session_state.get("papers_search_input", "")
    
    # Trigger search from on_change event
    if st.session_state.get("papers_search_triggered", False) and current_search:
        search_query = current_search
        st.session_state.papers_search_triggered = False
        st.session_state.papers_search_query = search_query
        st.session_state.papers_last_query = search_query
        st.session_state.papers_search_performed = True
        
        with st.spinner(f"Searching for '{search_query}'..."):
            # Create local connection
            conn_local = sqlite3.connect(db_file)
            cursor = conn_local.cursor()
            
            # Search using SQL LIKE
            search_pattern = f'%{search_query}%'
            
            cursor.execute('''
                SELECT 
                    id,
                    paragraph,
                    criteria,
                    energy_method,
                    direction,
                    scale,
                    climate,
                    location,
                    building_use,
                    approach,
                    sample_size
                FROM energy_data 
                WHERE paragraph IS NOT NULL 
                  AND paragraph != '' 
                  AND paragraph != '0' 
                  AND paragraph != '0.0'
                  AND paragraph != 'None'
                  AND LENGTH(TRIM(paragraph)) > 0
                  AND status NOT IN ("rejected")
                  AND (
                      LOWER(paragraph) LIKE LOWER(?) OR
                      LOWER(criteria) LIKE LOWER(?) OR
                      LOWER(energy_method) LIKE LOWER(?) OR
                      LOWER(location) LIKE LOWER(?) OR
                      LOWER(climate) LIKE LOWER(?) OR
                      LOWER(building_use) LIKE LOWER(?) OR
                      LOWER(approach) LIKE LOWER(?)
                  )
                ORDER BY id DESC
            ''', (search_pattern, search_pattern, search_pattern, 
                  search_pattern, search_pattern, search_pattern, search_pattern))
            
            results = cursor.fetchall()
            conn_local.close()
            
            # Store results
            st.session_state.papers_current_results = results
            st.session_state.papers_current_page = 0
            
            st.rerun()
    
    # ============= RESULTS HEADER AND CLEAR BUTTON =============
    # Only show when there's a search query
    if (st.session_state.get("papers_search_performed", False) and 
        st.session_state.get("papers_last_query", "") and 
        st.session_state.papers_current_results is not None):
        
        results = st.session_state.papers_current_results
        search_query = st.session_state.get("papers_last_query", "")
        
        # Sort results based on selected option
        if sort_order == "Determinant (A-Z)":
            results.sort(key=lambda x: str(x[2] or '').lower())  # criteria
        elif sort_order == "Location (A-Z)":
            results.sort(key=lambda x: str(x[7] or '').lower())  # location
        elif sort_order == "Building Use (A-Z)":
            results.sort(key=lambda x: str(x[8] or '').lower())  # building_use
        elif sort_order == "Scale (A-Z)":
            results.sort(key=lambda x: str(x[5] or '').lower())  # scale
        elif sort_order == "Climate (A-Z)":
            results.sort(key=lambda x: str(x[6] or '').lower())  # climate
        elif sort_order == "Approach (A-Z)":
            results.sort(key=lambda x: str(x[9] or '').lower())  # approach
        
        # Results header with inline clear button - SHOW FOR BOTH RESULTS AND NO RESULTS
        col_header, col_clear = st.columns([4, 1])
        
        with col_header:
            if len(results) == 1:
                st.success(f"Found {len(results)} study matching '{search_query}'")
            elif len(results) > 1:
                st.success(f"Found {len(results)} studies matching '{search_query}'")
            else:
                st.warning(f"No results found for '{search_query}'")
        
        with col_clear:
            # Clear button positioned next to the message
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
        
        # Only show results and pagination if there are results
        if len(results) > 0:
            # ============= TOP PAGINATION =============
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
            
            # Get current page
            start_idx = st.session_state.papers_current_page * PAPERS_PER_PAGE
            end_idx = min(start_idx + PAPERS_PER_PAGE, len(results))
            page_results = results[start_idx:end_idx]
            
            # Display current page indicator
            st.markdown(f"<div style='text-align: right; color: #666; font-size: 0.9em;'>Showing {start_idx + 1}-{end_idx} of {len(results)} records</div>", 
                      unsafe_allow_html=True)
            
            # ============= DISPLAY RESULTS =============
            for record in page_results:
                record_id, paragraph, criteria, energy_method, direction, scale, climate, location, building_use, approach, sample_size = record
                
                st.markdown("---")
                
                # TWO COLUMN LAYOUT
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
                        
                        # Define climate descriptions (same as above)
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
                        
                        # Get the climate code (handle both raw codes and formatted strings)
                        climate_code = climate
                        if " - " in str(climate):
                            climate_code = climate.split(" - ")[0]
                        climate_code = ''.join([c for c in str(climate_code) if c.isalnum()])
                        
                        # Get description
                        description = climate_descriptions.get(climate_code, '')
                        
                        # Format display text
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
                if search_query:
                    import re
                    pattern = re.compile(re.escape(search_query), re.IGNORECASE)
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
                
                st.markdown("<br>", unsafe_allow_html=True)
            
            # ============= BOTTOM PAGINATION =============
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
                
                st.markdown(f"<div style='text-align: right; color: #666; font-size: 0.9em; margin-top: 5px;'>Showing {start_idx + 1}-{end_idx} of {len(results)} records</div>", 
                          unsafe_allow_html=True)
    
    # Initial state - no search performed yet
    elif not st.session_state.papers_search_performed:
        st.info("Enter a search term above and press Enter to find studies in the database.")
    
    # Empty search state - show nothing

def render_enhanced_papers_tab():
    """Enhanced Studies tab - NO statistics for admin to prevent slowdown"""
    
    # Check if current user is admin
    is_admin = st.session_state.get("user_role") == "admin"
    
    if is_admin:
        # Admin gets SIMPLE view - search only, no statistics
        render_papers_tab()
    else:
        # Regular users get both tabs
        view_tab1, view_tab2 = st.tabs(["Search Studies", "Statistics"])
        
        with view_tab1:
            render_papers_tab()
    
        with view_tab2:
            # Statistics tab - this can still load data because it's just counts, not full records
            conn_local = sqlite3.connect(db_file)
            cursor = conn_local.cursor()
            
            # Get comprehensive statistics
            cursor.execute('''
                SELECT 
                    COUNT(DISTINCT paragraph) as total_papers,
                    COUNT(DISTINCT criteria) as unique_determinants,
                    COUNT(DISTINCT energy_method) as unique_outputs,
                    COUNT(DISTINCT location) as unique_locations,
                    COUNT(DISTINCT climate) as unique_climates,
                    COUNT(DISTINCT user) as unique_contributors,
                    SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved_count,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_count
                FROM energy_data 
                WHERE paragraph IS NOT NULL 
                AND paragraph != '' 
                AND paragraph != '0' 
                AND paragraph != '0.0'
                AND paragraph != 'None'
                AND LENGTH(TRIM(paragraph)) > 0
            ''')
            
            stats = cursor.fetchone()
            
            # Display statistics in columns
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Studies", stats[0] or 0)
                st.metric("Unique Determinants", stats[1] or 0)
                st.metric("Unique Energy Outputs", stats[2] or 0)
            
            with col2:
                st.metric("Unique Locations", stats[3] or 0)
                st.metric("Unique Climates", stats[4] or 0)
            
            # Show climate code distribution with colors and descriptions
            # In render_enhanced_papers_tab(), replace the climate distribution section

            # Show climate code distribution with horizontal bars
            st.subheader("Climate Code Distribution")

            # Define climate descriptions (keeping your existing dictionary)
            climate_descriptions = {
                # Tropical Climates
                'Af': 'Tropical Rainforest', 
                'Am': 'Tropical Monsoon', 
                'Aw': 'Tropical Savanna',
                
                # Arid Climates
                'BWh': 'Hot Desert', 
                'BWk': 'Cold Desert', 
                'BSh': 'Hot Semi-arid', 
                'BSk': 'Cold Semi-arid',
                
                # Temperate Climates
                'Cfa': 'Humid Subtropical', 
                'Cfb': 'Oceanic', 
                'Cfc': 'Subpolar Oceanic',
                'Csa': 'Hot-summer Mediterranean', 
                'Csb': 'Warm-summer Mediterranean',
                'Cwa': 'Monsoon-influenced Humid Subtropical',
                
                # Continental Climates
                'Dfa': 'Hot-summer Humid Continental', 
                'Dfb': 'Warm-summer Humid Continental', 
                'Dfc': 'Subarctic', 
                'Dfd': 'Extremely Cold Subarctic',
                'Dwa': 'Monsoon-influenced Hot-summer Humid Continental',
                'Dwb': 'Monsoon-influenced Warm-summer Humid Continental',
                'Dwc': 'Monsoon-influenced Subarctic',
                'Dwd': 'Monsoon-influenced Extremely Cold Subarctic',
                
                # Polar Climates
                'ET': 'Tundra', 
                'EF': 'Ice Cap',
                
                # Special cases
                'Var': 'Varies / Multiple Climates'
            }

            cursor.execute('''
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
                AND status NOT IN ("rejected")
                GROUP BY climate
                ORDER BY count DESC
                LIMIT 15
            ''')

            top_climates = cursor.fetchall()

            if top_climates:
                # Find max count for scaling bars
                max_count = max(count for _, count in top_climates)
                
                # Create a list for processing
                climate_data = []
                for climate, count in top_climates:
                    # Extract clean climate code
                    climate_code = climate
                    if " - " in str(climate):
                        climate_code = climate.split(" - ")[0]
                    climate_code = ''.join([c for c in str(climate_code) if c.isalnum()])
                    
                    # Get description and color
                    description = climate_descriptions.get(climate_code, '')
                    color = get_climate_color(climate_code)
                    
                    climate_data.append({
                        'code': climate_code,
                        'description': description,
                        'count': count,
                        'width_percent': (count / max_count) * 100,  # Scale relative to max
                        'color': color
                    })
                
                # Display as horizontal bars
                for item in climate_data:
                    # Create two columns - one for description, one for bar and count
                    col_desc, col_bar = st.columns([1.2, 3])
                    
                    with col_desc:
                        # Show only the description, vertically centered using markdown spacing
                        if item['description']:
                            # Use div with flexbox to vertically center the text
                            desc_html = f'''
                            <div style="display: flex; align-items: center; height: 48px; margin: 8px 0;">
                                <span style="font-style: italic; color: #555;">{item['description']}</span>
                            </div>
                            '''
                            st.markdown(desc_html, unsafe_allow_html=True)
                        else:
                            # Fallback to code if no description
                            desc_html = f'''
                            <div style="display: flex; align-items: center; height: 48px; margin: 8px 0;">
                                <span style="font-weight: 500;">{item['code']}</span>
                            </div>
                            '''
                            st.markdown(desc_html, unsafe_allow_html=True)
                    
                    with col_bar:
                        # Create horizontal bar with just the code inside, count outside
                        bar_html = f'''
                        <div style="display: flex; align-items: center; margin: 8px 0; width: 100%; height: 48px;">
                            <div style="
                                width: {item['width_percent']}%;
                                background-color: {item['color']};
                                height: 32px;
                                border-radius: 4px;
                                display: flex;
                                align-items: center;
                                padding-left: 8px;
                                color: black;
                                font-weight: 500;
                                min-width: 50px;
                                white-space: nowrap;
                            ">
                                {item['code']}
                            </div>
                            <div style="margin-left: 10px; font-weight: 500; color: #333; min-width: 30px;">
                                {item['count']}
                            </div>
                        </div>
                        '''
                        st.markdown(bar_html, unsafe_allow_html=True)
                
                # Show total
                total_studies = sum(count for _, count in top_climates)
                st.caption(f"Total studies with climate data: {total_studies}")
                
            else:
                st.info("No climate data available")
            
            # Create a DataFrame for better display
            climate_data = []
            for climate, count in top_climates:
                # Extract clean climate code
                climate_code = climate
                if " - " in str(climate):
                    climate_code = climate.split(" - ")[0]
                climate_code = ''.join([c for c in str(climate_code) if c.isalnum()])
                
                # Get description and color
                description = climate_descriptions.get(climate_code, '')
                color = get_climate_color(climate_code)
                
                climate_data.append({
                    'code': climate_code,
                    'description': description,
                    'count': count,
                    'color': color
                })
            
            # # Display as colored badges with descriptions
            # for item in climate_data:
            #     col1, col2 = st.columns([3, 1])
            #     with col1:
            #         # Create colored badge with code and description
            #         display_text = f"{item['code']} - {item['description']}" if item['description'] else item['code']
            #         st.markdown(
            #             f"<span style='background-color: {item['color']}; padding: 2px 8px; border-radius: 10px; color: black; font-weight: 500;'>{display_text}</span>", 
            #             unsafe_allow_html=True
            #         )
            #     with col2:
            #         st.write(f"**{item['count']}** studies")
            
            # Show top determinants
            st.subheader("Most Studied Determinants")
            cursor.execute('''
                SELECT criteria, COUNT(*) as count
                FROM energy_data 
                WHERE paragraph IS NOT NULL 
                AND paragraph != '' 
                AND paragraph != '0' 
                AND paragraph != '0.0'
                AND paragraph != 'None'
                AND LENGTH(TRIM(paragraph)) > 0
                AND status NOT IN ("rejected")
                GROUP BY criteria
                ORDER BY count DESC
                LIMIT 10
            ''')
            
            top_determinants = cursor.fetchall()
            for i, (criteria, count) in enumerate(top_determinants, 1):
                st.write(f"{i}. **{criteria}**: {count} studies")
            
            conn_local.close()

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
    """Get ALL valid Köppen climate options with counts - FILTER based on current search criteria"""
    cursor = conn.cursor()
    
    # Define ALL valid Köppen codes including the new ones we added
    valid_koppen_codes = [
        # Group A: Tropical
        'Af', 'Am', 'Aw',
        
        # Group B: Arid
        'BWh', 'BWk', 'BSh', 'BSk',
        
        # Group C: Temperate
        'Cfa', 'Cfb', 'Cfc', 
        'Csa', 'Csb',
        'Cwa', 'Cwb', 'Cwc',
        
        # Group D: Continental
        'Dfa', 'Dfb', 'Dfc', 'Dfd',
        'Dwa', 'Dwb', 'Dwc', 'Dwd',
        
        # Group E: Polar
        'ET', 'EF',
        
        # Special cases
        'Var'
    ]
    
    # Create case-insensitive condition for valid codes
    valid_conditions = ' OR '.join([f'UPPER(climate) = UPPER(?)' for _ in valid_koppen_codes])
    
    query = f'''
        SELECT climate, COUNT(*) as count
        FROM energy_data 
        WHERE climate IS NOT NULL 
          AND climate != '' 
          AND climate != 'Awaiting data'
          AND ({valid_conditions})
          AND paragraph IS NOT NULL 
          AND paragraph != '' 
          AND paragraph != '0' 
          AND paragraph != '0.0'
          AND paragraph != 'None'
          AND LENGTH(TRIM(paragraph)) > 0
          AND status NOT IN ("pending", "rejected")
    '''
    params = valid_koppen_codes.copy()
    
    # Apply other filters
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
    
    query += ' GROUP BY climate ORDER BY climate ASC'
    
    cursor.execute(query, params)
    results = cursor.fetchall()
    
    # Define Köppen climate classifications with descriptions (including all new codes)
    koppen_climates_with_descriptions = {
        # Group A: Tropical Climates
        'AF': 'Tropical Rainforest', 
        'AM': 'Tropical Monsoon', 
        'AW': 'Tropical Savanna',
        
        # Group B: Arid Climates
        'BWH': 'Hot Desert', 
        'BWK': 'Cold Desert', 
        'BSH': 'Hot Semi-arid', 
        'BSK': 'Cold Semi-arid',
        
        # Group C: Temperate Climates
        'CFA': 'Humid Subtropical', 
        'CFB': 'Oceanic', 
        'CFC': 'Subpolar Oceanic',
        'CSA': 'Hot-summer Mediterranean', 
        'CSB': 'Warm-summer Mediterranean',
        'CWA': 'Monsoon-influenced Humid Subtropical',
        'CWB': 'Monsoon-influenced Subtropical Highland',
        'CWC': 'Monsoon-influenced Cold Subtropical Highland',
        
        # Group D: Continental Climates
        'DFA': 'Hot-summer Humid Continental', 
        'DFB': 'Warm-summer Humid Continental', 
        'DFC': 'Subarctic', 
        'DFD': 'Extremely Cold Subarctic',
        'DWA': 'Monsoon-influenced Hot-summer Humid Continental',
        'DWB': 'Monsoon-influenced Warm-summer Humid Continental',
        'DWC': 'Monsoon-influenced Subarctic',
        'DWD': 'Monsoon-influenced Extremely Cold Subarctic',
        
        # Group E: Polar Climates
        'ET': 'Tundra', 
        'EF': 'Ice Cap',
        
        # Special cases
        'VAR': 'Varies / Multiple Climates'
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
        '#999999': '⬜',  # Var
    }
    
    # Create a dictionary of counts
    count_dict = {}
    for climate, count in results:
        if climate and str(climate).strip():
            climate_clean = climate
            if " - " in str(climate):
                climate_clean = climate.split(" - ")[0]
            climate_clean = ''.join([c for c in str(climate_clean) if c.isalnum()])
            if climate_clean.upper() in koppen_climates_with_descriptions:
                count_dict[climate_clean] = count
    
    # Format ONLY climate codes that have counts > 0
    valid_climates = []
    for climate_code in valid_koppen_codes:
        climate_upper = climate_code.upper()
        if climate_upper in koppen_climates_with_descriptions:
            count = count_dict.get(climate_code, 0)
            # ONLY include if count > 0
            if count > 0:
                description = koppen_climates_with_descriptions[climate_upper]
                color = get_climate_color(climate_code)
                emoji = color_to_emoji.get(color, '⬜')
                formatted_climate = f"{emoji} {climate_code} - {description} [{count}]"
                valid_climates.append((climate_code, formatted_climate, color, count))
    
    # Sort by climate code
    valid_climates.sort(key=lambda x: x[0])
    return [(formatted, color, count) for _, formatted, color, count in valid_climates]

# Also update the get_climate_color function to handle case-insensitive:
def get_climate_color(climate_code):
    """Get color for climate code - handle mixed case and special cases"""
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
        'CFA': '#C5FF4B', 'CFB': '#64FD33', 'CFC': '#36C901',
        'CSA': '#FFFE04', 'CSB': '#CDCE08',
        'CWA': '#95FE97', 'CWB': '#62C764', 'CWC': '#379632',
        
        # Continental Climates
        'DFA': '#01FEFC', 'DFB': '#3DC6FA', 'DFC': '#037F7F', 'DFD': '#004860',
        'DWA': '#A5ADFE', 'DWB': '#4A78E7', 'DWC': '#48DDB1', 'DWD': '#32028A',
        
        # Polar Climates
        'ET': '#AFB0AB', 'EF': '#686964',
        
        # Special categories
        'VAR': '#999999',
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
    """Unified search interface used by both main app and admin - WITH FULL FILTERS AND FORMATTING"""
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
    selected_criteria = st.selectbox("Determinant", criteria_list, key="unified_criteria")
    actual_criteria = selected_criteria.split(" [")[0] if selected_criteria != "Select a determinant" else None
    
    if actual_criteria:
        energy_method_counts = query_energy_method_counts(conn, actual_criteria)
        method_list = ["Select an output"] + [f"{method} [{count}]" for method, count in energy_method_counts]
        
        selected_method = st.selectbox("Energy Output(s)", method_list, key="unified_method")
        actual_method = selected_method.split(" [")[0] if selected_method != "Select an output" else None
        
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
            
            if selected_direction:
                # Filters
                col_scale, col_climate = st.columns(2)
                
                with col_scale:
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
                    if climate_options:
                        current_scale_filter = []
                        if 'unified_selected_scale' in st.session_state and st.session_state.unified_selected_scale != "All":
                            scale_name = st.session_state.unified_selected_scale.split(" [")[0]
                            current_scale_filter = [scale_name]
                        
                        current_location_filter = []
                        if 'unified_selected_location' in st.session_state and st.session_state.unified_selected_location != "All":
                            location_name = st.session_state.unified_selected_location.split(" [")[0]
                            current_location_filter = [location_name]
                        
                        climate_options_with_counts = query_climate_options_with_counts(
                            conn, 
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
                        conn, actual_criteria, actual_method, current_direction, 
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
                        conn, actual_criteria, actual_method, current_direction,
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
                        conn, actual_criteria, actual_method, current_direction,
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
        selected_climates_upper = [c.upper() for c in selected_climates]
        filtered_records = [r for r in filtered_records if r[8] and r[8].upper() in selected_climates_upper]
    if selected_locations:
        filtered_records = [r for r in filtered_records if r[9] in selected_locations]
    if selected_building_uses:
        filtered_records = [r for r in filtered_records if r[10] in selected_building_uses]
    if selected_approaches:
        filtered_records = [r for r in filtered_records if r[11] in selected_approaches]

    # ============= RESULTS DISPLAY - NO EXPANDER, DIRECT 2-COLUMN LAYOUT =============
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

        # DISPLAY EACH RECORD DIRECTLY - NO EXPANDER, NO HEADINGS
        for count, record in enumerate(display_records, start=1):
            record_id, criteria, energy_method, direction, paragraph, user, status, scale, climate, location, building_use, approach, sample_size = record
            
            st.markdown("---")
            
            # TWO COLUMN LAYOUT - WITH FIELD LABELS, NO EMOJIS
            col1, col2 = st.columns(2)
            
            with col1:
                clean_criteria = sanitize_metadata_text(criteria)
                clean_energy_method = sanitize_metadata_text(energy_method)
                clean_location = sanitize_metadata_text(location) if location else None
                clean_building_use = sanitize_metadata_text(building_use) if building_use else None
                
                st.write(f"**{clean_criteria}** → **{clean_energy_method}** ({direction})")
                if clean_location:
                    st.write(f"**Location:** {clean_location}")
                if clean_building_use:
                    st.write(f"**Building Use:** {clean_building_use}")
            
            with col2:
                st.write(f"**Scale:** {scale}")
                if climate:
                    # Format climate with color badge
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
                                if " [" in formatted:
                                    formatted_climate_display = formatted.split(" [")[0]
                                else:
                                    formatted_climate_display = formatted
                                break
                    
                    color = get_climate_color(climate)
                    st.markdown(f"**Climate:** <span style='background-color: {color}; padding: 2px 8px; border-radius: 10px; color: black;'>{formatted_climate_display}</span>", unsafe_allow_html=True)
                
                if approach:
                    st.write(f"**Approach:** {approach}")
                if sample_size:
                    st.write(f"**Sample Size:** {sample_size}")

            # STUDY CONTENT - SELECTABLE, CLICKABLE LINKS, NO HEADING
            # Highlight matching terms
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
            
            # Convert URLs to clickable links
            paragraph_with_links = convert_urls_to_links(highlighted_paragraph)
            
            # Display as selectable text box - NOT LOCKED
            st.markdown(
                f'''
                <div style="
                    border: 1px solid #e0e0e0;
                    padding: 15px;
                    border-radius: 8px;
                    background-color: #f9f9fb;  /* Light grey tint */
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

def render_contribute_tab():
    """Render the Contribute tab content"""
    st.title("Contribute to the SpatialBuild Energy project.")
    whats_next_html = ("""
    Sign up or log in to add your study or reference, sharing determinants, energy outputs and their relationships. If approved your contribution will be added to the database. Your help will improve this resource for urban planners, developers, and policymakers.</p>
    Let's work together to optimize macro-scale energy use and create sustainable cities. <br><strong>Dive in and explore today.</strong>"""
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
    2. Select Energy Outputs: For example energy use intensity or heating demand.<br>
    3. Filter your Results and access the relevant study via the links provided."""
    )
    st.markdown(how_it_works_html, unsafe_allow_html=True)
    
    render_unified_search_interface(enable_editing=enable_editing)

# MAIN APP LAYOUT - UPDATED WITH PAPERS TAB AND TAB STATE MANAGEMENT
# Initialize current_tab if not exists
if "current_tab" not in st.session_state:
    st.session_state.current_tab = "tab0"

if st.session_state.logged_in:
    if st.session_state.current_user == "admin":
        # Admin view with Papers tab
        tab_labels = ["SpatialBuild Energy", "Studies", "Contribute", "Edit/Review"]
        
        # Create tabs - all tabs will render their content
        tabs = st.tabs(tab_labels)
        
        # Create references to tabs
        tab0, tab1, tab2, tab3 = tabs
        
        # Render ALL tabs - Streamlit handles which one is visible
        with tab0:
            render_spatialbuild_tab(enable_editing=False)
            # Update current tab when this tab is active
            st.session_state.current_tab = "tab0"
        
        with tab1:
            render_enhanced_papers_tab()
            st.session_state.current_tab = "tab1"
        
        with tab2:
            render_contribute_tab()
            st.session_state.current_tab = "tab2"
        
        with tab3:
            # Check if we're currently editing a record in missing data
            if st.session_state.get("admin_editing_in_missing_data", False):
                # Show a back button to return to missing data review
                if st.button("← Back to Missing Data Review"):
                    # Clear edit flags
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
        # Regular user view with Papers tab
        tab_labels = ["SpatialBuild Energy", "Studies", "Contribute", "Your Contributions"]
        
        # Create tabs
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
    # Not logged in view with Papers tab
    tab_labels = ["SpatialBuild Energy", "Studies", "Contribute"]
    
    # Create tabs
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

# Add this after your main app layout to ensure tabs stay active
st.markdown("""
<script>
// Function to set active tab
function setActiveTab() {
    const urlParams = new URLSearchParams(window.location.search);
    const tabParam = urlParams.get('tab');
    
    // If we have a stored tab in sessionStorage, use it
    const savedTab = sessionStorage.getItem('active_tab');
    if (savedTab !== null) {
        const tabButtons = document.querySelectorAll('button[data-baseweb="tab"]');
        if (tabButtons.length > parseInt(savedTab)) {
            setTimeout(function() {
                tabButtons[parseInt(savedTab)].click();
            }, 100);
        }
    }
}

// Run when page loads
document.addEventListener('DOMContentLoaded', setActiveTab);

// Also run after any Streamlit rerun
const observer = new MutationObserver(function(mutations) {
    setActiveTab();
});

observer.observe(document.body, {
    childList: true,
    subtree: true
});
</script>
""", unsafe_allow_html=True)

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