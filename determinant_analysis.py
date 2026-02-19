# determinant_analysis.py
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from collections import Counter
from climate_colors import get_climate_color  # Fixed import!

def analyze_determinant_pair(db_connection, determinant, top_keywords, bottom_keywords):
    """Analyze a determinant against two energy output categories"""
    all_records = db_connection.get_energy_data(limit=5000)
    
    top_records = []
    bottom_records = []
    
    for record in all_records:
        # Check determinant match (case-insensitive, partial)
        criteria = record.get('criteria', '')
        if determinant.lower() not in criteria.lower():
            continue
            
        energy_method = record.get('energy_method', '').lower()
        direction = record.get('direction')
        climate = record.get('climate')
        
        if not climate or not direction:
            continue
            
        # Clean climate code
        climate_code = climate
        if " - " in str(climate):
            climate_code = climate.split(" - ")[0]
        climate_code = ''.join([c for c in str(climate_code) if c.isalnum()])
        
        # Categorize
        if any(keyword in energy_method for keyword in top_keywords):
            top_records.append({
                'climate': climate_code,
                'direction': direction
            })
        elif any(keyword in energy_method for keyword in bottom_keywords):
            bottom_records.append({
                'climate': climate_code,
                'direction': direction
            })
    
    return top_records, bottom_records


