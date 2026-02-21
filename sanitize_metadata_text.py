import pandas as pd
import re
def sanitize_metadata_text(text):
    """Remove markdown formatting characters from metadata text"""
    if not text or pd.isna(text):
        return text
    
    text = str(text)
    
    # Remove markdown formatting characters
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'__(.*?)__', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'_(.*?)_', r'\1', text)
    
    # Remove any remaining asterisks
    text = text.replace('**', '').replace('*', '')
    
    return text.strip()