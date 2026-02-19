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
    st.subheader("📊 Frequency Analysis")
    
    # Analysis type selector
    analysis_type = st.selectbox(
        "Select analysis type",
        options=[
            "🌍 Climate Frequency Analysis",
            "📏 Scale Frequency Analysis"
        ],
        key="analysis_type_selector"
    )
    
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
    
    # Create two columns: left for controls (30%), right for visualization (70%)
    left_col, right_col = st.columns([1, 2])
    
    with left_col:
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
    
    with right_col:
        # Visualization area
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
            
            # Build the visualization
            with right_col:
                # Define color function based on analysis type
                def get_item_color(item):
                    if "Climate" in analysis_type:
                        return get_climate_color(item)
                    else:  # Scale frequency
                        # Simple color mapping for scales
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
                        # Return color based on scale name or default gray
                        for key, color in scale_colors.items():
                            if key.lower() in str(item).lower():
                                return color
                        return '#9B9B9B'  # Default gray
                
                # Replace the CSS with this corrected version:

                st.markdown("""
                <style>
                    .viz-card {
                        background-color: transparent;
                        padding: 0 30px;  /* Add left and right padding here */
                        box-shadow: none;
                        display: block;  /* Changed from flex to block */
                        margin: 10px auto;
                        width: 100%;  /* Take full width of parent */
                        box-sizing: border-box;  /* Include padding in width */
                    }
                    .stack-container {
                        display: block;
                        flex-direction: column;
                        align-items: center;
                        width: 50%;
                        max-width: 260px;  /* Control the actual chart width */
                        margin: 0px auto;  /* Center the stack container */
                        padding: 0px;
                    }
                    .frequency-box {
                        width: 100%;
                        height: 28px;
                        margin: 0;
                        padding: 0 5px;
                        border: none;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        color: black;
                        font-size: 12px;
                        font-weight: bold;
                        box-sizing: border-box;
                    }
                    .display-box {
                        width: 100%;
                        height: 36px;
                        margin: 0;
                        padding: 0 5px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        font-weight: bold;
                        font-size: 14px;
                        background-color: white;
                        border-left: 1px solid #dee2e6;
                        border-right: 1px solid #dee2e6;
                        box-sizing: border-box;
                    }
                    .display-box.top {
                        border-top: 1px solid #dee2e6;
                        border-bottom: none;
                    }
                    .display-box.middle {
                        background-color: #f0f2f6;
                        border-top: 2px solid #000000;
                        border-bottom: 2px solid #000000;
                        border-left: 2px solid #000000;
                        border-right: 2px solid #000000;
                        font-weight: bold;
                    }
                    .display-box.bottom {
                        border-top: none;
                        border-bottom: 1px solid #dee2e6;
                    }
                    /* Remove any extra margins from Streamlit elements */
                    div[data-testid="stVerticalBlock"] > div {
                        padding: 0 !important;
                    }
                    .stMarkdown {
                        margin: 0 !important;
                    }
                </style>
                """, unsafe_allow_html=True)
                
                st.markdown('<div class="viz-card">', unsafe_allow_html=True)
                st.markdown('<div class="stack-container">', unsafe_allow_html=True)
                
                # TOP SECTION - Increase results
                if 'selected_top' in locals() and selected_top and selected_top != "-- Choose energy output --":
                    selected_top_energy = selected_top.split(" [")[0]
                    
                    # Filter records for top stack
                    top_items = []
                    for record in det_records:
                        if record.get('direction') == 'Increase':
                            method = record.get('energy_method', '').lower()
                            if selected_top_energy.lower() in method:
                                if "Climate" in analysis_type:
                                    item = record.get('climate')
                                else:  # Scale frequency
                                    item = record.get('scale')
                                
                                if item and item not in ['', None, 'Awaiting data']:
                                    # Clean item code
                                    item_clean = item
                                    if " - " in str(item):
                                        item_clean = item.split(" - ")[0]
                                    item_clean = ''.join([c for c in str(item_clean) if c.isalnum()])
                                    top_items.append(item_clean)
                    
                    if top_items:
                        top_counts = Counter(top_items)
                        top_sorted = sorted(top_counts.items(), key=lambda x: x[1], reverse=True)
                        
                        for item, count in top_sorted:
                            for i in range(count):
                                color = get_item_color(item)
                                if i == 0:
                                    st.markdown(f'<div class="frequency-box" style="background-color: {color};">{item}</div>', unsafe_allow_html=True)
                                else:
                                    st.markdown(f'<div class="frequency-box" style="background-color: {color};"></div>', unsafe_allow_html=True)
                
                # Top display box - Energy output increase
                if 'selected_top' in locals() and selected_top and selected_top != "-- Choose energy output --":
                    st.markdown(f'<div class="display-box top">↑ {selected_top.split(" [")[0]} (increase)</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="display-box top" style="color: #adb5bd;">↑ Energy output (increase)</div>', unsafe_allow_html=True)
                
                # Middle display box - Determinant
                st.markdown(f'<div class="display-box middle">{selected_determinant}</div>', unsafe_allow_html=True)
                
                # Bottom display box - Energy output decrease
                if 'selected_bottom' in locals() and selected_bottom and selected_bottom != "-- Choose energy output --":
                    st.markdown(f'<div class="display-box bottom">↓ {selected_bottom.split(" [")[0]} (decrease)</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="display-box bottom" style="color: #adb5bd;">↓ Energy output (decrease)</div>', unsafe_allow_html=True)
                
                # BOTTOM SECTION - Decrease results
                if 'selected_bottom' in locals() and selected_bottom and selected_bottom != "-- Choose energy output --":
                    selected_bottom_energy = selected_bottom.split(" [")[0]
                    
                    # Filter records for bottom stack
                    bottom_items = []
                    for record in det_records:
                        if record.get('direction') == 'Decrease':
                            method = record.get('energy_method', '').lower()
                            if selected_bottom_energy.lower() in method:
                                if "Climate" in analysis_type:
                                    item = record.get('climate')
                                else:  # Scale frequency
                                    item = record.get('scale')
                                
                                if item and item not in ['', None, 'Awaiting data']:
                                    # Clean item code
                                    item_clean = item
                                    if " - " in str(item):
                                        item_clean = item.split(" - ")[0]
                                    item_clean = ''.join([c for c in str(item_clean) if c.isalnum()])
                                    bottom_items.append(item_clean)
                    
                    if bottom_items:
                        bottom_counts = Counter(bottom_items)
                        bottom_sorted = sorted(bottom_counts.items(), key=lambda x: x[1], reverse=True)
                        
                        for item, count in bottom_sorted:
                            for i in range(count):
                                color = get_item_color(item)
                                if i == 0:
                                    st.markdown(f'<div class="frequency-box" style="background-color: {color};">{item}</div>', unsafe_allow_html=True)
                                else:
                                    st.markdown(f'<div class="frequency-box" style="background-color: {color};"></div>', unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)  # Close stack-container
                st.markdown('</div>', unsafe_allow_html=True)  # Close viz-card
                
                # Add button to save this visual
                if st.button("📸 Add to Analysis Suite", key="save_visual"):
                    if ('selected_top' in locals() and selected_top and selected_top != "-- Choose energy output --" and
                        'selected_bottom' in locals() and selected_bottom and selected_bottom != "-- Choose energy output --"):
                        
                        # Create a visual representation
                        visual_html = []
                        visual_html.append('<div class="viz-card" style="margin-bottom: 10px;">')
                        visual_html.append('<div class="stack-container">')
                        
                        # Add top items
                        if 'top_items' in locals() and top_items:
                            for item, count in top_sorted:
                                for i in range(count):
                                    color = get_item_color(item)
                                    if i == 0:
                                        visual_html.append(f'<div class="frequency-box" style="background-color: {color};">{item}</div>')
                                    else:
                                        visual_html.append(f'<div class="frequency-box" style="background-color: {color};"></div>')
                        
                        # Add display boxes
                        visual_html.append(f'<div class="display-box top">↑ {selected_top.split(" [")[0]} (increase)</div>')
                        visual_html.append(f'<div class="display-box middle">{selected_determinant}</div>')
                        visual_html.append(f'<div class="display-box bottom">↓ {selected_bottom.split(" [")[0]} (decrease)</div>')
                        
                        # Add bottom items
                        if 'bottom_items' in locals() and bottom_items:
                            for item, count in bottom_sorted:
                                for i in range(count):
                                    color = get_item_color(item)
                                    if i == 0:
                                        visual_html.append(f'<div class="frequency-box" style="background-color: {color};">{item}</div>')
                                    else:
                                        visual_html.append(f'<div class="frequency-box" style="background-color: {color};"></div>')
                        
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
    
    # Display saved visuals
    if st.session_state.saved_visuals:
        st.divider()
        st.subheader("📚 Your Analysis Suite")
        
        # Add clear all button
        if st.button("🗑️ Clear All", key="clear_all"):
            st.session_state.saved_visuals = []
            st.rerun()
        
        # Display saved visuals in a grid
        cols = st.columns(2)
        for i, visual in enumerate(st.session_state.saved_visuals):
            with cols[i % 2]:
                st.markdown(f"**{visual['type']}**: {visual['determinant']}", unsafe_allow_html=True)
                st.markdown(visual['html'], unsafe_allow_html=True)
                if st.button(f"❌ Remove", key=f"remove_{i}"):
                    st.session_state.saved_visuals.pop(i)
                    st.rerun()