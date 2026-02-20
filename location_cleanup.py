# location_cleanup.py
import streamlit as st
import pandas as pd
import re

def cleanup_locations(db_connection):
    """Clean up location names in the database"""
    
    # Get all records
    all_records = db_connection.get_energy_data(limit=5000)
    
    # Define cleaning rules
    cleaning_rules = {
        # Standardize country/region names
        r'Belgium \(Walloon Region\)': 'Wallonia, Belgium',
        r'Walloon Region, Belgium': 'Wallonia, Belgium',
        
        # US cities
        r'Dallas, TX': 'Dallas, Texas, USA',
        r'St\. Paul, Minnesota, and Tallahassee, Florida, USA': 'SPLIT:St. Paul, Minnesota, USA|Tallahassee, Florida, USA',
        
        # India
        r'Delhi, India \(specifically, Safdarjung and NPL areas\)': 'Delhi, India',
        
        # Eastern Europe - set to approximate center (Poland)
        r'Eastern Europe \(specifically 11 post-communist countries: Slovenia, Slovak Republic, Czech Republic, Romania, Poland, Lithuania, Latvia, Estonia, Belarus, Russia, Ukraine\)': 'Warsaw, Poland',
        
        # Global variations - all to 'Global' (will be filtered out)
        r'Global \*\*': 'Global',
        r'Global \(136 countries\)': 'Global',
        r'Global \(developed and developing countries\)': 'Global',
        r'\*\*Global \*\*': 'Global',
        
        # Not specified variations
        r'Not specified': 'Not Specified',
    }
    
    # Track changes
    updates = []
    split_records = []
    
    for record in all_records:
        record_id = record['id']
        old_location = record.get('location', '')
        
        if not old_location:
            continue
            
        new_location = old_location
        needs_update = False
        
        # Apply cleaning rules
        for pattern, replacement in cleaning_rules.items():
            if re.search(pattern, old_location, re.IGNORECASE):
                if replacement.startswith('SPLIT:'):
                    # Handle split locations
                    locations = replacement.replace('SPLIT:', '').split('|')
                    for loc in locations:
                        split_records.append({
                            'original_id': record_id,
                            'new_location': loc.strip(),
                            'original_record': record
                        })
                    needs_update = True
                    new_location = None  # Mark for deletion
                else:
                    new_location = re.sub(pattern, replacement, old_location, flags=re.IGNORECASE)
                    needs_update = True
                break
        
        if needs_update:
            if new_location is None:
                # This record will be replaced by split records
                updates.append({
                    'id': record_id,
                    'action': 'delete',
                    'old': old_location
                })
            else:
                updates.append({
                    'id': record_id,
                    'action': 'update',
                    'old': old_location,
                    'new': new_location
                })
    
    # Show preview of changes
    st.subheader("Location Cleanup Preview")
    
    if updates:
        df_updates = pd.DataFrame(updates)
        st.dataframe(df_updates)
    
    if split_records:
        st.write(f"**{len(split_records)} new records will be created from split locations**")
        for split in split_records[:5]:
            st.write(f"- Record {split['original_id']} → {split['new_location']}")
        if len(split_records) > 5:
            st.write(f"... and {len(split_records) - 5} more")
    
    # Confirmation button
    if st.button("Apply Cleanup"):
        with st.spinner("Updating locations..."):
            # Apply updates
            for update in updates:
                if update['action'] == 'update':
                    db_connection.update_record('energy_data', update['id'], {'location': update['new']})
                elif update['action'] == 'delete':
                    # For split locations, we'll delete original and create new records
                    original = next((s['original_record'] for s in split_records if s['original_id'] == update['id']), None)
                    if original:
                        # Delete original
                        db_connection.delete_record('energy_data', update['id'])
                        
                        # Create new records for each split
                        for split in [s for s in split_records if s['original_id'] == update['id']]:
                            new_record = original.copy()
                            new_record.pop('id', None)  # Remove ID to let DB assign new one
                            new_record['location'] = split['new_location']
                            db_connection.insert_record('energy_data', new_record)
            
            st.success(f"Applied {len(updates)} updates and created {len(split_records)} new records!")