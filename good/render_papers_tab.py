def render_papers_tab():
    """Render the Studies tab with search functionality - LOADS NOTHING UNTIL SEARCH"""
    st.title("Research Studies Database")
    
    st.markdown("""Use the search box below to browse all studies in the SpatialBuild Energy database.""")
    
    st.markdown("---")
    
    # ============= CLEAN SESSION STATE =============
    if "papers_search_performed" not in st.session_state:
        st.session_state.papers_search_performed = False
    
    if "papers_current_results" not in st.session_state:
        st.session_state.papers_current_results = None
    
    if "papers_current_page" not in st.session_state:
        st.session_state.papers_current_page = 0
    
    if "papers_search_query" not in st.session_state:
        st.session_state.papers_search_query = ""
    
    # ============= CUSTOM CSS FOR PAGINATION =============
    st.markdown("""
    <style>
    /* Center pagination controls */
    div[data-testid="column"]:has(button[key*="papers_prev"]),
    div[data-testid="column"]:has(button[key*="papers_next"]) {
        display: flex;
        justify-content: center;
        align-items: center;
    }
    
    /* Center the page counter text */
    div[data-testid="column"]:has(p:contains("Page")) {
        display: flex;
        justify-content: center;
        align-items: center;
        text-align: center;
    }
    
    /* Make pagination buttons consistent */
    button[key*="papers_prev"], button[key*="papers_next"] {
        width: 100px !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # ============= SEARCH INTERFACE =============
    
    # Search row with two columns
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.markdown("**Search Studies**")
        
        # Function to handle search on Enter
        def on_search_change():
            if st.session_state.papers_search_input:
                st.session_state.papers_search_triggered = True
                st.session_state.papers_search_query = st.session_state.papers_search_input
            else:
                # If search is cleared, reset everything
                st.session_state.papers_search_triggered = False
                st.session_state.papers_search_query = ""
                st.session_state.papers_current_results = []
                st.session_state.papers_search_performed = False
                st.session_state.papers_last_query = ""
                st.session_state.papers_current_page = 0
        
        # The text input
        search_query = st.text_input(
            "Search studies",
            placeholder="Type to search by title, author, determinant, climate...",
            key="papers_search_input",
            label_visibility="collapsed",
            on_change=on_search_change,
            value=st.session_state.get("papers_search_query", "")
        )
    
    with col2:
        st.markdown("**Sort by**")
        sort_order = st.selectbox(
            "Sort results by",
            ["Determinant (A-Z)", 
             "Location (A-Z)", 
             "Building Use (A-Z)", 
             "Scale (A-Z)", 
             "Climate (A-Z)", 
             "Approach (A-Z)"],
            key="papers_sort",
            label_visibility="collapsed"
        )
    
    # Get current search query from widget
    current_search = st.session_state.get("papers_search_input", "")
    
    # Trigger search from on_change event
    if st.session_state.get("papers_search_triggered", False) and current_search:
        search_query = current_search
        st.session_state.papers_search_triggered = False
        st.session_state.papers_search_query = search_query
        st.session_state.papers_last_query = search_query
        st.session_state.papers_search_performed = True
        
        with st.spinner(f"Searching for '{search_query}'..."):
            # Create local connection
            conn_local = sqlite3.connect(db_file)
            cursor = conn_local.cursor()
            
            # Search using SQL LIKE
            search_pattern = f'%{search_query}%'
            
            cursor.execute('''
                SELECT 
                    id,
                    paragraph,
                    criteria,
                    energy_method,
                    direction,
                    scale,
                    climate,
                    location,
                    building_use,
                    approach,
                    sample_size
                FROM energy_data 
                WHERE paragraph IS NOT NULL 
                  AND paragraph != '' 
                  AND paragraph != '0' 
                  AND paragraph != '0.0'
                  AND paragraph != 'None'
                  AND LENGTH(TRIM(paragraph)) > 0
                  AND status NOT IN ("rejected")
                  AND (
                      LOWER(paragraph) LIKE LOWER(?) OR
                      LOWER(criteria) LIKE LOWER(?) OR
                      LOWER(energy_method) LIKE LOWER(?) OR
                      LOWER(location) LIKE LOWER(?) OR
                      LOWER(climate) LIKE LOWER(?) OR
                      LOWER(building_use) LIKE LOWER(?) OR
                      LOWER(approach) LIKE LOWER(?)
                  )
                ORDER BY id DESC
            ''', (search_pattern, search_pattern, search_pattern, 
                  search_pattern, search_pattern, search_pattern, search_pattern))
            
            results = cursor.fetchall()
            conn_local.close()
            
            # Store results
            st.session_state.papers_current_results = results
            st.session_state.papers_current_page = 0
            
            st.rerun()
    
    # ============= RESULTS HEADER AND CLEAR BUTTON =============
    # Only show when there's a search query
    if (st.session_state.get("papers_search_performed", False) and 
        st.session_state.get("papers_last_query", "") and 
        st.session_state.papers_current_results is not None):
        
        results = st.session_state.papers_current_results
        search_query = st.session_state.get("papers_last_query", "")
        
        # Sort results based on selected option
        if sort_order == "Determinant (A-Z)":
            results.sort(key=lambda x: str(x[2] or '').lower())  # criteria
        elif sort_order == "Location (A-Z)":
            results.sort(key=lambda x: str(x[7] or '').lower())  # location
        elif sort_order == "Building Use (A-Z)":
            results.sort(key=lambda x: str(x[8] or '').lower())  # building_use
        elif sort_order == "Scale (A-Z)":
            results.sort(key=lambda x: str(x[5] or '').lower())  # scale
        elif sort_order == "Climate (A-Z)":
            results.sort(key=lambda x: str(x[6] or '').lower())  # climate
        elif sort_order == "Approach (A-Z)":
            results.sort(key=lambda x: str(x[9] or '').lower())  # approach
        
        # Results header with inline clear button - SHOW FOR BOTH RESULTS AND NO RESULTS
        col_header, col_clear = st.columns([4, 1])
        
        with col_header:
            if len(results) == 1:
                st.success(f"Found {len(results)} study matching '{search_query}'")
            elif len(results) > 1:
                st.success(f"Found {len(results)} studies matching '{search_query}'")
            else:
                st.warning(f"No results found for '{search_query}'")
        
        with col_clear:
            # Clear button positioned next to the message
            if st.button("✕ Clear", key=f"clear_btn_{st.session_state.get('papers_clear_counter', 0)}", 
                       help="Clear search", use_container_width=False):
                st.session_state.papers_clear_counter = st.session_state.get('papers_clear_counter', 0) + 1
                st.session_state.papers_search_query = ""
                st.session_state.papers_current_results = []
                st.session_state.papers_search_performed = False
                st.session_state.papers_search_triggered = False
                st.session_state.papers_current_page = 0
                st.session_state.papers_last_query = ""
                st.rerun()
        
        # Only show results and pagination if there are results
        if len(results) > 0:
            # ============= TOP PAGINATION =============
            PAPERS_PER_PAGE = 10
            total_pages = (len(results) + PAPERS_PER_PAGE - 1) // PAPERS_PER_PAGE
            
            if total_pages > 1:
                col_prev, col_page, col_next = st.columns([1, 1, 1])
                
                with col_prev:
                    if st.button("◀ Previous", disabled=st.session_state.papers_current_page == 0, 
                               key="papers_prev_top", use_container_width=True):
                        st.session_state.papers_current_page = max(0, st.session_state.papers_current_page - 1)
                        st.rerun()
                
                with col_page:
                    st.markdown(f"<div style='text-align: center; font-weight: 500;'>Page {st.session_state.papers_current_page + 1} of {total_pages}</div>", 
                              unsafe_allow_html=True)
                
                with col_next:
                    if st.button("Next ▶", disabled=st.session_state.papers_current_page >= total_pages - 1, 
                               key="papers_next_top", use_container_width=True):
                        st.session_state.papers_current_page = min(total_pages - 1, st.session_state.papers_current_page + 1)
                        st.rerun()
            
            # Get current page
            start_idx = st.session_state.papers_current_page * PAPERS_PER_PAGE
            end_idx = min(start_idx + PAPERS_PER_PAGE, len(results))
            page_results = results[start_idx:end_idx]
            
            # Display current page indicator
            st.markdown(f"<div style='text-align: right; color: #666; font-size: 0.9em;'>Showing {start_idx + 1}-{end_idx} of {len(results)} records</div>", 
                      unsafe_allow_html=True)
            
            # ============= DISPLAY RESULTS =============
            for record in page_results:
                record_id, paragraph, criteria, energy_method, direction, scale, climate, location, building_use, approach, sample_size = record
                
                st.markdown("---")
                
                # TWO COLUMN LAYOUT
                col1, col2 = st.columns(2)
                
                with col1:
                    clean_criteria = sanitize_metadata_text(criteria)
                    clean_energy_method = sanitize_metadata_text(energy_method)
                    
                    st.write(f"**{clean_criteria}** → **{clean_energy_method}** ({direction})")
                    st.write(f"**Record ID:** {record_id}")
                    if location:
                        st.write(f"**Location:** {sanitize_metadata_text(location)}")
                    if building_use:
                        st.write(f"**Building Use:** {sanitize_metadata_text(building_use)}")
                                
                with col2:
                    st.write(f"**Scale:** {scale if scale else 'Not specified'}")
                    if climate:
                        color = get_climate_color(climate)
                        
                        # Define climate descriptions (same as above)
                        climate_descriptions = {
                            'Af': 'Tropical Rainforest', 'Am': 'Tropical Monsoon', 'Aw': 'Tropical Savanna',
                            'BWh': 'Hot Desert', 'BWk': 'Cold Desert', 'BSh': 'Hot Semi-arid', 'BSk': 'Cold Semi-arid',
                            'Cfa': 'Humid Subtropical', 'Cfb': 'Oceanic', 'Cfc': 'Subpolar Oceanic',
                            'Csa': 'Hot-summer Mediterranean', 'Csb': 'Warm-summer Mediterranean',
                            'Cwa': 'Monsoon-influenced Humid Subtropical',
                            'Dfa': 'Hot-summer Humid Continental', 'Dfb': 'Warm-summer Humid Continental', 
                            'Dfc': 'Subarctic', 'Dfd': 'Extremely Cold Subarctic',
                            'Dwa': 'Monsoon-influenced Hot-summer Humid Continental',
                            'Dwb': 'Monsoon-influenced Warm-summer Humid Continental',
                            'Dwc': 'Monsoon-influenced Subarctic',
                            'Dwd': 'Monsoon-influenced Extremely Cold Subarctic',
                            'ET': 'Tundra', 'EF': 'Ice Cap',
                            'Var': 'Varies / Multiple Climates'
                        }
                        
                        # Get the climate code (handle both raw codes and formatted strings)
                        climate_code = climate
                        if " - " in str(climate):
                            climate_code = climate.split(" - ")[0]
                        climate_code = ''.join([c for c in str(climate_code) if c.isalnum()])
                        
                        # Get description
                        description = climate_descriptions.get(climate_code, '')
                        
                        # Format display text
                        if description:
                            climate_display = f"{climate_code} - {description}"
                        else:
                            climate_display = climate_code
                            
                        st.markdown(
                            f"**Climate:** <span style='background-color: {color}; padding: 2px 8px; border-radius: 10px; color: black;'>{climate_display}</span>", 
                            unsafe_allow_html=True
                        )
                    if approach:
                        st.write(f"**Approach:** {approach}")
                    if sample_size:
                        st.write(f"**Sample Size:** {sample_size}")
                
                # STUDY CONTENT
                highlighted_paragraph = paragraph
                if search_query:
                    import re
                    pattern = re.compile(re.escape(search_query), re.IGNORECASE)
                    highlighted_paragraph = pattern.sub(
                        lambda m: f"<span style='background-color: #FFFF00; font-weight: bold;'>{m.group()}</span>", 
                        highlighted_paragraph
                    )
                
                paragraph_with_links = convert_urls_to_links(highlighted_paragraph)
                
                st.markdown(
                    f'''
                    <div style="
                        border: 1px solid #e0e0e0;
                        padding: 15px;
                        border-radius: 8px;
                        background-color: #f9f9fb;
                        max-height: 250px;
                        overflow-y: auto;
                        font-family: Arial, sans-serif;
                        line-height: 1.5;
                        font-size: 14px;
                        user-select: text;
                        -webkit-user-select: text;
                        cursor: text;
                    ">
                        {paragraph_with_links}
                    </div>
                    ''',
                    unsafe_allow_html=True
                )
                
                st.markdown("<br>", unsafe_allow_html=True)
            
            # ============= BOTTOM PAGINATION =============
            if total_pages > 1:
                st.markdown("---")
                
                col_prev_bottom, col_page_bottom, col_next_bottom = st.columns([1, 1, 1])
                
                with col_prev_bottom:
                    if st.button("◀ Previous", disabled=st.session_state.papers_current_page == 0, 
                               key="papers_prev_bottom", use_container_width=True):
                        st.session_state.papers_current_page = max(0, st.session_state.papers_current_page - 1)
                        st.rerun()
                
                with col_page_bottom:
                    st.markdown(f"<div style='text-align: center; font-weight: 500;'>Page {st.session_state.papers_current_page + 1} of {total_pages}</div>", 
                              unsafe_allow_html=True)
                
                with col_next_bottom:
                    if st.button("Next ▶", disabled=st.session_state.papers_current_page >= total_pages - 1, 
                               key="papers_next_bottom", use_container_width=True):
                        st.session_state.papers_current_page = min(total_pages - 1, st.session_state.papers_current_page + 1)
                        st.rerun()
                
                st.markdown(f"<div style='text-align: right; color: #666; font-size: 0.9em; margin-top: 5px;'>Showing {start_idx + 1}-{end_idx} of {len(results)} records</div>", 
                          unsafe_allow_html=True)
    
    # Initial state - no search performed yet
    elif not st.session_state.papers_search_performed:
        st.info("Enter a search term above and press Enter to find studies in the database.")
    
    # Empty search state - show nothing