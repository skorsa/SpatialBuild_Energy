# location_map.py
import streamlit as st
import folium
from streamlit_folium import folium_static
import random
import pandas as pd
import re
from folium import IFrame, Html
import math
from location_lookup import get_location_coordinates  # Fixed import!

# Function to convert URLs to clickable links
def convert_urls_to_links(text):
    """Convert URLs in text to clickable HTML links"""
    if not text:
        return text
    
    # Replace newlines with HTML line breaks
    text = text.replace('\n', '<br>')
    
    # URL patterns to match
    patterns = [
        (r'\b(doi\.org/\S+)\b', r'<a href="https://\1" target="_blank" style="color: #0066cc; text-decoration: none;">\1</a>'),
        (r'(https?://\S+)', r'<a href="\1" target="_blank" style="color: #0066cc; text-decoration: none;">\1</a>'),
        (r'\b(www\.\S+)\b', r'<a href="http://\1" target="_blank" style="color: #0066cc; text-decoration: none;">\1</a>'),
    ]
    
    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    return text

# Function to get climate color
def get_climate_color(climate_code):
    """Get color for climate code"""
    if not climate_code:
        return '#808080'
    
    climate_clean = str(climate_code)
    if " - " in climate_clean:
        climate_clean = climate_clean.split(" - ")[0]
    climate_clean = ''.join([c for c in climate_clean if c.isalnum()])
    
    colors = {
        'Af': '#0000FE', 'Am': '#0077FD', 'Aw': '#44A7F8',
        'BWh': '#FD0000', 'BWk': '#F89292', 'BSh': '#F4A400', 'BSk': '#FEDA60',
        'Csa': '#FFFE04', 'Csb': '#CDCE08', 'Cwa': '#95FE97', 'Cwb': '#62C764',
        'Cfa': '#C5FF4B', 'Cfb': '#64FD33', 'Cfc': '#36C901',
        'Dfa': '#01FEFC', 'Dfb': '#3DC6FA', 'Dfc': '#037F7F', 'Dfd': '#004860',
        'Dwa': '#A5ADFE', 'Dwb': '#4A78E7', 'Dwc': '#48DDB1',
        'ET': '#AFB0AB', 'EF': '#686964',
        'Var': '#999999'
    }
    
    climate_upper = climate_clean.upper()
    color_map = {k.upper(): v for k, v in colors.items()}
    return color_map.get(climate_upper, '#808080')

# Spiral offset function
def get_spiral_offset(index, total_count, base_radius=0.03):
    """Generate spiral offsets to spread markers nicely with adaptive radius"""
    if total_count == 1:
        return 0, 0
    
    # Adjust radius based on number of markers
    if total_count > 20:
        radius_step = base_radius * 1.5
    elif total_count > 10:
        radius_step = base_radius * 1.2
    else:
        radius_step = base_radius
    
    # Golden angle in radians (approx 137.5 degrees)
    golden_angle = 2.39996
    
    angle = index * golden_angle
    r = radius_step * math.sqrt(index)
    
    # Add some randomness to break up perfect patterns
    r += random.uniform(-0.005, 0.005)
    
    dx = r * math.cos(angle)
    dy = r * math.sin(angle)
    
    return dx, dy


# ============= DATA PREPARATION FUNCTION =============

