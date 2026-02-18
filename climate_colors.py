# climate_colors.py
def get_climate_color(climate_code):
    """Get color for climate code"""
    if not climate_code:
        return '#808080'
    
    # Extract code if it's formatted
    climate_clean = str(climate_code)
    if " - " in climate_clean:
        climate_clean = climate_clean.split(" - ")[0]
    climate_clean = ''.join([c for c in climate_clean if c.isalnum()])
    
    colors = {
        # Tropical Climates - Blues
        'Af': '#0000FE', 'Am': '#0077FD', 'Aw': '#44A7F8',
        # Arid Climates - Reds/Oranges
        'BWh': '#FD0000', 'BWk': '#F89292', 'BSh': '#F4A400', 'BSk': '#FEDA60',
        # Temperate Climates - Greens
        'Csa': '#FFFE04', 'Csb': '#CDCE08', 'Cwa': '#95FE97', 'Cwb': '#62C764',
        'Cfa': '#C5FF4B', 'Cfb': '#64FD33', 'Cfc': '#36C901',
        # Continental Climates - Purples
        'Dfa': '#01FEFC', 'Dfb': '#3DC6FA', 'Dfc': '#037F7F', 'Dfd': '#004860',
        'Dwa': '#A5ADFE', 'Dwb': '#4A78E7', 'Dwc': '#48DDB1',
        'ET': '#AFB0AB', 'EF': '#686964',
        'Var': '#999999', 'All': '#999999'
    }
    
    # Try uppercase for lookup
    climate_upper = climate_clean.upper()
    color_map = {k.upper(): v for k, v in colors.items()}
    return color_map.get(climate_upper, '#808080')