def render_frequency_analysis(db_connection):
    st.subheader("📊 Moderator Analysis")
    
    
    # Initialize session state for storing multiple visuals
    if 'saved_visuals' not in st.session_state:
        st.session_state.saved_visuals = []
    
    # Get all determinants with counts
    all_records = db_connection.get_energy_data(limit=5000)
    
    # Count determinants
    determinant_counts = {}
    for record in all_records:
        criteria = record.get('criteria')
        if criteria and criteria not in ['', None]:
            determinant_counts[criteria] = determinant_counts.get(criteria, 0) + 1
    
    # Sort determinants by count
    determinants_with_counts = sorted(
        determinant_counts.items(), 
        key=lambda x: x[1], 
        reverse=True
    )
    determinant_options = ["-- Choose a determinant --"] + [f"{d} [{c}]" for d, c in determinants_with_counts]
    
    # Create three columns: left for controls (30%), middle for chart (40%), right blank (30%)
    left_col, mid_col, right_col = st.columns([.5, 0.5, 1])
    
    with left_col:
         # Analysis type selector
        analysis_type = st.selectbox(
            "Select moderator",
            options=[
                "🌍 Climate",
                "📏 Scale"
            ],
            key="analysis_type_selector"
        )
        # Create placeholders for dynamic dropdowns
        top_dropdown = st.empty()
        det_dropdown = st.empty()
        bottom_dropdown = st.empty()
        
        # Determinant dropdown (always active)
        selected_det_with_count = det_dropdown.selectbox(
            "Select determinant",
            options=determinant_options,
            key="det_selector"
        )
        

        # Initially, show disabled/inactive dropdowns for energy outputs
        top_dropdown.selectbox(
            "↑ Energy output (increase)",
            options=["-- Choose energy output --"],
            key="top_energy_initial",
            disabled=True
        )
        
        bottom_dropdown.selectbox(
            "↓ Energy output (decrease)",
            options=["-- Choose energy output --"],
            key="bottom_energy_initial",
            disabled=True
        )
    
        # In your render_frequency_analysis function, replace the section starting from "with mid_col:" with this:

        with mid_col:
            # Initialize variables
            selected_determinant = None
            det_records = []
            increase_methods = {}
            decrease_methods = {}
            selected_top = None
            selected_bottom = None
            top_items = []
            bottom_items = []
            top_sorted = []
            bottom_sorted = []
            top_height = 0
            bottom_height = 0
            
            # Check if determinant is selected
            if selected_det_with_count and selected_det_with_count != "-- Choose a determinant --":
                selected_determinant = selected_det_with_count.split(" [")[0]
                
                # Get energy outputs for this determinant
                det_records = [r for r in all_records if r.get('criteria') == selected_determinant]
                
                # Get energy outputs for increase direction
                increase_methods = {}
                for record in det_records:
                    if record.get('direction') == 'Increase':
                        method = record.get('energy_method')
                        if method:
                            increase_methods[method] = increase_methods.get(method, 0) + 1
                
                # Get energy outputs for decrease direction
                decrease_methods = {}
                for record in det_records:
                    if record.get('direction') == 'Decrease':
                        method = record.get('energy_method')
                        if method:
                            decrease_methods[method] = decrease_methods.get(method, 0) + 1
                
                # Update the dropdowns in left column
                with left_col:
                    # Update top dropdown (now active)
                    if increase_methods:
                        increase_options = ["-- Choose energy output --"] + [f"{m} [{c}]" for m, c in sorted(increase_methods.items(), key=lambda x: x[1], reverse=True)]
                        selected_top = top_dropdown.selectbox(
                            "↑ Energy output (increase)",
                            options=increase_options,
                            key="top_energy_active"
                        )
                    
                    # Update bottom dropdown (now active)
                    if decrease_methods:
                        decrease_options = ["-- Choose energy output --"] + [f"{m} [{c}]" for m, c in sorted(decrease_methods.items(), key=lambda x: x[1], reverse=True)]
                        selected_bottom = bottom_dropdown.selectbox(
                            "↓ Energy output (decrease)",
                            options=decrease_options,
                            key="bottom_energy_active"
                        )
            
            # Define color function based on analysis type
            def get_item_color(item):
                if "Climate" in analysis_type:
                    return get_climate_color(item)
                else:  # Scale frequency
                    scale_colors = {
                        'National': '#FF6B6B',
                        'Regional': '#4ECDC4',
                        'City': '#45B7D1',
                        'Urban': '#96CEB4',
                        'Neighborhood': '#FFE194',
                        'Building': '#E78F8F',
                        'Global': '#B83B5E',
                        'Continental': '#6C5B7B',
                        'Local': '#F08A5D',
                        'Municipal': '#4D96FF',
                    }
                    for key, color in scale_colors.items():
                        if key.lower() in str(item).lower():
                            return color
                    return '#9B9B9B'
            
            # Process top stack if selected
            if selected_determinant and selected_top and selected_top != "-- Choose energy output --":
                selected_top_energy = selected_top.split(" [")[0]
                
                # Filter records for top stack
                top_items = []
                for record in det_records:
                    if record.get('direction') == 'Increase':
                        method = record.get('energy_method', '').lower()
                        if selected_top_energy.lower() in method:
                            if "Climate" in analysis_type:
                                item = record.get('climate')
                            else:
                                item = record.get('scale')
                            
                            if item and item not in ['', None, 'Awaiting data']:
                                item_clean = item
                                if " - " in str(item):
                                    item_clean = item.split(" - ")[0]
                                item_clean = ''.join([c for c in str(item_clean) if c.isalnum()])
                                top_items.append(item_clean)
                
                if top_items:
                    top_counts = Counter(top_items)
                    top_sorted = sorted(top_counts.items(), key=lambda x: x[1], reverse=True)
                    top_height = sum(top_counts.values())
            
            # Process bottom stack if selected
            if selected_determinant and selected_bottom and selected_bottom != "-- Choose energy output --":
                selected_bottom_energy = selected_bottom.split(" [")[0]
                
                bottom_items = []
                for record in det_records:
                    if record.get('direction') == 'Decrease':
                        method = record.get('energy_method', '').lower()
                        if selected_bottom_energy.lower() in method:
                            if "Climate" in analysis_type:
                                item = record.get('climate')
                            else:
                                item = record.get('scale')
                            
                            if item and item not in ['', None, 'Awaiting data']:
                                item_clean = item
                                if " - " in str(item):
                                    item_clean = item.split(" - ")[0]
                                item_clean = ''.join([c for c in str(item_clean) if c.isalnum()])
                                bottom_items.append(item_clean)
                
                if bottom_items:
                    bottom_counts = Counter(bottom_items)
                    bottom_sorted = sorted(bottom_counts.items(), key=lambda x: x[1], reverse=True)
                    bottom_height = sum(bottom_counts.values())
            
            
            # CSS styles
            st.markdown("""
            <style>
                .viz-card {
                    background-color: transparent;
                    padding: 0;
                    box-shadow: none;
                    display: block;
                    margin: 10px auto;
                    width: 100%;
                    box-sizing: border-box;
                }
                .stack-container {
                    display: flex;
                    flex-direction: row;
                    align-items: stretch;
                    width: 100%;
                    max-width: 280px;
                    margin: 0 auto;
                    padding: 0;
                }
                .arrow-label {
                    font-size: 10px;
                    font-weight: bold;
                    color: #2c3e50;
                    text-align: center;
                    margin: 2px 0;
                    white-space: nowrap;
                    transform: rotate(-90deg);
                }
                .arrow-up {
                    color: #e74c3c;
                    font-size: 24px;
                    text-align: center;
                    line-height: 1;
                    margin: 0;
                }
                .arrow-down {
                    color: #3498db;
                    font-size: 24px;
                    text-align: center;
                    line-height: 1;
                    margin: 0;
                }
                .bars-column {
                    display: flex;
                    flex-direction: column;
                    flex: 1;
                }
                .frequency-box {
                    width: 100%;
                    height: 28px;
                    margin: 0;
                    padding: 0 3px;
                    border: none;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: black;
                    font-size: 10px;
                    font-weight: bold;
                    box-sizing: border-box;
                    white-space: nowrap;
                    overflow: hidden;
                    text-overflow: ellipsis;
                }
                .display-box {
                    width: 100%;
                    height: 36px;
                    margin: 0;
                    padding: 0 3px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-weight: bold;
                    font-size: 13px;
                    background-color: #f0f2f6;
                    border: 2px solid #000000;
                    box-sizing: border-box;
                    white-space: nowrap;
                    overflow: hidden;
                    text-overflow: ellipsis;
                }
                div[data-testid="stVerticalBlock"] > div {
                    padding: 0 !important;
                }
                .stMarkdown {
                    margin: 0 !important;
                }
            </style>
            """, unsafe_allow_html=True)
            
           # Replace the visualization section in mid_col with this:

            # Only render visualization if determinant is selected
            # Replace the chart section in mid_col with this:

            # Only render visualization if determinant is selected
            if selected_determinant:
                # Create a container for the chart with two columns
                chart_col1, chart_col2 = st.columns([0.25, 1])
                
                with chart_col1:
                    # Arrow column on the left
                    st.markdown('<div style="display: flex; flex-direction: column; height: 100%; position: relative;">', unsafe_allow_html=True)
                    
                    # Calculate total stack heights
                    top_stack_height = top_height * 28 if top_height > 0 else 28
                    bottom_stack_height = bottom_height * 28 if bottom_height > 0 else 28
                    determinant_height = 36
                    
                    # Top arrow section (pointing up from determinant)
                    if top_height > 0 and selected_top:
                        st.markdown(f'''
                        <div style="position: relative; height: {top_stack_height}px; margin-bottom: 0;">
                            <!-- Vertical line -->
                            <div style="position: absolute; left: 20px; top: {top_stack_height}px; width: 2px; height: {top_stack_height}px; background-color: #e74c3c; transform: translateY(-100%);"></div>
                            <!-- Arrow head -->
                            <div style="position: absolute; left: 14px; top: 0; width: 0; height: 0; border-left: 8px solid transparent; border-right: 8px solid transparent; border-bottom: 12px solid #e74c3c;"></div>
                            <!-- Rotated label -->
                            <div style="position: absolute; left: 30px; top: {top_stack_height/2}px; transform: translateY(-50%) rotate(0deg); font-size: 11px; font-weight: bold; color: #e74c3c; white-space: nowrap; writing-mode: vertical-rl; text-orientation: mixed;">
                                {selected_top.split(" [")[0]}
                            </div>
                        </div>
                        ''', unsafe_allow_html=True)
                    else:
                        # Placeholder when no selection
                        st.markdown(f'<div style="height: 28px;"></div>', unsafe_allow_html=True)
                    
                    # Determinant spacer (visual connector)
                    st.markdown(f'<div style="height: {determinant_height}px;"></div>', unsafe_allow_html=True)
                    
                    # Bottom arrow section (pointing down from determinant)
                    if bottom_height > 0 and selected_bottom:
                        st.markdown(f'''
                        <div style="position: relative; height: {bottom_stack_height}px; margin-top: 0;">
                            <!-- Vertical line -->
                            <div style="position: absolute; left: 20px; top: 0; width: 2px; height: {bottom_stack_height}px; background-color: #3498db;"></div>
                            <!-- Arrow head -->
                            <div style="position: absolute; left: 14px; bottom: 0; width: 0; height: 0; border-left: 8px solid transparent; border-right: 8px solid transparent; border-top: 12px solid #3498db;"></div>
                            <!-- Rotated label -->
                            <div style="position: absolute; left: 30px; top: {bottom_stack_height/2}px; transform: translateY(-50%) rotate(0deg); font-size: 11px; font-weight: bold; color: #3498db; white-space: nowrap; writing-mode: vertical-rl; text-orientation: mixed;">
                                {selected_bottom.split(" [")[0]}
                            </div>
                        </div>
                        ''', unsafe_allow_html=True)
                    else:
                        # Placeholder when no selection
                        st.markdown(f'<div style="height: 28px;"></div>', unsafe_allow_html=True)
                    
                    st.markdown('</div>', unsafe_allow_html=True)  # Close arrow column
                
                with chart_col2:
                    # Bars column on the right
                    st.markdown('<div class="bars-column">', unsafe_allow_html=True)
                    
                    # TOP SECTION - Increase results
                    if top_items and selected_top:
                        for item, count in top_sorted:
                            for i in range(count):
                                color = get_item_color(item)
                                if i == 0:
                                    st.markdown(f'<div class="frequency-box" style="background-color: {color};">{item}</div>', unsafe_allow_html=True)
                                else:
                                    st.markdown(f'<div class="frequency-box" style="background-color: {color};"></div>', unsafe_allow_html=True)
                    else:
                        # Placeholder to maintain spacing
                        st.markdown('<div class="frequency-box" style="opacity:0;"></div>', unsafe_allow_html=True)
                    
                    # Middle display box (Determinant)
                    st.markdown(f'<div class="display-box">{selected_determinant}</div>', unsafe_allow_html=True)
                    
                    # BOTTOM SECTION - Decrease results
                    if bottom_items and selected_bottom:
                        for item, count in bottom_sorted:
                            for i in range(count):
                                color = get_item_color(item)
                                if i == 0:
                                    st.markdown(f'<div class="frequency-box" style="background-color: {color};">{item}</div>', unsafe_allow_html=True)
                                else:
                                    st.markdown(f'<div class="frequency-box" style="background-color: {color};"></div>', unsafe_allow_html=True)
                    else:
                        # Placeholder to maintain spacing
                        st.markdown('<div class="frequency-box" style="opacity:0;"></div>', unsafe_allow_html=True)
                    
                    st.markdown('</div>', unsafe_allow_html=True)  # Close bars-column
                st.markdown('</div>', unsafe_allow_html=True)  # Close stack-container
                st.markdown('</div>', unsafe_allow_html=True)  # Close viz-card
            
            # Add button to save this visual (moved to left column)
            with left_col:
                if selected_determinant and selected_top and selected_bottom:
                    if st.button("📸 Add to Analysis Suite", key="save_visual"):
                        if top_items and bottom_items:
                            visual_html = []
                            visual_html.append('<div class="viz-card" style="margin-bottom: 10px;">')
                            visual_html.append('<div class="stack-container">')
                            
                            # Add arrow column for saved visual
                            visual_html.append('<div class="arrow-column">')
                            
                            # Top arrow
                            visual_html.append(f'<div class="arrow-up-section" style="height: {top_height * 28}px;">')
                            visual_html.append('<div class="arrow-up">↑</div>')
                            visual_html.append(f'<div class="arrow-label">{selected_top.split(" [")[0]}</div>')
                            visual_html.append('</div>')
                            
                            # Determinant spacer
                            visual_html.append('<div style="height: 36px;"></div>')
                            
                            # Bottom arrow
                            visual_html.append(f'<div class="arrow-down-section" style="height: {bottom_height * 28}px;">')
                            visual_html.append('<div class="arrow-down">↓</div>')
                            visual_html.append(f'<div class="arrow-label">{selected_bottom.split(" [")[0]}</div>')
                            visual_html.append('</div>')
                            
                            visual_html.append('</div>')  # Close arrow-column
                            
                            # Bars column
                            visual_html.append('<div class="bars-column">')
                            
                            # Top bars
                            for item, count in top_sorted:
                                for i in range(count):
                                    color = get_item_color(item)
                                    if i == 0:
                                        visual_html.append(f'<div class="frequency-box" style="background-color: {color};">{item}</div>')
                                    else:
                                        visual_html.append(f'<div class="frequency-box" style="background-color: {color};"></div>')
                            
                            # Determinant
                            visual_html.append(f'<div class="display-box">{selected_determinant}</div>')
                            
                            # Bottom bars
                            for item, count in bottom_sorted:
                                for i in range(count):
                                    color = get_item_color(item)
                                    if i == 0:
                                        visual_html.append(f'<div class="frequency-box" style="background-color: {color};">{item}</div>')
                                    else:
                                        visual_html.append(f'<div class="frequency-box" style="background-color: {color};"></div>')
                            
                            visual_html.append('</div>')  # Close bars-column
                            visual_html.append('</div></div>')
                            
                            st.session_state.saved_visuals.append({
                                'html': ''.join(visual_html),
                                'type': analysis_type,
                                'determinant': selected_determinant,
                                'top_energy': selected_top.split(" [")[0],
                                'bottom_energy': selected_bottom.split(" [")[0]
                            })
                            st.success(f"Added {selected_determinant} analysis to suite!")
                            st.rerun()