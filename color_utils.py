# color_utils.py
from color_schemes import (
    get_climate_color,
    get_scale_color,
    get_building_use_color,
    get_approach_color,
    climate_descriptions
)

def get_color_for_field(field_type, value):
    """Unified function to get color for any field type"""
    color_functions = {
        'climate': get_climate_color,
        'scale': get_scale_color,
        'building_use': get_building_use_color,
        'approach': get_approach_color
    }
    
    func = color_functions.get(field_type)
    if func:
        return func(value)
    return '#cccccc'  # Default gray

def format_climate_display(climate):
    """Format climate code with description"""
    if not climate:
        return "Not specified"
    
    climate_code = climate
    if " - " in str(climate):
        climate_code = climate.split(" - ")[0]
    climate_code = ''.join([c for c in str(climate_code) if c.isalnum()])
    
    description = climate_descriptions.get(climate_code, '')
    
    if description:
        return f"{climate_code} - {description}"
    return climate_code