@st.cache_data(ttl=3600)
def prepare_location_data(records):
    """Process records and prepare location data for mapping"""
    location_records = []
    
    for record in records:
        location = record.get('location')
        if location and location not in ['', None]:
            coords = get_location_coordinates(location)
            
            # ✅ CRITICAL FIX: Skip if no coordinates found
            if coords is None:
                continue  # Skip this record entirely
                
            raw_paragraph = record.get('paragraph', '')
            
            # Convert URLs to links (with safety checks)
            if raw_paragraph:
                url_pattern = r'https?://\S+|doi\.org/\S+|www\.\S+'
                urls = re.findall(url_pattern, raw_paragraph, re.IGNORECASE)
                
                placeholders = {}
                temp_text = raw_paragraph
                for i, url in enumerate(urls):
                    placeholder = f"__URL_PLACEHOLDER_{i}__"
                    placeholders[placeholder] = url
                    temp_text = temp_text.replace(url, placeholder)
                
                temp_with_links = convert_urls_to_links(temp_text)
                # Ensure we have a string to work with
                if temp_with_links is None:
                    temp_with_links = ""
                
                paragraph_with_links = temp_with_links
                for placeholder, url in placeholders.items():
                    if placeholder in paragraph_with_links:  # Check if placeholder exists
                        paragraph_with_links = paragraph_with_links.replace(placeholder, url)
            else:
                paragraph_with_links = ""
            
            location_records.append({
                'coords': coords,  # Now guaranteed not to be None
                'location': location,
                'criteria': record.get('criteria', 'Unknown'),
                'energy_method': record.get('energy_method', 'Unknown'),
                'direction': record.get('direction', 'Unknown'),
                'id': record.get('id'),
                'climate': record.get('climate', 'Not specified'),
                'scale': record.get('scale', 'Not specified'),
                'approach': record.get('approach', 'Not specified'),
                'sample_size': record.get('sample_size', 'Not specified'),
                'paragraph': paragraph_with_links,
                'paragraph_preview': raw_paragraph[:150] + '...' if len(raw_paragraph) > 150 else raw_paragraph
            })
    
    # Group by location
    location_groups = {}
    for record in location_records:
        group_key = f"{record['coords'][0]:.1f},{record['coords'][1]:.1f}"
        if group_key not in location_groups:
            location_groups[group_key] = {
                'coords': record['coords'],
                'location': record['location'],
                'count': 0,
                'records': []
            }
        location_groups[group_key]['count'] += 1
        location_groups[group_key]['records'].append(record)
    
    return location_records, location_groups

# ============= MAIN RENDER FUNCTION =============

