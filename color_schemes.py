# color_schemes.py
"""
Centralized color schemes for all visualizations in the app.
This file should have NO imports from other project files.
"""

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
    
    climate_upper = climate_clean.upper()
    color_map = {k.upper(): v for k, v in colors.items()}
    return color_map.get(climate_upper, '#808080')

def get_scale_color(scale):
    """Get color for scale (blue gradient from dark to light)"""
    scale_colors = {
        'Multi-National': "#105e8d",      # Darkest blue (first color)
        'National': '#2470a0',             # Step 2
        'Regional': '#3882b3',              # Step 3
        'State(s) / Province(s)': '#4c94c6', # Step 4
        'County / Municipal Region(s)': '#60a6d9', # Step 5
        'Multi-Cities': '#74b8ec',          # Step 6
        'Urban': '#88caff',                  # Step 7
        'District(s)': "#9cd4ff",           # Step 8
        'Neighborhood(s)': '#b0deff',        # Step 9
        'Block(s)': "#d2eefb"                # Lightest blue (last color)
    }
        
    scale_lower = str(scale).lower()
    for key, color in scale_colors.items():
        if key.lower() in scale_lower:
            return color
    return '#9B9B9B'

def get_building_use_color(building_use):
    """Get color for building use"""
    building_colors = {
        'Residential': "#FFFF00",
        'Commercial': "#FF0000",
        'Mixed use': "#B958FF",
        'Office': '#6C5B7B',
        'Retail': '#F08A5D',
        'Industrial': '#B83B5E',
        'Educational': '#45B7D1',
        'Healthcare': '#96CEB4',
        'Public': '#A8E6CF',
        'Religious': '#FFB347',
        'Transport': '#4D96FF',
        'Agricultural': '#6BCB77',
        'Unspecified / Other': '#9B9B9B',
        'Other': '#9B9B9B',
    }
    
    building_lower = str(building_use).lower()
    for key, color in building_colors.items():
        if key.lower() in building_lower:
            return color
    return '#9B9B9B'

def get_approach_color(approach):
    """Get color for research approach"""
    approach_colors = {
        'Hybrid': "#2481A1",
        'Top-down': "#1E57F2",
        'Bottom-up': "#46C9F9",
        'Mixed-methods': '#45B7D1',
        'Empirical': '#96CEB4',
        'Theoretical': '#6C5B7B',
        'Simulation': '#F08A5D',
        'Survey': '#B83B5E',
        'Case study': '#4D96FF',
        'Review': '#A8E6CF',
        'Meta-analysis': '#9B59B6',
        'Literature review': '#F39C12',
        'Experimental': '#27AE60',
        'Modeling': '#2980B9',
    }
    
    approach_lower = str(approach).lower()
    for key, color in approach_colors.items():
        if key.lower() in approach_lower:
            return color
    return '#9B9B9B'

# Climate descriptions for display
climate_descriptions = {
    'Af': 'Tropical Rainforest',
    'Am': 'Tropical Monsoon',
    'Aw': 'Tropical Savanna',
    'BWh': 'Hot Desert',
    'BWk': 'Cold Desert',
    'BSh': 'Hot Semi-arid',
    'BSk': 'Cold Semi-arid',
    'Cfa': 'Humid Subtropical',
    'Cfb': 'Oceanic',
    'Cfc': 'Subpolar Oceanic',
    'Csa': 'Hot-summer Mediterranean',
    'Csb': 'Warm-summer Mediterranean',
    'Cwa': 'Monsoon-influenced Humid Subtropical',
    'Dfa': 'Hot-summer Humid Continental',
    'Dfb': 'Warm-summer Humid Continental',
    'Dfc': 'Subarctic',
    'Dfd': 'Extremely Cold Subarctic',
    'Dwa': 'Monsoon-influenced Hot-summer Humid Continental',
    'Dwb': 'Monsoon-influenced Warm-summer Humid Continental',
    'Dwc': 'Monsoon-influenced Subarctic',
    'Dwd': 'Monsoon-influenced Extremely Cold Subarctic',
    'ET': 'Tundra',
    'EF': 'Ice Cap',
    'Var': 'Varies / Multiple Climates'
}