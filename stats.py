# stats.py
import streamlit as st
from color_schemes import (
    get_climate_color,
    get_scale_color,
    get_building_use_color,
    get_approach_color,
    climate_descriptions
)
from sanitize_metadata_text import sanitize_metadata_text

def render_statistics_tab(db_connection):
    """Render the Statistics tab with all distributions"""
    st.subheader("Database Statistics")
    
    # Get all non-rejected records
    all_records = db_connection.get_energy_data(limit=5000)
    valid_records = [r for r in all_records if r.get('status') != 'rejected']
    
    if not valid_records:
        st.info("No data available for statistics")
        return
    
    # First, identify unique studies by paragraph content
    study_map = {}  # Map paragraph -> first record with that paragraph
    for record in valid_records:
        para = record.get('paragraph')
        if para and para not in ['0', '0.0', '', None]:
            if para not in study_map:
                study_map[para] = record
    
    unique_studies = list(study_map.values())
    total_studies = len(unique_studies)
    total_records = len(valid_records)
    
    # Count unique values across all records
    unique_determinants = set(r.get('criteria') for r in valid_records if r.get('criteria'))
    unique_outputs = set(r.get('energy_method') for r in valid_records if r.get('energy_method'))
    unique_locations = set(r.get('location') for r in valid_records if r.get('location') and r.get('location') not in ['', None])
    unique_climates = set(r.get('climate') for r in valid_records if r.get('climate') and r.get('climate') not in ['Awaiting data', ''])
    unique_scales = set(r.get('scale') for r in valid_records if r.get('scale') and r.get('scale') not in ['Awaiting data', ''])
    unique_building_uses = set(r.get('building_use') for r in valid_records if r.get('building_use') and r.get('building_use') not in ['', None])
    unique_approaches = set(r.get('approach') for r in valid_records if r.get('approach') and r.get('approach') not in ['', None])
    unique_contributors = set(r.get('user') for r in valid_records if r.get('user'))

    # Display summary metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Records", total_records)
        #st.metric("Unique Determinants", len(unique_determinants))
    with col2:
        st.metric("Unique Studies", total_studies)
        #st.metric("Unique Energy Outputs", len(unique_outputs))
    with col3:
        st.metric("Unique Locations", len(unique_locations))
        #st.metric("Unique Contributors", len(unique_contributors))
    
   
    
    # Create tabs for different distributions
    dist_tab1, dist_tab2, dist_tab3, dist_tab4, dist_tab5 = st.tabs([
        " Determinant",
        " Climate", 
        " Scale", 
        " Building Use", 
        " Approach"
    ])
    with dist_tab1:
        render_determinant_chart(unique_studies)

    with dist_tab2:
        render_climate_distribution(unique_studies)
    
    with dist_tab3:
        render_scale_distribution(unique_studies)
    
    with dist_tab4:
        render_building_use_distribution(unique_studies)
    
    with dist_tab5:
        render_approach_distribution(unique_studies)
    
    st.divider()
    
    

def render_climate_distribution(unique_studies):
    """Render climate code distribution with clean bars"""
    st.subheader("Climate Code Distribution")
    
    # Count climates by UNIQUE STUDY
    climate_counts = {}
    for study in unique_studies:
        climate = study.get('climate')
        if climate and climate not in ['Awaiting data', '']:
            # Extract the climate code
            climate_code = climate
            if " - " in str(climate):
                climate_code = climate.split(" - ")[0]
            climate_code = ''.join([c for c in str(climate_code) if c.isalnum()])
            climate_counts[climate_code] = climate_counts.get(climate_code, 0) + 1
    
    if climate_counts:
        render_clean_distribution_bars(climate_counts, climate_descriptions, get_climate_color, show_code=True)
    else:
        st.info("No climate data available")

def render_scale_distribution(unique_studies):
    """Render scale distribution with clean bars"""
    st.subheader("Scale Distribution")
    
    # Count scales by UNIQUE STUDY
    scale_counts = {}
    for study in unique_studies:
        scale = study.get('scale')
        if scale and scale not in ['Awaiting data', '']:
            scale_clean = scale
            if " - " in str(scale):
                scale_clean = scale.split(" - ")[0]
            scale_counts[scale_clean] = scale_counts.get(scale_clean, 0) + 1
    
    if scale_counts:
        render_clean_distribution_bars(scale_counts, {}, get_scale_color)
    else:
        st.info("No scale data available")

