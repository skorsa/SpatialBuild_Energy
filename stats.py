# stats.py
import streamlit as st
from sanitize_metadata_text import sanitize_metadata_text
from color_schemes import (
    get_climate_color,
    get_scale_color,
    get_building_use_color,
    get_approach_color,
    climate_descriptions
)

def render_statistics_tab(db_connection):
    """Render the Statistics tab with all Frequencys"""
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
    
   
    
    # Create tabs for different Frequencies
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
    
def render_determinant_chart(unique_studies):
    """Render top determinants chart with toggle and SVG export"""
    st.subheader("Top 10 Studied Determinants")
    
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
            chart_title = "All Determinants Frequency"
            filename = "All_Determinants_Chart"
        else:
            display_determinants = sorted(determinant_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            button_label = " Show All Determinants"
            chart_title = "Top 10 Determinants"
            filename = "Top_10_Determinants_Chart"
        
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
        with col1:
            if st.button(button_label, key="toggle_determinants_btn", use_container_width=True):
                st.session_state.show_all_determinants_stats = not st.session_state.show_all_determinants_stats
                st.rerun()
        
        # Show count info
        if st.session_state.show_all_determinants_stats:
            st.caption(f"Showing all {len(determinant_counts)} determinants")
        else:
            st.caption(f"Showing top 10 of {len(determinant_counts)} total determinants")
        
        # SVG export button below the chart
        st.markdown("---")
        col1, col2 = st.columns([1, 5])
        
        with col1:
            if st.button("📥 Export as SVG", key=f"export_svg_determinants_{filename}"):
                # Generate SVG
                svg_height = len(display_determinants) * 48 + 80  # 48px per bar + header
                svg_width = 900
                
                svg_content = [f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{svg_width}" height="{svg_height}" xmlns="http://www.w3.org/2000/svg">
    <style>
        .title {{ font-family: Arial; font-size: 16px; font-weight: bold; fill: #333; }}
        .bar-label {{ font-family: Arial; font-size: 12px; fill: #555; }}
        .count-label {{ font-family: Arial; font-size: 12px; font-weight: bold; fill: #333; }}
        .caption {{ font-family: Arial; font-size: 11px; fill: #888; }}
    </style>
    
    <!-- Chart Title -->
    <text x="10" y="30" class="title">{chart_title}</text>
''']
                
                y_position = 60
                for criteria, count in display_determinants:
                    # Truncate long text for SVG
                    display_text = criteria
                    if len(display_text) > 40:
                        display_text = display_text[:37] + "..."
                    
                    width_percent = (count / max_count) * 100
                    bar_width = (width_percent / 100) * 500  # Max bar width 500px
                    
                    # Add text label
                    svg_content.append(f'    <text x="10" y="{y_position + 16}" class="bar-label">{display_text}</text>')
                    
                    # Add bar
                    svg_content.append(f'    <rect x="250" y="{y_position + 5}" width="{bar_width}" height="24" fill="#95a5a6" rx="4" ry="4" />')
                    
                    # Add count
                    svg_content.append(f'    <text x="770" y="{y_position + 24}" class="count-label">{count}</text>')
                    
                    y_position += 48
                
                # Add caption
                total_studies = sum(count for _, count in determinant_counts.items())
                caption_text = f"Total determinants: {len(determinant_counts)} | Total studies: {total_studies}"
                if not st.session_state.show_all_determinants_stats:
                    caption_text = f"Showing top 10 of {len(determinant_counts)} determinants | Total studies: {total_studies}"
                
                svg_content.append(f'    <text x="10" y="{y_position + 20}" class="caption">{caption_text}</text>')
                svg_content.append('</svg>')
                
                svg_string = '\n'.join(svg_content)
                
                # SVG download
                import base64
                b64 = base64.b64encode(svg_string.encode()).decode()
                svg_filename = f"{filename}.svg"
                
                # Create visible download link
                st.markdown(f'''
                <div style="padding: 10px; background-color: #f0f2f6; border-radius: 5px; margin: 10px 0;">
                    <p style="margin-bottom: 10px; font-weight: bold;">✅ SVG Ready for Download:</p>
                    <a href="data:image/svg+xml;base64,{b64}" download="{svg_filename}" 
                       style="background-color: #4CAF50; color: white; padding: 8px 16px; 
                              text-decoration: none; border-radius: 4px; display: inline-block;">
                        📥 Click here to save {svg_filename}
                    </a>
                    <p style="margin-top: 8px; font-size: 12px; color: #666;">
                        If download doesn't start automatically, click the button above.
                    </p>
                </div>
                ''', unsafe_allow_html=True)
                
                # Auto-download via JavaScript
                st.markdown(f'''
                <script>
                    setTimeout(function() {{
                        const link = document.createElement('a');
                        link.href = 'data:image/svg+xml;base64,{b64}';
                        link.download = '{svg_filename}';
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);
                    }}, 500);
                </script>
                ''', unsafe_allow_html=True)
                
                st.success(f"✅ {svg_filename} ready for download!")
    else:
        st.info("No determinant data available")

def render_climate_distribution(unique_studies):
    """Render climate code distribution with clean bars - code on bar, description on left"""
    st.subheader("Climate Code Distribution (by unique study)")
    
    # Count climates by UNIQUE STUDY
    climate_counts = {}
    climate_display_map = {}  # Map code to full display with description
    for study in unique_studies:
        climate = study.get('climate')
        if climate and climate not in ['Awaiting data', '']:
            # Extract the climate code
            climate_code = climate
            if " - " in str(climate):
                climate_code = climate.split(" - ")[0]
            climate_code = ''.join([c for c in str(climate_code) if c.isalnum()])
            climate_counts[climate_code] = climate_counts.get(climate_code, 0) + 1
            
            # Store the description for this code
            if climate_code not in climate_display_map:
                description = climate_descriptions.get(climate_code, '')
                if description:
                    climate_display_map[climate_code] = description
                else:
                    climate_display_map[climate_code] = climate_code
    
    if climate_counts:
        sorted_items = sorted(climate_counts.items(), key=lambda x: x[1], reverse=True)
        max_count = max(count for _, count in sorted_items)
        
        # Calculate minimum width to accommodate 3-letter code (approx 30px)
        MIN_BAR_WIDTH_PX = 40
        MAX_BAR_WIDTH_PX = 500
        
        for climate_code, count in sorted_items:
            # Get the description for the left column
            description = climate_display_map.get(climate_code, climate_code)
            
            color = get_climate_color(climate_code)
            
            # Calculate width percentage with minimum to show the code
            width_percent = (count / max_count) * 100
            # Ensure minimum width for the bar to show the code
            min_width_percent = (MIN_BAR_WIDTH_PX / MAX_BAR_WIDTH_PX) * 100
            display_width_percent = max(width_percent, min_width_percent)
            
            col_desc, col_bar = st.columns([1.5, 3])
            
            with col_desc:
                desc_html = f'''
                <div style="display: flex; align-items: center; height: 32px; margin: 2px 0;">
                    <span style="font-style: italic; color: #555; font-size: 0.9em;">{description}</span>
                </div>
                '''
                st.markdown(desc_html, unsafe_allow_html=True)
            
            with col_bar:
                bar_html = f'''
                <div style="display: flex; align-items: center; margin: 2px 0; width: 100%; height: 32px; position: relative;">
                    <div style="
                        width: {display_width_percent}%;
                        background-color: {color};
                        height: 24px;
                        border-radius: 4px;
                        display: flex;
                        align-items: center;
                        padding-left: 8px;
                        box-sizing: border-box;
                        overflow: hidden;
                        white-space: nowrap;
                        color: {'white' if color in ['#105e8d', '#2470a0', '#3882b3', '#4c94c6', '#FF4444', '#44AA44', '#4444FF'] else 'black'};
                        font-weight: normal;
                        font-size: 12px;
                    ">{climate_code}</div>
                    <div style="margin-left: 10px; font-weight: 500; color: #333; min-width: 30px;">
                        {count}
                    </div>
                </div>
                '''
                st.markdown(bar_html, unsafe_allow_html=True)
        
        st.caption(f"Total studies with data: {sum(climate_counts.values())}")
        
        # Export button (simplified version)
        st.markdown("---")
        col1, col2 = st.columns([1, 5])
        
        with col1:
            if st.button("📥 Export as SVG", key=f"export_svg_climate_{hash(str(sorted_items))}"):
                # Generate SVG with the same visual style
                svg_height = len(sorted_items) * 40 + 80
                svg_width = 900
                
                svg_content = [f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{svg_width}" height="{svg_height}" xmlns="http://www.w3.org/2000/svg">
    <style>
        .title {{ font-family: Arial; font-size: 16px; font-weight: bold; fill: #333; }}
        .desc-label {{ font-family: Arial; font-size: 12px; fill: #555; font-style: italic; }}
        .bar-text {{ font-family: Arial; font-size: 12px; font-weight: normal; fill: white; }}
        .count-label {{ font-family: Arial; font-size: 12px; font-weight: bold; fill: #333; }}
        .caption {{ font-family: Arial; font-size: 11px; fill: #888; }}
    </style>
    
    <text x="10" y="30" class="title">Climate Code Distribution (by unique study)</text>
''']
                
                y_position = 60
                for climate_code, count in sorted_items:
                    description = climate_display_map.get(climate_code, climate_code)
                    color = get_climate_color(climate_code)
                    
                    width_percent = (count / max_count) * 100
                    min_width_percent = (MIN_BAR_WIDTH_PX / MAX_BAR_WIDTH_PX) * 100
                    display_width_percent = max(width_percent, min_width_percent)
                    bar_width = (display_width_percent / 100) * 500
                    
                    # Text color based on background
                    text_color = 'white' if color in ['#105e8d', '#2470a0', '#3882b3', '#4c94c6', '#FF4444', '#44AA44', '#4444FF'] else 'black'
                    
                    # Description on left
                    svg_content.append(f'    <text x="10" y="{y_position + 16}" class="desc-label">{description}</text>')
                    
                    # Bar with code inside
                    svg_content.append(f'    <rect x="250" y="{y_position + 5}" width="{bar_width}" height="24" fill="{color}" rx="4" ry="4" />')
                    svg_content.append(f'    <text x="258" y="{y_position + 23}" fill="{text_color}" font-family="Arial" font-size="12" font-weight="normal">{climate_code}</text>')
                    
                    # Count
                    svg_content.append(f'    <text x="770" y="{y_position + 24}" class="count-label">{count}</text>')
                    
                    y_position += 40
                
                svg_content.append(f'    <text x="10" y="{y_position + 20}" class="caption">Total studies with data: {sum(climate_counts.values())}</text>')
                svg_content.append('</svg>')
                
                svg_string = '\n'.join(svg_content)
                
                import base64
                b64 = base64.b64encode(svg_string.encode()).decode()
                filename = "Climate_Distribution_Chart.svg"
                
                st.markdown(f'''
                <div style="padding: 10px; background-color: #f0f2f6; border-radius: 5px; margin: 10px 0;">
                    <p style="margin-bottom: 10px; font-weight: bold;">✅ SVG Ready for Download:</p>
                    <a href="data:image/svg+xml;base64,{b64}" download="{filename}" 
                       style="background-color: #4CAF50; color: white; padding: 8px 16px; 
                              text-decoration: none; border-radius: 4px; display: inline-block;">
                        📥 Click here to save {filename}
                    </a>
                </div>
                ''', unsafe_allow_html=True)
    else:
        st.info("No climate data available")

def render_scale_distribution(unique_studies):
    """Render scale Frequency with clean bars"""
    st.subheader("Scale Frequency ")
    
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
        render_clean_distribution_bars(
            scale_counts, 
            {}, 
            get_scale_color,
            chart_name="Scale_Frequency_Chart"
        )
    else:
        st.info("No scale data available")

def render_building_use_distribution(unique_studies):
    """Render building use Frequency with clean bars"""
    st.subheader("Building Use Frequency ")
    
    # Count building uses by UNIQUE STUDY
    building_counts = {}
    for study in unique_studies:
        building_use = study.get('building_use')
        if building_use and building_use not in ['', None]:
            building_counts[building_use] = building_counts.get(building_use, 0) + 1
    
    if building_counts:
        render_clean_distribution_bars(
            building_counts, 
            {}, 
            get_building_use_color,
            chart_name="Building_Use_Frequency_Chart"
        )
    else:
        st.info("No building use data available")

def render_approach_distribution(unique_studies):
    """Render approach Frequency with clean bars"""
    st.subheader("Approach Frequency ")
    
    # Count approaches by UNIQUE STUDY
    approach_counts = {}
    for study in unique_studies:
        approach = study.get('approach')
        if approach and approach not in ['', None]:
            approach_counts[approach] = approach_counts.get(approach, 0) + 1
    
    if approach_counts:
        render_clean_distribution_bars(
            approach_counts, 
            {}, 
            get_approach_color,
            chart_name="Approach_Frequency_Chart"
        )
    else:
        st.info("No approach data available")

def render_clean_distribution_bars(counts, descriptions, color_func, show_code=False, chart_name="Frequency"):
    """Generic function to render Frequency bars with clean design and SVG export"""
    if not counts:
        return
    
    sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    max_count = max(count for _, count in sorted_items)
    
    # Display the bars first
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
    
    # SVG export button below the chart
    st.markdown("---")
    col1, col2 = st.columns([1, 5])
    
    with col1:
        if st.button("📥 Export as SVG", key=f"export_svg_{chart_name}_{hash(str(sorted_items))}"):
            # Generate SVG
            svg_height = len(sorted_items) * 40 + 80  # 40px per bar + header
            svg_width = 900
            
            # Clean chart name for filename
            clean_filename = chart_name.lower().replace(' ', '_').replace('(', '').replace(')', '')
            
            svg_content = [f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{svg_width}" height="{svg_height}" xmlns="http://www.w3.org/2000/svg">
    <style>
        .title {{ font-family: Arial; font-size: 16px; font-weight: bold; fill: #333; }}
        .bar-label {{ font-family: Arial; font-size: 12px; fill: #555; }}
        .count-label {{ font-family: Arial; font-size: 12px; font-weight: bold; fill: #333; }}
        .caption {{ font-family: Arial; font-size: 11px; fill: #888; }}
    </style>
    
    <!-- Chart Title -->
    <text x="10" y="30" class="title">{chart_name.replace('_', ' ').title()}</text>
''']
            
            y_position = 60
            for item, count in sorted_items:
                description = descriptions.get(item, '') if descriptions else ''
                
                if description and show_code:
                    left_text = f"{item} - {description}"
                elif description:
                    left_text = description
                else:
                    left_text = item
                
                # Truncate long text for SVG
                if len(left_text) > 40:
                    left_text = left_text[:37] + "..."
                
                color = color_func(item)
                width_percent = (count / max_count) * 100
                bar_width = (width_percent / 100) * 500  # Max bar width 500px
                
                # Add text label
                svg_content.append(f'    <text x="10" y="{y_position + 16}" class="bar-label">{left_text}</text>')
                
                # Add bar
                svg_content.append(f'    <rect x="250" y="{y_position + 5}" width="{bar_width}" height="24" fill="{color}" rx="4" ry="4" />')
                
                # Add count
                svg_content.append(f'    <text x="770" y="{y_position + 24}" class="count-label">{count}</text>')
                
                y_position += 40
            
            # Add caption
            svg_content.append(f'    <text x="10" y="{y_position + 20}" class="caption">Total studies with data: {sum(counts.values())}</text>')
            svg_content.append('</svg>')
            
            svg_string = '\n'.join(svg_content)
            
            # SVG download
            import base64
            b64 = base64.b64encode(svg_string.encode()).decode()
            filename = f"{clean_filename}.svg"
            
            # Create both a visible link and auto-download
            st.markdown(f'''
            <div style="padding: 10px; background-color: #f0f2f6; border-radius: 5px; margin: 10px 0;">
                <p style="margin-bottom: 10px; font-weight: bold;">✅ SVG Ready for Download:</p>
                <a href="data:image/svg+xml;base64,{b64}" download="{filename}" 
                   style="background-color: #4CAF50; color: white; padding: 8px 16px; 
                          text-decoration: none; border-radius: 4px; display: inline-block;">
                    📥 Click here to save {filename}
                </a>
                <p style="margin-top: 8px; font-size: 12px; color: #666;">
                    If download doesn't start automatically, click the button above.
                </p>
            </div>
            ''', unsafe_allow_html=True)
            
            # Also trigger auto-download via JavaScript
            st.markdown(f'''
            <script>
                setTimeout(function() {{
                    const link = document.createElement('a');
                    link.href = 'data:image/svg+xml;base64,{b64}';
                    link.download = '{filename}';
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                }}, 500);
            </script>
            ''', unsafe_allow_html=True)

