# determinant_analysis.py
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from collections import Counter
import re
import base64
from color_schemes import (
    get_climate_color,
    get_scale_color,
    get_building_use_color,
    get_approach_color
)

# Module-level color function
def get_item_color(item, analysis_type):
    """Get color for item based on analysis type"""
    if "Climate" in analysis_type:
        return get_climate_color(item)
    elif "Scale" in analysis_type:
        return get_scale_color(item)
    elif "Building Use" in analysis_type:
        return get_building_use_color(item)
    else:  # Approach
        return get_approach_color(item)

if 'analyses_list' not in st.session_state:
    st.session_state.analyses_list = []
    
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
    st.subheader(" Moderator Analysis")
    
    # Initialize session state for storing multiple visuals
    if 'saved_visuals' not in st.session_state:
        st.session_state.saved_visuals = []
    
    # If user is logged in, load their saved analyses from database
    if st.session_state.get('logged_in') and st.session_state.get('user_id'):
        user_id = st.session_state.user_id
        saved = db_connection.get_user_analyses(user_id)
        # Convert to the format expected by the display code
        st.session_state.saved_visuals = []
        for item in saved:
            st.session_state.saved_visuals.append({
                'id': item['id'],  # store DB id for deletion
                'html': item['html'],
                'type': item['analysis_type'],
                'determinant': item['determinant'],
                'top_energy': item['top_energy'],
                'bottom_energy': item['bottom_energy']
            })
    else:
        # If not logged in, clear any previous session visuals
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
    
    # Create three columns: left for controls, middle for chart, right blank
    left_col, mid_col, right_col = st.columns([1, 1, 1])
    
    with left_col:
        # Analysis type selector
        analysis_type = st.selectbox(
            "Select moderator",
            options=[
                " Climate",
                " Scale", 
                " Building Use",
                " Approach"
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
                    # Calculate total increase count
                    total_increase = sum(increase_methods.values())
                    increase_options = [
                        "-- Choose energy output --",
                        f"✨ ALL ENERGY OUTPUTS (INCREASE) [{total_increase}]"
                    ] + [f"{m} [{c}]" for m, c in sorted(increase_methods.items(), key=lambda x: x[1], reverse=True)]
                    
                    selected_top = top_dropdown.selectbox(
                        "↑ Energy output (increase)",
                        options=increase_options,
                        key="top_energy_active"
                    )
                
                # Update bottom dropdown (now active)
                if decrease_methods:
                    # Calculate total decrease count
                    total_decrease = sum(decrease_methods.values())
                    decrease_options = [
                        "-- Choose energy output --",
                        f"✨ ALL ENERGY OUTPUTS (DECREASE) [{total_decrease}]"
                    ] + [f"{m} [{c}]" for m, c in sorted(decrease_methods.items(), key=lambda x: x[1], reverse=True)]
                    
                    selected_bottom = bottom_dropdown.selectbox(
                        "↓ Energy output (decrease)",
                        options=decrease_options,
                        key="bottom_energy_active"
                    )
        
        # Process top stack if selected
        if selected_determinant and selected_top and selected_top != "-- Choose energy output --":
            # Check if "ALL ENERGY OUTPUTS (INCREASE)" is selected
            if "ALL ENERGY OUTPUTS (INCREASE)" in selected_top:
                # Include ALL increase records regardless of energy output
                top_items = []
                for record in det_records:
                    if record.get('direction') == 'Increase':
                        if "Climate" in analysis_type:
                            item = record.get('climate')
                        elif "Scale" in analysis_type:
                            item = record.get('scale')
                        elif "Building Use" in analysis_type:
                            item = record.get('building_use')
                        else:  # Approach
                            item = record.get('approach')
                        
                        if item and item not in ['', None, 'Awaiting data']:
                            display_item = item
                            clean_item = item
                            if " - " in str(item):
                                clean_item = item.split(" - ")[0]
                            clean_item = clean_item.strip()
                            top_items.append({
                                'display': display_item,
                                'clean': clean_item
                            })
            else:
                # Filter for specific energy output
                selected_top_energy = selected_top.split(" [")[0]
                
                # Filter records for top stack
                top_items = []
                for record in det_records:
                    if record.get('direction') == 'Increase':
                        method = record.get('energy_method', '').lower()
                        if selected_top_energy.lower() in method:
                            if "Climate" in analysis_type:
                                item = record.get('climate')
                            elif "Scale" in analysis_type:
                                item = record.get('scale')
                            elif "Building Use" in analysis_type:
                                item = record.get('building_use')
                            else:  # Approach
                                item = record.get('approach')
                            
                            if item and item not in ['', None, 'Awaiting data']:
                                display_item = item
                                clean_item = item
                                if " - " in str(item):
                                    clean_item = item.split(" - ")[0]
                                clean_item = clean_item.strip()
                                top_items.append({
                                    'display': display_item,
                                    'clean': clean_item
                                })
            
            if top_items:
                # Count by clean version for grouping
                top_counts = {}
                for ti in top_items:
                    clean = ti['clean']
                    top_counts[clean] = top_counts.get(clean, 0) + 1
                
                # Create sorted list with display names
                top_sorted = []
                for clean, count in sorted(top_counts.items(), key=lambda x: x[1], reverse=True):
                    display = next((ti['display'] for ti in top_items if ti['clean'] == clean), clean)
                    top_sorted.append((display, count))
                
                top_height = sum(top_counts.values())
        
        # Process bottom stack if selected
        if selected_determinant and selected_bottom and selected_bottom != "-- Choose energy output --":
            # Check if "ALL ENERGY OUTPUTS (DECREASE)" is selected
            if "ALL ENERGY OUTPUTS (DECREASE)" in selected_bottom:
                # Include ALL decrease records regardless of energy output
                bottom_items = []
                for record in det_records:
                    if record.get('direction') == 'Decrease':
                        if "Climate" in analysis_type:
                            item = record.get('climate')
                        elif "Scale" in analysis_type:
                            item = record.get('scale')
                        elif "Building Use" in analysis_type:
                            item = record.get('building_use')
                        else:  # Approach
                            item = record.get('approach')
                        
                        if item and item not in ['', None, 'Awaiting data']:
                            display_item = item
                            clean_item = item
                            if " - " in str(item):
                                clean_item = item.split(" - ")[0]
                            clean_item = clean_item.strip()
                            bottom_items.append({
                                'display': display_item,
                                'clean': clean_item
                            })
            else:
                # Filter for specific energy output
                selected_bottom_energy = selected_bottom.split(" [")[0]
                
                bottom_items = []
                for record in det_records:
                    if record.get('direction') == 'Decrease':
                        method = record.get('energy_method', '').lower()
                        if selected_bottom_energy.lower() in method:
                            if "Climate" in analysis_type:
                                item = record.get('climate')
                            elif "Scale" in analysis_type:
                                item = record.get('scale')
                            elif "Building Use" in analysis_type:
                                item = record.get('building_use')
                            else:  # Approach
                                item = record.get('approach')
                            
                            if item and item not in ['', None, 'Awaiting data']:
                                display_item = item
                                clean_item = item
                                if " - " in str(item):
                                    clean_item = item.split(" - ")[0]
                                clean_item = clean_item.strip()
                                bottom_items.append({
                                    'display': display_item,
                                    'clean': clean_item
                                })
            
            if bottom_items:
                # Count by clean version for grouping
                bottom_counts = {}
                for bi in bottom_items:
                    clean = bi['clean']
                    bottom_counts[clean] = bottom_counts.get(clean, 0) + 1
                
                # Create sorted list with display names
                bottom_sorted = []
                for clean, count in sorted(bottom_counts.items(), key=lambda x: x[1], reverse=True):
                    display = next((bi['display'] for bi in bottom_items if bi['clean'] == clean), clean)
                    bottom_sorted.append((display, count))
                
                bottom_height = sum(bottom_counts.values())
        
        # CSS styles for consistent chart width
        st.markdown("""
        <style>
            .viz-card {
                background-color: transparent;
                padding: 0;
                box-shadow: none;
                display: block;
                margin: 10px auto;
                width: auto;
                box-sizing: border-box;
            }
            .stack-container {
                display: flex;
                flex-direction: row;
                align-items: stretch;
                width: auto;
                margin: 0 auto;
                padding: 0;
            }
            .bars-column {
                display: flex;
                flex-direction: column;
                flex: 1;
                width: auto;
            }
            .frequency-box {
                width: 100%;
                height: 28px;
                margin: 0;
                padding: 0 3px;
                border: 1px dashed rgba(0,0,0,0.3);
                display: flex;
                align-items: center;
                justify-content: center;
                color: black;
                font-size: 12px;
                font-weight: plain;
                box-sizing: border-box;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                border-bottom: 1px dashed rgba(0,0,0,0.3);
            }
            .frequency-box:last-child {
                border-bottom: 1px dashed rgba(0,0,0,0.3);
            }
            .frequency-box + .frequency-box {
                border-top: none;
            }
            .display-box {
                width: auto;
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
            .arrow-column {
                width: 60px;
                margin-right: 0;
            }
            .saved-chart {
                margin-bottom: 20px;
                page-break-inside: avoid;
            }
            .analysis-suite-header {
                margin-top: 40px;
                padding-top: 20px;
                border-top: 3px solid #e0e0e0;
            }
        </style>
        """, unsafe_allow_html=True)

        # Only render visualization if determinant is selected
        if selected_determinant:
            # Create a container for the chart with two columns
            chart_col1, chart_col2 = st.columns([6, 0.5])
            
            with chart_col1:
                # Bars column on the left
                st.markdown('<div class="bars-column">', unsafe_allow_html=True)
                
                # TOP SECTION - Increase results
                if top_items and selected_top:
                    for display_name, count in top_sorted:
                        for i in range(count):
                            color = get_item_color(display_name, analysis_type)
                            st.markdown(f'<div class="frequency-box" style="background-color: {color};">{display_name}</div>', unsafe_allow_html=True)
                else:
                    # Placeholder to maintain spacing
                    st.markdown('<div class="frequency-box" style="opacity:0;"></div>', unsafe_allow_html=True)
                
                # Middle display box (Determinant)
                st.markdown(f'<div class="display-box">{selected_determinant}</div>', unsafe_allow_html=True)

                # BOTTOM SECTION - Decrease results
                if bottom_items and selected_bottom:
                    for display_name, count in bottom_sorted:
                        for i in range(count):
                            color = get_item_color(display_name, analysis_type)
                            st.markdown(f'<div class="frequency-box" style="background-color: {color};">{display_name}</div>', unsafe_allow_html=True)
                else:
                    # Placeholder to maintain spacing
                    st.markdown('<div class="frequency-box" style="opacity:0;"></div>', unsafe_allow_html=True)

                with chart_col2:
                    # Arrow column on the right
                    st.markdown('<div style="display: flex; flex-direction: column; height: 100%; position: relative;">', unsafe_allow_html=True)
                    
                    # Calculate total stack heights
                    top_stack_height = top_height * 28 if top_height > 0 else 28
                    bottom_stack_height = bottom_height * 28 if bottom_height > 0 else 28
                    determinant_height = 36
                    
                    # Top arrow section
                    if top_height > 0 and selected_top:
                        # Get the display name for the energy output
                        if "ALL ENERGY OUTPUTS (INCREASE)" in selected_top:
                            energy_name = "All Increase"
                        else:
                            energy_name = selected_top.split(" [")[0]
                        
                        increase_count = top_height
                        text_length = len(energy_name) + len(f"(Increase) {increase_count}")
                        text_height = text_length * 11

                        st.markdown(f'''
                        <div style="position: relative; height: {top_stack_height}px; margin-bottom: 0; width: 60px;">
                            <div style="position: absolute; left: 10px; top: {top_stack_height}px; width: 3px; height: {top_stack_height}px; background-color: #e74c3c; transform: translateY(-100%);"></div>
                            <div style="position: absolute; left: 4px; top: 0; width: 0; height: 0; border-left: 8px solid transparent; border-right: 8px solid transparent; border-bottom: 14px solid #e74c3c;"></div>
                            <div style="position: absolute; left: 20px; bottom: 0; height: {max(top_stack_height, text_height)}px; display: flex; flex-direction: column; justify-content: flex-start; writing-mode: vertical-rl; text-orientation: mixed; transform: rotate(180deg); color: #e74c3c; white-space: nowrap;">
                                <div style="margin: 0;">{energy_name}</div>
                                <div style="margin-bottom: auto; opacity: 0.9;">Increase [{increase_count}]</div>
                            </div>
                        </div>
                        ''', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div style="height: 28px;"></div>', unsafe_allow_html=True)

                    # Determinant spacer
                    st.markdown(f'<div style="height: {determinant_height}px; width: 60px;"></div>', unsafe_allow_html=True)

                    # Bottom arrow section
                    if bottom_height > 0 and selected_bottom:
                        # Get the display name for the energy output
                        if "ALL ENERGY OUTPUTS (DECREASE)" in selected_bottom:
                            energy_name = "All Decrease"
                        else:
                            energy_name = selected_bottom.split(" [")[0]
                        
                        decrease_count = bottom_height
                        text_length = len(energy_name) + len(f"(Decrease) {decrease_count}")
                        text_height = text_length * 11
                                            
                        st.markdown(f'''
                        <div style="position: relative; height: {bottom_stack_height}px; margin-top: 0; width: 60px;">
                            <div style="position: absolute; left: 10px; top: 0; width: 3px; height: {bottom_stack_height}px; background-color: #3498db;"></div>
                            <div style="position: absolute; left: 4px; bottom: 0; width: 0; height: 0; border-left: 8px solid transparent; border-right: 8px solid transparent; border-top: 14px solid #3498db;"></div>
                            <div style="position: absolute; left: 20px; top: 0; height: {max(bottom_stack_height, text_height)}px; display: flex; flex-direction: column; justify-content: flex-start; writing-mode: vertical-rl; text-orientation: mixed; transform: rotate(180deg); color: #3498db; white-space: nowrap;">
                                <div style="margin-top: auto;">{energy_name}</div>
                                <div style="margin-top: auto; opacity: 0.9;">Decrease [{decrease_count}]</div>
                            </div>
                        </div>
                        ''', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div style="height: 28px;"></div>', unsafe_allow_html=True)

                    st.markdown('</div>', unsafe_allow_html=True)  # Close arrow column

                st.markdown('</div>', unsafe_allow_html=True)  # Close chart row

    # Add button to save this visual (in left column, below dropdowns)
    with left_col:
        if selected_determinant and selected_top and selected_bottom and selected_top != "-- Choose energy output --" and selected_bottom != "-- Choose energy output --":
            if st.session_state.get('logged_in', False):
                # Create two columns for Save and Export buttons
                col_save, col_export, _ = st.columns([1, 1, 1])
                
                with col_save:
                    if st.button("💾 Save to Collection", key="save_visual", use_container_width=True):
                        if top_items and bottom_items:
                            # Outer container – full width
                            visual_html = ['<div style="width: 100%; margin-bottom: 0;">']
                            
                            # Flex row for chart
                            visual_html.append('<div style="display: flex; flex-direction: row; align-items: stretch; width: 100%;">')
                            
                            # LEFT COLUMN - Bars (flex-grow)
                            visual_html.append('<div style="flex: 1; min-width: 0;">')
                            
                            # Top bars
                            for display_name, count in top_sorted:
                                for i in range(count):
                                    color = get_item_color(display_name, analysis_type)
                                    visual_html.append(f'<div style="width: 100%; height: 28px; background-color: {color}; display: flex; align-items: center; justify-content: center; color: black; font-size: 12px; border: 1px dashed rgba(0,0,0,0.3); box-sizing: border-box;">{display_name}</div>')
                            
                            # Determinant box
                            visual_html.append(f'<div style="width: 100%; height: 36px; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 13px; background-color: #f0f2f6; border: 2px solid #000000; box-sizing: border-box;">{selected_determinant}</div>')
                            
                            # Bottom bars
                            for display_name, count in bottom_sorted:
                                for i in range(count):
                                    color = get_item_color(display_name, analysis_type)
                                    visual_html.append(f'<div style="width: 100%; height: 28px; background-color: {color}; display: flex; align-items: center; justify-content: center; color: black; font-size: 12px; border: 1px dashed rgba(0,0,0,0.3); box-sizing: border-box;">{display_name}</div>')
                            
                            visual_html.append('</div>')  # Close left column
                            
                            # RIGHT COLUMN - Arrows (fixed width 60px)
                            visual_html.append('<div style="width: 60px; position: relative;">')
                            
                            # Top arrow section
                            top_stack_height = top_height * 28
                            
                            # Get the display name for the energy output
                            if "ALL ENERGY OUTPUTS (INCREASE)" in selected_top:
                                energy_name_top = "All Increase"
                            else:
                                energy_name_top = selected_top.split(" [")[0]
                            
                            increase_count = top_height
                            text_length_top = len(energy_name_top) + len(f"(Increase) {increase_count}")
                            text_height_top = text_length_top * 11

                            visual_html.append(f'''
                            <div style="position: relative; height: {top_stack_height}px; width: 60px; margin-bottom: 0;">
                                <div style="position: absolute; left: 10px; top: {top_stack_height}px; width: 3px; height: {top_stack_height}px; background-color: #e74c3c; transform: translateY(-100%);"></div>
                                <div style="position: absolute; left: 4px; top: 0; width: 0; height: 0; border-left: 8px solid transparent; border-right: 8px solid transparent; border-bottom: 14px solid #e74c3c;"></div>
                                <div style="position: absolute; left: 20px; bottom: 0; height: {max(top_stack_height, text_height_top)}px; display: flex; flex-direction: column; justify-content: flex-start; writing-mode: vertical-rl; text-orientation: mixed; transform: rotate(180deg); color: #e74c3c; white-space: nowrap; line-height: 1.2;">
                                    <div style="margin: 0;">{energy_name_top}</div>
                                    <div style="margin-bottom: auto; opacity: 0.9;">Increase [{increase_count}]</div>
                                </div>
                            </div>
                            ''')
                            
                            # Determinant spacer
                            visual_html.append('<div style="height: 36px; width: 60px;"></div>')
                            
                            # Bottom arrow section
                            bottom_stack_height = bottom_height * 28
                            
                            # Get the display name for the energy output
                            if "ALL ENERGY OUTPUTS (DECREASE)" in selected_bottom:
                                energy_name_bottom = "All Decrease"
                            else:
                                energy_name_bottom = selected_bottom.split(" [")[0]
                            
                            decrease_count = bottom_height
                            text_length_bottom = len(energy_name_bottom) + len(f"(Decrease) {decrease_count}")
                            text_height_bottom = text_length_bottom * 11
                                                
                            visual_html.append(f'''
                            <div style="position: relative; height: {bottom_stack_height}px; width: 60px; margin-top: 0;">
                                <div style="position: absolute; left: 10px; top: 0; width: 3px; height: {bottom_stack_height}px; background-color: #3498db;"></div>
                                <div style="position: absolute; left: 4px; bottom: 0; width: 0; height: 0; border-left: 8px solid transparent; border-right: 8px solid transparent; border-top: 14px solid #3498db;"></div>
                                <div style="position: absolute; left: 20px; top: 0; height: {max(bottom_stack_height, text_height_bottom)}px; display: flex; flex-direction: column; justify-content: flex-start; writing-mode: vertical-rl; text-orientation: mixed; transform: rotate(180deg); color: #3498db; white-space: nowrap; line-height: 1.2;">
                                    <div style="margin-top: auto;">{energy_name_bottom}</div>
                                    <div style="margin-top: auto; opacity: 0.9;">Decrease [{decrease_count}]</div>
                                </div>
                            </div>
                            ''')
                            
                            visual_html.append('</div>')  # Close right column
                            visual_html.append('</div>')  # Close flex row
                            
                            visual_html.append('</div>')  # Close outer container - NO LEGEND
                            
                            # Get user_id
                            user_id = st.session_state.user_id
                            
                            # Save to database WITHOUT svg parameter
                            result = db_connection.save_analysis(
                                user_id=user_id,
                                analysis_type=analysis_type,
                                determinant=selected_determinant,
                                top_energy=selected_top,
                                bottom_energy=selected_bottom,
                                html=''.join(visual_html)
                            )
                                            
                            # Add to session state with ALL the data needed for SVG generation
                            new_item = {
                                'id': result[0]['id'] if db_connection.use_supabase else result,
                                'html': ''.join(visual_html),
                                'type': analysis_type,
                                'determinant': selected_determinant,
                                'top_energy': selected_top,
                                'bottom_energy': selected_bottom,
                                # Store the raw data needed for SVG generation
                                'top_sorted': top_sorted.copy(),
                                'bottom_sorted': bottom_sorted.copy(),
                                'top_height': top_height,
                                'bottom_height': bottom_height,
                                'analysis_type': analysis_type
                            }
                            
                            # Use a unique key approach to avoid duplication
                            if 'saved_visuals' not in st.session_state:
                                st.session_state.saved_visuals = []
                            
                            # Check if already exists to avoid duplicates
                            exists = False
                            for existing in st.session_state.saved_visuals:
                                if existing.get('id') == new_item['id']:
                                    exists = True
                                    break
                            
                            if not exists:
                                st.session_state.saved_visuals.append(new_item)
                                st.success(f"✅ Added {selected_determinant} analysis to collection")
                            else:
                                st.info("This analysis is already in your collection")
                            
                            st.rerun()
                
                with col_export:
                    if st.button("📥 Export SVG", key="export_current_svg", use_container_width=True):
                        # Generate SVG using current data
                        svg_content = generate_analysis_svg(
                            determinant=selected_determinant,
                            analysis_type=analysis_type,
                            top_sorted=top_sorted,
                            bottom_sorted=bottom_sorted,
                            top_height=top_height,
                            bottom_height=bottom_height,
                            selected_top=selected_top,
                            selected_bottom=selected_bottom
                        )
                        
                        # Download SVG
                        b64 = base64.b64encode(svg_content.encode()).decode()
                        filename = f"{selected_determinant}_{analysis_type.strip()}_Analysis.svg".replace(' ', '_')
                        
                        st.markdown(f'''
                        <div style="padding: 10px; background-color: #f0f2f6; border-radius: 5px; margin: 10px 0;">
                            <a href="data:image/svg+xml;base64,{b64}" download="{filename}" 
                               style="background-color: #4CAF50; color: white; padding: 8px 16px; 
                                      text-decoration: none; border-radius: 4px; display: inline-block;">
                                📥 Click to save {filename}
                            </a>
                        </div>
                        ''', unsafe_allow_html=True)
            else:
                # For non-logged in users, just show export button
                if st.button("📥 Export SVG", key="export_current_svg", use_container_width=True):
                    if top_items and bottom_items:
                        svg_content = generate_analysis_svg(
                            determinant=selected_determinant,
                            analysis_type=analysis_type,
                            top_sorted=top_sorted,
                            bottom_sorted=bottom_sorted,
                            top_height=top_height,
                            bottom_height=bottom_height,
                            selected_top=selected_top,
                            selected_bottom=selected_bottom
                        )
                        
                        b64 = base64.b64encode(svg_content.encode()).decode()
                        filename = f"{selected_determinant}_{analysis_type.strip()}_Analysis.svg".replace(' ', '_')
                        
                        st.markdown(f'''
                        <div style="padding: 10px; background-color: #f0f2f6; border-radius: 5px; margin: 10px 0;">
                            <a href="data:image/svg+xml;base64,{b64}" download="{filename}" 
                               style="background-color: #4CAF50; color: white; padding: 8px 16px; 
                                      text-decoration: none; border-radius: 4px; display: inline-block;">
                                📥 Click to save {filename}
                            </a>
                        </div>
                        ''', unsafe_allow_html=True)

    # ANALYSIS SUITE SECTION
    if st.session_state.saved_visuals:
        st.markdown('<div class="analysis-suite-header"></div>', unsafe_allow_html=True)
        st.subheader("Your Analysis Collection")
        
        # Export All and Clear All buttons
        col_export_all, col_clear, _ = st.columns([1, 1, 4])
        
        with col_export_all:
            if st.button("📥 Export All as HTML", key="export_all_analyses", use_container_width=True):
                # Generate a combined HTML file with all analyses
                all_charts_html = '<html><head><title>Analysis Collection</title></head><body style="font-family: Arial, sans-serif;">'
                all_charts_html += '<h1 style="text-align: center;">Analysis Collection</h1>'
                
                for i, visual in enumerate(st.session_state.saved_visuals):
                    all_charts_html += f'<h2>Analysis {i+1}: {visual["determinant"]} - {visual["type"].strip()}</h2>'
                    all_charts_html += visual['html']
                    if i < len(st.session_state.saved_visuals) - 1:
                        all_charts_html += '<hr style="margin: 40px 0; border: 1px dashed #ccc;">'
                
                all_charts_html += '</body></html>'
                
                # Download combined HTML
                b64 = base64.b64encode(all_charts_html.encode()).decode()
                filename = "Analysis_Collection.html"
                
                st.markdown(f'''
                <div style="padding: 10px; background-color: #f0f2f6; border-radius: 5px; margin: 10px 0;">
                    <p style="margin-bottom: 10px; font-weight: bold;">✅ Combined HTML Ready for Download:</p>
                    <a href="data:text/html;charset=utf-8;base64,{b64}" download="{filename}" 
                       style="background-color: #4CAF50; color: white; padding: 8px 16px; 
                              text-decoration: none; border-radius: 4px; display: inline-block;">
                        📥 Click here to save {filename}
                    </a>
                    <p style="margin-top: 8px; font-size: 12px; color: #666;">
                        Contains all {len(st.session_state.saved_visuals)} analyses in one HTML file.
                    </p>
                </div>
                ''', unsafe_allow_html=True)
        
        with col_clear:
            if st.button("🗑️ Clear All", key="clear_all_suite", use_container_width=True):
                # Delete all from database first
                if st.session_state.get('logged_in') and st.session_state.get('user_id'):
                    for visual in st.session_state.saved_visuals:
                        try:
                            db_connection.delete_analysis(visual['id'])
                        except:
                            pass
                # Clear session state
                st.session_state.saved_visuals = []
                st.rerun()
        
        # Display each saved visual with generous spacing
        for i, visual in enumerate(st.session_state.saved_visuals):
            # Add top spacing for all but first item
            if i > 0:
                st.markdown('<div style="margin-top: 40px;"></div>', unsafe_allow_html=True)
            
            # First row: Controls and Export SVG button
            colA, colB, colC, colD = st.columns([1, 1.5, 1.5, 2])
            
            with colA:
                if st.button(f"❌ Remove", key=f"remove_saved_{i}", use_container_width=True):
                    # Delete from database
                    try:
                        db_connection.delete_analysis(visual['id'])
                    except:
                        pass
                    # Remove from session state
                    st.session_state.saved_visuals.pop(i)
                    st.rerun()
            
            with colB:
                st.markdown(f"**Analysis {i+1}:**")
            
            with colC:
                st.markdown(f"{visual['determinant']} - {visual['type'].strip()}")
            
            with colD:
                if st.button(f"📥 Export SVG", key=f"export_svg_{i}", use_container_width=True):
                    # Create SVG from the HTML content
                    # Extract the chart parts from the HTML
                    svg_content = convert_html_to_svg(visual['html'], visual['determinant'], visual['type'])
                    
                    # Download individual SVG
                    b64 = base64.b64encode(svg_content.encode()).decode()
                    filename = f"Analysis_{i+1}_{visual['determinant']}.svg".replace(' ', '_')
                    
                    st.markdown(f'''
                    <div style="padding: 5px; background-color: #f0f2f6; border-radius: 5px; margin: 5px 0;">
                        <a href="data:image/svg+xml;base64,{b64}" download="{filename}" 
                           style="background-color: #4CAF50; color: white; padding: 4px 8px; 
                                  text-decoration: none; border-radius: 4px; display: inline-block; font-size: 12px;">
                            📥 Save {filename}
                        </a>
                    </div>
                    ''', unsafe_allow_html=True)
            
            # Add small spacing before chart
            st.markdown('<div style="margin-top: 10px;"></div>', unsafe_allow_html=True)
            
            # Chart with specified proportions
            chart_spacer1, chart_main, chart_spacer2 = st.columns([1, 1.25, 1])
            
            with chart_main:
                st.markdown(visual['html'], unsafe_allow_html=True)
            
            # Add extra bottom spacing to prevent clash with next item
            st.markdown('<div style="margin-bottom: 120px;"></div>', unsafe_allow_html=True)
            
            # Divider with extra spacing
            if i < len(st.session_state.saved_visuals) - 1:
                st.divider()
                st.markdown('<div style="margin-top: 30px;"></div>', unsafe_allow_html=True)


def convert_html_to_svg(html_content, determinant, analysis_type):
    """Convert HTML chart to SVG format"""
    import re
    
    # Extract colors and text from the HTML
    # This is a simplified conversion - you may need to adjust based on your HTML structure
    
    # Find all frequency boxes (the colored bars)
    box_pattern = r'<div class="frequency-box" style="background-color: (.*?);">(.*?)</div>'
    boxes = re.findall(box_pattern, html_content, re.DOTALL)
    
    # Find determinant box
    det_pattern = r'<div class="display-box">(.*?)</div>'
    determinant_text = re.findall(det_pattern, html_content, re.DOTALL)
    
    # Calculate dimensions
    bar_height = 28
    determinant_height = 36
    num_top_boxes = 0
    num_bottom_boxes = 0
    in_top_section = True
    
    # Count boxes to determine heights
    for color, text in boxes:
        if text.strip() == determinant_text[0] if determinant_text else "":
            in_top_section = False
            continue
        if in_top_section:
            num_top_boxes += 1
        else:
            num_bottom_boxes += 1
    
    top_stack_height = num_top_boxes * bar_height
    bottom_stack_height = num_bottom_boxes * bar_height
    total_height = top_stack_height + determinant_height + bottom_stack_height + 100
    
    # Start building SVG
    svg = [f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="800" height="{total_height}" xmlns="http://www.w3.org/2000/svg">
    <style>
        .bar-label {{ font-family: Arial; font-size: 12px; }}
        .display-box {{ font-family: Arial; font-size: 13px; font-weight: bold; }}
    </style>
''']
    
    y_pos = 50
    
    # Add top bars
    in_top = True
    for color, text in boxes:
        if text.strip() == determinant_text[0] if determinant_text else "":
            in_top = False
            continue
        
        if in_top:
            # Clean color string
            color = color.strip()
            svg.append(f'    <rect x="50" y="{y_pos}" width="500" height="{bar_height}" fill="{color}" rx="4" ry="4" />')
            # Determine text color based on background
            text_color = "white" if color in ['#105e8d', '#2470a0', '#3882b3', '#4c94c6', '#FF4444', '#44AA44', '#4444FF'] else "black"
            svg.append(f'    <text x="55" y="{y_pos + 18}" class="bar-label" fill="{text_color}">{text.strip()}</text>')
            y_pos += bar_height
    
    # Add determinant box
    if determinant_text:
        svg.append(f'    <rect x="50" y="{y_pos}" width="500" height="{determinant_height}" fill="#f0f2f6" stroke="black" stroke-width="2" rx="4" ry="4" />')
        svg.append(f'    <text x="55" y="{y_pos + 23}" class="display-box" fill="black">{determinant_text[0].strip()}</text>')
        y_pos += determinant_height
    
    # Add bottom bars
    for color, text in boxes:
        if text.strip() != determinant_text[0] if determinant_text else "":
            color = color.strip()
            svg.append(f'    <rect x="50" y="{y_pos}" width="500" height="{bar_height}" fill="{color}" rx="4" ry="4" />')
            text_color = "white" if color in ['#105e8d', '#2470a0', '#3882b3', '#4c94c6', '#FF4444', '#44AA44', '#4444FF'] else "black"
            svg.append(f'    <text x="55" y="{y_pos + 18}" class="bar-label" fill="{text_color}">{text.strip()}</text>')
            y_pos += bar_height
    
    # Extract arrow information from HTML (simplified - you may need to parse the arrow section)
    # This is a placeholder - you might want to extract the actual arrow text from the HTML
    arrow_x = 600
    
    # Add placeholder arrows (you may want to parse these from the HTML)
    if top_stack_height > 0:
        svg.append(f'    <line x1="{arrow_x+10}" y1="50" x2="{arrow_x+10}" y2="{50 + top_stack_height}" stroke="#e74c3c" stroke-width="3" />')
        svg.append(f'    <polygon points="{arrow_x+4},50 {arrow_x+16},50 {arrow_x+10},36" fill="#e74c3c" />')
    
    if bottom_stack_height > 0:
        bottom_start = 50 + top_stack_height + determinant_height
        svg.append(f'    <line x1="{arrow_x+10}" y1="{bottom_start}" x2="{arrow_x+10}" y2="{bottom_start + bottom_stack_height}" stroke="#3498db" stroke-width="3" />')
        svg.append(f'    <polygon points="{arrow_x+4},{bottom_start + bottom_stack_height} {arrow_x+16},{bottom_start + bottom_stack_height} {arrow_x+10},{bottom_start + bottom_stack_height+14}" fill="#3498db" />')
    
    svg.append('</svg>')
    return '\n'.join(svg)


def generate_analysis_svg(determinant, analysis_type, top_sorted, bottom_sorted, top_height, bottom_height, selected_top, selected_bottom):
    """Generate SVG version of the analysis chart matching HTML display"""
    
    # Calculate dimensions
    bar_height = 28
    determinant_height = 36
    top_stack_height = top_height * bar_height
    bottom_stack_height = bottom_height * bar_height
    total_height = top_stack_height + determinant_height + bottom_stack_height + 100
    
    # Get the display names for energy outputs
    if "ALL ENERGY OUTPUTS (INCREASE)" in selected_top:
        energy_name_top = "All Increase"
        top_display = "All Increase"
    else:
        energy_name_top = selected_top.split(" [")[0]
        top_display = energy_name_top
    
    if "ALL ENERGY OUTPUTS (DECREASE)" in selected_bottom:
        energy_name_bottom = "All Decrease"
        bottom_display = "All Decrease"
    else:
        energy_name_bottom = selected_bottom.split(" [")[0]
        bottom_display = energy_name_bottom
    
    svg = [f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="800" height="{total_height}" xmlns="http://www.w3.org/2000/svg">
    <style>
        .bar-label {{ font-family: Arial; font-size: 12px; text-anchor: middle; dominant-baseline: middle; }}
        .display-box {{ font-family: Arial; font-size: 13px; font-weight: bold; text-anchor: middle; dominant-baseline: middle; }}
        .arrow-text {{ font-family: Arial; font-size: 14px; fill: white; font-weight: bold; }}
    </style>
''']
    
    y_pos = 50
    
    # Top bars - NO ROUNDING
    if top_sorted:
        for display_name, count in top_sorted:
            for i in range(count):
                color = get_item_color(display_name, analysis_type)
                # Draw bar with no rounding
                svg.append(f'    <rect x="50" y="{y_pos}" width="500" height="{bar_height}" fill="{color}" rx="0" ry="0" />')
                # Add dashed border with no rounding
                svg.append(f'    <rect x="50" y="{y_pos}" width="500" height="{bar_height}" fill="none" stroke="rgba(0,0,0,0.3)" stroke-width="1" stroke-dasharray="5,5" rx="0" ry="0" />')
                # Centered text
                svg.append(f'    <text x="300" y="{y_pos + bar_height/2 + 1}" class="bar-label" fill="black">{display_name}</text>')
                y_pos += bar_height
    
    # Determinant box - keep rounded corners as original
    svg.append(f'    <rect x="50" y="{y_pos}" width="500" height="{determinant_height}" fill="#f0f2f6" stroke="black" stroke-width="2" rx="0" ry="0" />')
    svg.append(f'    <text x="300" y="{y_pos + determinant_height/2 + 1}" class="display-box" fill="black">{determinant}</text>')
    y_pos += determinant_height
    
    # Bottom bars - NO ROUNDING
    if bottom_sorted:
        for display_name, count in bottom_sorted:
            for i in range(count):
                color = get_item_color(display_name, analysis_type)
                # Draw bar with no rounding
                svg.append(f'    <rect x="50" y="{y_pos}" width="500" height="{bar_height}" fill="{color}" rx="0" ry="0" />')
                # Add dashed border with no rounding
                svg.append(f'    <rect x="50" y="{y_pos}" width="500" height="{bar_height}" fill="none" stroke="rgba(0,0,0,0.3)" stroke-width="1" stroke-dasharray="5,5" rx="0" ry="0" />')
                # Centered text
                svg.append(f'    <text x="300" y="{y_pos + bar_height/2 + 1}" class="bar-label" fill="black">{display_name}</text>')
                y_pos += bar_height
    
    # Add arrows on the right with labels
    arrow_x = 600
    
    # Top arrow section (180° rotation - reads bottom to top)
    if top_height > 0:
        arrow_top_start = 50
        arrow_top_end = 50 + top_stack_height
        arrow_mid = (arrow_top_start + arrow_top_end) / 2
        
        # Vertical line
        svg.append(f'    <line x1="{arrow_x+10}" y1="{arrow_top_start}" x2="{arrow_x+10}" y2="{arrow_top_end}" stroke="#e74c3c" stroke-width="3" />')
        # Arrow head at top
        svg.append(f'    <polygon points="{arrow_x+4},{arrow_top_start} {arrow_x+16},{arrow_top_start} {arrow_x+10},{arrow_top_start-14}" fill="#e74c3c" />')
        
        # Add text vertically - rotated -90° (reads bottom to top)
        text_x = arrow_x + 35
        svg.append(f'''    <g transform="rotate(-90, {text_x}, {arrow_mid})">
            <text x="{text_x}" y="{arrow_mid}" font-family="Arial" font-size="14" fill="#e74c3c" text-anchor="right" dominant-baseline="middle" font-weight="regular">
                <tspan x="{text_x}" dy="-0.8em">{top_display}</tspan>
                <tspan x="{text_x}" dy="1.4em">Increase [{top_height}]</tspan>
            </text>
        </g>''')

        # Bottom arrow section (rotate 90° - reads top to bottom)
        if bottom_height > 0:
            bottom_start = 50 + top_stack_height + determinant_height
            bottom_end = bottom_start + bottom_stack_height
            bottom_mid = (bottom_start + bottom_end) / 2
            
            # Vertical line
            svg.append(f'    <line x1="{arrow_x+10}" y1="{bottom_start}" x2="{arrow_x+10}" y2="{bottom_end}" stroke="#3498db" stroke-width="3" />')
            # Arrow head at bottom
            svg.append(f'    <polygon points="{arrow_x+4},{bottom_end} {arrow_x+16},{bottom_end} {arrow_x+10},{bottom_end+14}" fill="#3498db" />')
            
            # Add text vertically - rotate 90° (reads top to bottom)
            text_x = arrow_x + 35
            svg.append(f'''    <g transform="rotate(-90, {text_x}, {bottom_mid})">
                <text x="{text_x}" y="{bottom_mid}" font-family="Arial" font-size="14" fill="#3498db" text-anchor="left" dominant-baseline="middle" font-weight="regular">
                    <tspan x="{text_x}" dy="-0.8em">{bottom_display}</tspan>
                    <tspan x="{text_x}" dy="1.4em">Decrease [{bottom_height}]</tspan>
                </text>
            </g>''')
    
    svg.append('</svg>')
    return '\n'.join(svg)