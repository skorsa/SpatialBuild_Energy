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
import pandas as pd

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
    st.caption("Interactive map showing where studies are located. Click on markers for complete study details. Marker colors represent climate zones.")
    
    # Add filter options (simplified - no status filter)
    with st.expander("🔍 Filter Options", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            show_clusters = st.checkbox("Show clustered locations", value=True, 
                                       help="When enabled, multiple studies at nearby locations will be spread out",
                                       key="map_show_clusters")
            marker_size = st.slider("Marker size", min_value=3, max_value=15, value=5, 
                                   help="Adjust the size of location markers",
                                   key="map_marker_size")
        
        with col2:
            max_markers = st.number_input("Max markers to display", min_value=50, max_value=2000, value=1000, step=50,
                                         help="Limit the number of markers for better performance",
                                         key="map_max_markers")
    
    # Get all non-rejected records
    with st.spinner("Loading location data..."):
        all_records = db_connection.get_energy_data(limit=5000)
        
        # Only include non-rejected records (keep NULL, approved, pending)
        valid_records = [r for r in all_records if r.get('status') != 'rejected']
        
        # Process records
        location_records, location_groups = prepare_location_data(valid_records)
        
        # Debug info
        st.sidebar.write(f"📍 Records with coordinates: {len(location_records)}")
        st.sidebar.write(f"🗺️ Location groups: {len(location_groups)}")
    
    if not location_records:
        st.info("📭 No location data available for mapping.")
        return
    
    # Create a hash of filter settings to detect changes
    filter_hash = hash(f"{show_clusters}_{marker_size}_{max_markers}")

    if 'last_filter_hash' not in st.session_state:
        st.session_state.last_filter_hash = filter_hash

    # Check if filters changed OR if this is the first run
    filters_changed = st.session_state.last_filter_hash != filter_hash
    
    # Debug
    st.sidebar.write(f"🔄 Filters changed: {filters_changed}")
    st.sidebar.write(f"🗺️ Map in session: {'map' in st.session_state}")

    # Recreate map if filters changed or first run
    if filters_changed or 'map' not in st.session_state:
        st.sidebar.write("🆕 Creating new map...")
        
        # Create new map
        m = folium.Map(location=[20, 0], zoom_start=2, tiles='CartoDB positron')
        
        # Add markers (your existing marker code)
        for group_key, group_data in location_groups.items():
            radius = marker_size + min(group_data['count'] * 1.5, 15)
            
            if show_clusters and group_data['count'] > 1:
                for j, record in enumerate(group_data['records'][:30]):
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
                for record in group_data['records']:
                    marker_color = get_climate_color(record['climate'])
                    direction_icon = "📈" if record['direction'] == 'Increase' else "📉"
                    
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
                                <tr><td style='padding: 5px; font-weight: bold;'>Climate:</td><td><span style='background-color: {marker_color}; padding: 2px 8px; border-radius: 10px; color: white;'>{record['climate']}</span></td></tr>
                                <tr><td style='padding: 5px; font-weight: bold;'>Scale:</td><td>{record['scale']}</td></tr>
                            </table>
                            <hr>
                            <div style='font-weight: bold; margin-bottom: 5px;'>Study Content:</div>
                            <div style='max-height: 300px; overflow-y: auto; background-color: #f8f9fa; padding: 15px; border-radius: 5px; font-size: 13px; line-height: 1.6;'>
                                {record['paragraph']}
                            </div>
                        </div>
                    </div>
                    """
                    
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
        
        # Store the map in session state
        st.session_state.map = m
        st.session_state.last_filter_hash = filter_hash
        
        st.sidebar.write("✅ Map created and stored")

    # Display the map from session state
    if 'map' in st.session_state:
        st.sidebar.write("🗺️ Displaying map from session")
        folium_static(st.session_state.map, width=800, height=500)
    else:
        st.info("Loading map...")
        st.sidebar.write("❌ No map in session state")

    # Statistics
    st.divider()
    col1, col2, col3 = st.columns(3)
    col1.metric("📍 Geographic Locations", len(location_groups))
    col2.metric("📚 Records on Map", len(location_records))
    if location_groups:
        most = max(location_groups.items(), key=lambda x: x[1]['count'])
        col3.metric("🏆 Most Records", f"{most[1]['location']} ({most[1]['count']})")


    # Count records with no specific location - USING CACHE AS SOURCE OF TRUTH
    from location_lookup import load_location_cache

    # Load the cache
    cache = load_location_cache()

    # Get all valid records
    all_records = db_connection.get_energy_data(limit=5000)
    valid_records = [r for r in all_records if r.get('status') != 'rejected']

    # Separate records based on cache
    geographic_records = []
    unspecified_records = []

    for record in valid_records:
        location = record.get('location', '')
        
        if not location or location.strip() == '':
            # Empty location
            unspecified_records.append(record)
        else:
            # Check if location exists in cache and has coordinates
            cache_entry = cache.get(location)
            if cache_entry is None:
                # Location is in cache but has null coordinates (explicitly non-geographic)
                unspecified_records.append(record)
            elif cache_entry is not None:
                # Location has coordinates in cache
                geographic_records.append(record)
            else:
                # Location not in cache (shouldn't happen after regeneration)
                # Fallback to term-based filtering
                location_lower = location.lower()
                non_geographic_terms = ['global', 'not specified', 'generic', 'n/a', 'unknown', 'various', 
                                    'none', 'unspecified', 'all', 'multiple', 'worldwide']
                if any(term in location_lower for term in non_geographic_terms):
                    unspecified_records.append(record)
                else:
                    geographic_records.append(record)

    # Double-check that location_records matches geographic_records
    # (This is just for debugging - can be removed later)
    if len(location_records) != len(geographic_records):
        print(f"⚠️ Warning: location_records ({len(location_records)}) != geographic_records ({len(geographic_records)})")

    if unspecified_records:
        with st.expander(f"📋 Studies Without Specific Locations ({len(unspecified_records)} records)"):
            st.caption("These records have missing, empty, or non-geographic locations (Global, Not Specified, Generic, etc.)")
            
            # Group by location type
            location_counts = {}
            for record in unspecified_records:
                loc = record.get('location', 'Not specified')
                if not loc or loc.strip() == '':
                    loc = 'Not specified'
                location_counts[loc] = location_counts.get(loc, 0) + 1
            
            # Display summary counts
            st.write("**Summary by location type:**")
            for loc, count in sorted(location_counts.items()):
                # Add emoji indicator based on cache status
                cache_entry = cache.get(loc)
                if cache_entry is None:
                    status = "❌"  # Explicitly non-geographic
                elif loc not in cache:
                    status = "⚠️"  # Not in cache
                else:
                    status = "✅"  # Should not happen here
                st.write(f"• {status} **{loc}**: {count} study/studies")

            # Option to show detailed records without locations
            if st.checkbox("Show detailed records without locations", key="show_unspecified_details"):
                st.write("**Detailed records:**")
                
                # Create data for display
                records_data = []
                for record in unspecified_records[:100]:  # Limit to 100
                    location = record.get('location', 'Not specified')
                    cache_status = "❌ No coordinates" if cache.get(location) is None else "⚠️ Not in cache"
                    
                    records_data.append({
                        'ID': record.get('id'),
                        'Location': location,
                        'Status': cache_status,
                        'Determinant': record.get('criteria'),
                        'Energy Output': record.get('energy_method'),
                        'Direction': record.get('direction'),
                        'Climate': record.get('climate'),
                        'Scale': record.get('scale')
                    })
                
                if records_data:
                    # Try using pandas
                    try:
                        import pandas as pd
                        df = pd.DataFrame(records_data)
                        st.dataframe(df, use_container_width=True)
                    except ImportError:
                        # Manual display without pandas
                        for item in records_data[:20]:  # Limit to 20 for manual display
                            st.markdown(f"""
                            **ID {item['ID']}**: {item['Determinant']} → {item['Energy Output']}  
                            Location: {item['Location']} | {item['Status']}  
                            Climate: {item['Climate']} | Scale: {item['Scale']} | Direction: {item['Direction']}
                            ---
                            """)
                        if len(records_data) > 20:
                            st.caption(f"... and {len(records_data) - 20} more")
                    
                    if len(unspecified_records) > 100:
                        st.caption(f"Showing 100 of {len(unspecified_records)} records")