def render_location_map(db_connection):
    """Render a map showing study locations"""
    st.subheader("🗺️ Study Locations Map")
    st.caption("Click on markers for study details. Colors represent climate zones.")
    
    # Filters
    with st.expander("🔍 Filter Options", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            show_clusters = st.checkbox("Show individual markers", value=True, 
                                       help="Show each study as a separate marker")
            marker_size = st.slider("Marker size", 3, 15, 5)
        with col2:
            max_markers = st.number_input("Max markers", 50, 2000, 1000, 50)
    
    # Load data
    with st.spinner("Loading location data..."):
        all_records = db_connection.get_energy_data(limit=5000)
        valid_records = [r for r in all_records if r.get('status') in ['approved', None]]
        location_records, location_groups = prepare_location_data(valid_records)
    
    if not location_records:
        st.info("📭 No location data available.")
        return
    
    # Create map
    m = folium.Map(location=[20, 0], zoom_start=2, tiles='CartoDB positron')
    
    # Add markers
    for group_key, group_data in location_groups.items():
        radius = marker_size + min(group_data['count'] * 1.5, 15)
        
        if show_clusters and group_data['count'] > 1:
            # Individual markers with spiral offset
            for j, record in enumerate(group_data['records'][:30]):  # Limit per location
                dx, dy = get_spiral_offset(j, group_data['count'], 0.03)
                offset_coords = [group_data['coords'][0] + dx, group_data['coords'][1] + dy]
                
                marker_color = get_climate_color(record['climate'])
                direction_icon = "📈" if record['direction'] == 'Increase' else "📉"
                
                popup_html = f"""
                <div style='font-family: Arial; width: 400px; max-height: 500px; overflow-y: auto;'>
                    <div style='background-color: #2c3e50; color: white; padding: 8px;'>
                        <b>{record['location']}</b> | ID: {record['id']}
                    </div>
                    <div style='padding: 10px;'>
                        <b>Determinant:</b> {record['criteria']}<br>
                        <b>Energy Output:</b> {record['energy_method']}<br>
                        <b>Direction:</b> {direction_icon} {record['direction']}<br>
                        <b>Climate:</b> <span style='background-color:{marker_color};padding:2px 5px;color:white'>{record['climate']}</span><br>
                        <b>Scale:</b> {record['scale']}<br>
                        <hr>
                        <div style='max-height:200px;overflow-y:auto;background:#f8f9fa;padding:8px;'>
                            {record['paragraph']}
                        </div>
                    </div>
                </div>
                """
                
                folium.CircleMarker(
                    location=offset_coords,
                    radius=radius/1.5,
                    popup=folium.Popup(Html(popup_html, script=True), max_width=400),
                    color=marker_color,
                    fill=True,
                    fillColor=marker_color,
                    fillOpacity=0.8,
                ).add_to(m)
        else:
            # For single record or when clusters are disabled, show detailed popup for each record
            for record in group_data['records']:
                marker_color = get_climate_color(record['climate'])
                direction_icon = "📈" if record['direction'] == 'Increase' else "📉"
                climate_display = record['climate'] if record['climate'] != 'Not specified' else 'Unknown'
                
                popup_html = f"""
                <div style='font-family: Arial; width: 450px; max-height: 600px; overflow-y: auto;'>
                    <div style='background-color: #2c3e50; color: white; padding: 10px; border-radius: 5px 5px 0 0;'>
                        <b>📍 {record['location']}</b> | ID: {record['id']}
                    </div>
                    <div style='padding: 15px; background-color: white;'>
                        <table style='width: 100%; border-collapse: collapse;'>
                            <tr><td style='padding: 5px; font-weight: bold; width: 120px;'>Determinant:</td><td>{record['criteria']}</td></tr>
                            <tr><td style='padding: 5px; font-weight: bold;'>Energy Output:</td><td>{record['energy_method']}</td></tr>
                            <tr><td style='padding: 5px; font-weight: bold;'>Direction:</td><td>{direction_icon} {record['direction']}</td></tr>
                            <tr><td style='padding: 5px; font-weight: bold;'>Climate:</td><td><span style='background-color: {marker_color}; padding: 2px 8px; border-radius: 10px; color: white;'>{climate_display}</span></td></tr>
                            <tr><td style='padding: 5px; font-weight: bold;'>Scale:</td><td>{record['scale']}</td></tr>
                            <tr><td style='padding: 5px; font-weight: bold;'>Approach:</td><td>{record['approach']}</td></tr>
                            <tr><td style='padding: 5px; font-weight: bold;'>Sample Size:</td><td>{record['sample_size']}</td></tr>
                        </table>
                        <hr>
                        <div style='font-weight: bold; margin-bottom: 5px;'>Study Content:</div>
                        <div style='max-height: 300px; overflow-y: auto; background-color: #f8f9fa; padding: 15px; border-radius: 5px; font-size: 13px; line-height: 1.6;'>
                            {record['paragraph']}
                        </div>
                    </div>
                </div>
                """
                
                # Create HTML object and add to popup
                html = Html(popup_html, script=True)
                popup = folium.Popup(html, max_width=450)
                
                folium.CircleMarker(
                    location=record['coords'],
                    radius=radius,
                    popup=popup,
                    color=marker_color,
                    fill=True,
                    fillColor=marker_color,
                    fillOpacity=0.8,
                    tooltip=f"{record['criteria']} → {record['energy_method']}"
                ).add_to(m)
    
    # Display the map
    folium_static(m, width=800, height=500)
    
    # Statistics
    st.divider()
    col1, col2, col3 = st.columns(3)
    col1.metric("📍 Locations", len(location_groups))
    col2.metric("📚 Records", len(location_records))
    if location_groups:
        most = max(location_groups.items(), key=lambda x: x[1]['count'])
        col3.metric("🏆 Most Records", f"{most[1]['location']} ({most[1]['count']})")