def render_building_use_distribution(unique_studies):
    """Render building use distribution with clean bars"""
    st.subheader("Building Use Distribution")
    
    # Count building uses by UNIQUE STUDY
    building_counts = {}
    for study in unique_studies:
        building_use = study.get('building_use')
        if building_use and building_use not in ['', None]:
            building_counts[building_use] = building_counts.get(building_use, 0) + 1
    
    if building_counts:
        render_clean_distribution_bars(building_counts, {}, get_building_use_color)
    else:
        st.info("No building use data available")

def render_approach_distribution(unique_studies):
    """Render approach distribution with clean bars"""
    st.subheader("Approach Distribution")
    
    # Count approaches by UNIQUE STUDY
    approach_counts = {}
    for study in unique_studies:
        approach = study.get('approach')
        if approach and approach not in ['', None]:
            approach_counts[approach] = approach_counts.get(approach, 0) + 1
    
    if approach_counts:
        render_clean_distribution_bars(approach_counts, {}, get_approach_color)
    else:
        st.info("No approach data available")

def render_clean_distribution_bars(counts, descriptions, color_func, show_code=False):
    """Generic function to render distribution bars with clean design"""
    if not counts:
        return
    
    sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    max_count = max(count for _, count in sorted_items)
    
    for item, count in sorted_items:
        # Get description if available
        description = descriptions.get(item, '') if descriptions else ''
        
        # Determine what to show in the left column
        if description and show_code:
            left_text = f"{item} - {description}"
        elif description:
            left_text = description
        else:
            left_text = item
            
        color = color_func(item)
        width_percent = (count / max_count) * 100
        
        col_desc, col_bar = st.columns([1.5, 3])
        
        with col_desc:
            desc_html = f'''
            <div style="display: flex; align-items: center; height: 32px; margin: 2px 0;">
                <span style="font-style: italic; color: #555; font-size: 0.9em;">{left_text}</span>
            </div>
            '''
            st.markdown(desc_html, unsafe_allow_html=True)
        
        with col_bar:
            bar_html = f'''
            <div style="display: flex; align-items: center; margin: 2px 0; width: 100%; height: 32px;">
                <div style="
                    width: {width_percent}%;
                    background-color: {color};
                    height: 24px;
                    border-radius: 4px;
                "></div>
                <div style="margin-left: 10px; font-weight: 500; color: #333; min-width: 30px;">
                    {count}
                </div>
            </div>
            '''
            st.markdown(bar_html, unsafe_allow_html=True)
    
    st.caption(f"Total studies with data: {sum(counts.values())}")

def render_determinant_chart(unique_studies):
    """Render top determinants chart with toggle"""
    st.subheader("Top 10 Studied Determinants (by unique study)")
    
    # Initialize session state for showing all determinants
    if 'show_all_determinants_stats' not in st.session_state:
        st.session_state.show_all_determinants_stats = False
    
    determinant_counts = {}
    for study in unique_studies:
        criteria = study.get('criteria')
        if criteria:
            clean_criteria = sanitize_metadata_text(criteria)
            determinant_counts[clean_criteria] = determinant_counts.get(clean_criteria, 0) + 1
    
    if determinant_counts:
        # Determine which set to show
        if st.session_state.show_all_determinants_stats:
            display_determinants = sorted(determinant_counts.items(), key=lambda x: x[1], reverse=True)
            button_label = " Show Top 10 Only"
        else:
            display_determinants = sorted(determinant_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            button_label = " Show All Determinants"
        
        max_count = max(count for _, count in determinant_counts.items())
        
        # Create horizontal bar chart
        for criteria, count in display_determinants:
            width_percent = (count / max_count) * 100
            
            col_name, col_bar = st.columns([2, 3])
            
            with col_name:
                st.write(f"**{criteria}**")
            
            with col_bar:
                bar_html = f'''
                <div style="display: flex; align-items: center; margin: 8px 0; width: 100%; height: 32px;">
                    <div style="
                        width: {width_percent}%;
                        background-color: #95a5a6;
                        height: 24px;
                        border-radius: 4px;
                    "></div>
                    <div style="margin-left: 10px; font-weight: 500; color: #333; min-width: 30px;">
                        {count}
                    </div>
                </div>
                '''
                st.markdown(bar_html, unsafe_allow_html=True)
        
        # Toggle button
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button(button_label, key="toggle_determinants_btn", use_container_width=True):
                st.session_state.show_all_determinants_stats = not st.session_state.show_all_determinants_stats
                st.rerun()
        
        # Show count info
        if st.session_state.show_all_determinants_stats:
            st.caption(f"Showing all {len(determinant_counts)} determinants")
        else:
            st.caption(f"Showing top 10 of {len(determinant_counts)} total determinants")
    else:
        st.info("No determinant data available")