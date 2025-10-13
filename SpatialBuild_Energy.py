import re
import sqlite3
import pandas as pd
import streamlit as st
import streamlit_authenticator as stauth
import streamlit_authenticator as Hasher
from datetime import datetime
import os
from dotenv import load_dotenv
import bcrypt
import time 

load_dotenv()

def query_approved_criteria(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT criteria FROM energy_data WHERE status NOT IN ('rejected', 'pending')  ORDER BY criteria ASC")
    return cursor.fetchall()
    
def query_approved_energy_outputs(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT energy_method FROM energy_data WHERE status NOT IN ('rejected', 'pending') ORDER BY energy_method ASC")
    return cursor.fetchall()

def contribute():
    # Fetch existing determinants and energy outputs from approved records
    approved_determinants = query_approved_criteria(conn)
    criteria_list = ["Select a Determinant", "Add new Determinant"] + [f"{row[0]}" for row in approved_determinants]
    approved_energy_outputs = query_approved_energy_outputs(conn)
    energy_method_list = ["Select an Energy Output", "Add new Energy Output"] + [f"{row[0]}" for row in approved_energy_outputs]

    # Initialize session state
    if "selected_determinant_choice" not in st.session_state:
        st.session_state.selected_determinant_choice = "Select a Determinant"
    if "selected_energy_output_choice" not in st.session_state:
        st.session_state.selected_energy_output_choice = "Select an Energy Output"
    if "selected_direction_choice" not in st.session_state:
        st.session_state.selected_direction_choice = None
    if "new_determinant" not in st.session_state:
        st.session_state.new_determinant = ""
    if "new_energy_output" not in st.session_state:
        st.session_state.new_energy_output = ""
    if "reset_form" not in st.session_state:
        st.session_state.reset_form = False

    # Reset session state if reset_form flag is True
    if st.session_state.reset_form:
        st.session_state.selected_determinant_choice = "Select a Determinant"
        st.session_state.selected_energy_output_choice = "Select an Energy Output"
        st.session_state.selected_direction_choice = None
        st.session_state.new_determinant = ""
        st.session_state.new_energy_output = ""
        st.session_state.reset_form = False

    # Dropdown for Determinants
    selected_determinant_choice = st.selectbox(
        "Determinant",
        criteria_list,
        key="selected_determinant_choice"
    )

    # Handle adding a new determinant
    new_determinant = ""
    if selected_determinant_choice == "Add new Determinant":
        new_determinant = st.text_input("Enter New Determinant", key="new_determinant")

    # Dropdown for Energy Output
    new_energy_output = ""
    if selected_determinant_choice != "Select a Determinant":
        selected_energy_output_choice = st.selectbox(
            "Energy Output",
            energy_method_list,
            key="selected_energy_output_choice"
        )

        # Handle adding a new energy output
        if selected_energy_output_choice == "Add new Energy Output":
            new_energy_output = st.text_input("Enter New Energy Output", key="new_energy_output")
    else:
        selected_energy_output_choice = "Select an Energy Output"

    # Radio buttons for direction
    if (
        st.session_state.selected_energy_output_choice != "Select an Energy Output"
        and st.session_state.selected_determinant_choice != "Select a Determinant"
    ):
        st.radio(
            "Please select the direction of the relationship",
            ["Increase", "Decrease"],
            key="selected_direction_choice"
        )

    # Display text area and save button if all fields are selected
    if st.session_state.selected_direction_choice:
        st.markdown(
            f"<p>Please add your findings which show that a {st.session_state.selected_direction_choice} "
            f"(or presence) in {new_determinant or st.session_state.selected_determinant_choice} leads to <i>{'higher' if st.session_state.selected_direction_choice == 'Increase' else 'lower'}</i> "
            f"{new_energy_output or st.session_state.selected_energy_output_choice}.</p>",
            unsafe_allow_html=True
        )

        # Add New Record Section
        new_paragraph = st.text_area(
            f"Add new record for {new_determinant or st.session_state.selected_determinant_choice} and {new_energy_output or st.session_state.selected_energy_output_choice} "
            f"({st.session_state.selected_direction_choice})",
            key="new_paragraph"
        )

        # Show "Save" button within the form
        if st.button("Save", key="save_new_record"):
            # Save record only if text is provided
            if new_paragraph.strip():
                cursor = conn.cursor()

                # Save the record
                cursor.execute('''
                    INSERT INTO energy_data (criteria, energy_method, direction, paragraph, status, user)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    new_determinant or st.session_state.selected_determinant_choice,
                    new_energy_output or st.session_state.selected_energy_output_choice,
                    st.session_state.selected_direction_choice,
                    new_paragraph,
                    "pending",
                    st.session_state.current_user
                ))
                conn.commit()

                # Set reset_form flag
                st.session_state.reset_form = True

                st.success("New record submitted successfully. Thank you for your contribution. Status: pending verification")

                #allow time to read success message
                time.sleep(2)

                # Refresh the app to reflect the reset
                st.rerun()
            else:
                st.warning("Please ensure the record is not empty before saving.")

def admin_dashboard():
    st.subheader("Review Pending Data Submissions")

    # Connect to the database
    conn = sqlite3.connect("my_database.db")
    cursor = conn.cursor()

    # Fetch all records with their status
    records = cursor.execute("SELECT id, criteria, energy_method, direction, paragraph, user, status FROM energy_data").fetchall()

    if not records:
        st.write("No records found.")
    else:
        for record in records:
            record_id, criteria, energy_method, direction, paragraph, user, status = record
            if status == "pending":
                st.write(f"**Record ID:** {record_id}, **created by:** {user}")
                st.markdown(f"<p>The following pending study shows that a {direction} (or presence) in {criteria} leads to <i>{'higher' if direction ==('Increase') else 'lower'}</i> {energy_method}.</p>", unsafe_allow_html=True)
                st.write(f"**Submitted text:** {paragraph}")

                # Admin options to approve/reject or take action
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"Approve {record_id}"):
                        cursor.execute("UPDATE energy_data SET status = 'approved' WHERE id = ?", (record_id,))
                        conn.commit()
                        st.success(f"Record {record_id} approved.")
                        time.sleep(1)
                        st.rerun()
                with col2:
                    if st.button(f"Reject {record_id}"):
                        cursor.execute("UPDATE energy_data SET status = 'rejected' WHERE id = ?", (record_id,))
                        conn.commit()
                        st.error(f"Record {record_id} rejected.")
                        time.sleep(1)
                        st.rerun()
                st.markdown("---")  # Separator between records

    conn.close()

def user_dashboard():
    st.subheader("Review Your Submissions")

    # Connect to the database
    conn = sqlite3.connect("my_database.db")
    cursor = conn.cursor()

    # Fetch all records with their status
    # Fetch all records created by the current user
    records = cursor.execute("""
        SELECT id, criteria, energy_method, direction, paragraph, user, status
        FROM energy_data
        WHERE user = ?
    """, (st.session_state.current_user,)).fetchall()

    if not records:
        st.write("No records found.")
    else:
        for record in records:
            record_id, criteria, energy_method, direction, paragraph, user, status = record
            if st.session_state.current_user == user:
                st.write(f"**Record ID:** {record_id}, **created by:** {user}, **Status:** {status}")
                st.markdown(f"<p>The following pending study shows that a {direction} (or presence) in {criteria} leads to <i>{'higher' if direction == 'Increase' else 'lower'}</i> {energy_method}.</p>", unsafe_allow_html=True)
                st.write(f"**Submitted text:** {paragraph}")

            # Admin options to approve/reject or take action
            col1, col2 = st.columns(2)
            with col2:
                if st.button(f"Remove this submission {record_id}"):
                    try:
                        cursor.execute("DELETE FROM energy_data WHERE id = ?", (record_id,))
                        conn.commit()
                        st.success(f"Submission {record_id} has been removed.")
                        time.sleep(1)
                        st.rerun()  # Refresh the page to reflect the changes
                    except Exception as e:
                        st.error(f"Failed to remove record {record_id}: {e}")

            st.markdown("---")  # Separator between records

    conn.close()

def edit_columns():
    db_file = 'my_database.db'
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Add `status` column default to 'None'
    cursor.execute("UPDATE energy_data SET status = 'None'")
    conn.commit()
    conn.close()

# Run this function once to update the database schema
#edit_columns()

# Function to reset and re-create the table
def csv_to_sqlite(csv_file, db_file):
    try:
        # Read the CSV file into a DataFrame
        print(f"Reading CSV file: {csv_file}")
        df = pd.read_csv(csv_file, encoding='utf-8-sig')

        # Connect to the SQLite database (or create it)
        print(f"Connecting to database: {db_file}")
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # Drop the old table if it exists
        print("Dropping the existing 'energy_data' table if it exists")
        cursor.execute("DROP TABLE IF EXISTS energy_data")

        # Create the new table with group_id, criteria, energy_method, direction, and paragraph fields
        print("Creating the table 'energy_data' with direction")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS energy_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER,
                criteria TEXT,
                energy_method TEXT,
                direction TEXT,  -- Store Increase/Decrease here
                paragraph TEXT
            )
        ''')

        # Insert CSV data into SQLite, splitting paragraphs
        group_id = 1
        criteria_col = df.columns[0]  # Assuming the first column is 'criteria'
        
        # Group columns based on "Increase" and "Decrease"
        increase_cols = [col for col in df.columns if col.endswith('Increase')]
        reduction_cols = [col for col in df.columns if col.endswith('Decrease')]
        
        for _, row in df.iterrows():
            criteria = row[criteria_col]
            # Insert for each increase column
            for method in increase_cols:
                text_content = row[method]
                paragraphs = split_into_paragraphs(text_content)
                base_method = method.replace('Increase', '').strip()
                
                for paragraph in paragraphs:
                    cursor.execute('''
                        INSERT INTO energy_data (group_id, criteria, energy_method, direction, paragraph, status)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (group_id, criteria, base_method, 'Increase', paragraph))

            # Insert for each reduction column
            for method in reduction_cols:
                text_content = row[method]
                paragraphs = split_into_paragraphs(text_content)
                base_method = method.replace('Decrease', '').strip()
                
                for paragraph in paragraphs:
                    cursor.execute('''
                        INSERT INTO energy_data (group_id, criteria, energy_method, direction, paragraph, status)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (group_id, criteria, base_method, 'Decrease', paragraph))

            group_id += 1

        # Commit and close the connection
        conn.commit()
        print("Data inserted successfully")
        conn.close()

    except Exception as e:
        print(f"Error: {e}")

# Function to split a cell's content into paragraphs
def split_into_paragraphs(text: str) -> list:
    paragraphs = [para.strip() for para in str(text).split('\n\n') if para.strip()]
    return paragraphs

# Run this function once to reset and create the database
#csv_to_sqlite('Full_References_011.csv', 'my_database.db')

# Initialize session state variables
if "current_tab" not in st.session_state:
    st.session_state.current_tab = "tab0"  # Default tab
if 'login_status' not in st.session_state:
    st.session_state.login_status = None
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'selected_criteria' not in st.session_state:
    st.session_state.selected_criteria = None
if 'selected_method' not in st.session_state:
    st.session_state.selected_method = None
if 'show_new_record_form' not in st.session_state:
    st.session_state.show_new_record_form = False# Initialize session state variables
if "user_role" not in st.session_state:
    st.session_state.user_role = None

# Database connection
db_file = 'my_database.db'
conn = sqlite3.connect(db_file)

# Query functions
def query_criteria_list(conn):
    cursor = conn.cursor()
    cursor.execute('''
        SELECT criteria, COUNT(paragraph)
        FROM energy_data
        GROUP BY criteria
    ''')
    return cursor.fetchall()

def query_energy_method_list(conn):
    cursor = conn.cursor()
    cursor.execute('''
        SELECT energy_method, COUNT(paragraph)
        FROM energy_data
        GROUP BY energy_method
    ''', )
    return cursor.fetchall()

def query_criteria_counts(conn):
    cursor = conn.cursor()
    cursor.execute('''
        SELECT criteria, COUNT(paragraph) as count
        FROM energy_data
        WHERE paragraph IS NOT NULL AND paragraph != '' AND paragraph != '0' AND paragraph != '0.0' AND status NOT IN ("pending", "rejected")
        GROUP BY criteria
    ''')
    return cursor.fetchall()

def query_energy_method_counts(conn, selected_criteria):
    cursor = conn.cursor()
    cursor.execute('''
        SELECT energy_method, COUNT(paragraph) as count
        FROM energy_data
        WHERE criteria = ? AND (paragraph IS NOT NULL AND paragraph != '' AND paragraph != '0' AND paragraph != '0.0' AND status NOT IN ("pending", "rejected")) 
        GROUP BY energy_method
    ''', (selected_criteria,))
    return cursor.fetchall()

def query_paragraphs(conn, criteria, energy_method, direction):
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, paragraph FROM energy_data
        WHERE criteria = ? AND energy_method = ? AND direction = ? AND status NOT IN ("pending", "rejected")
    ''', (criteria, energy_method, direction))
    paragraphs = cursor.fetchall()
    return [(id, para) for id, para in paragraphs if para not in ['0', '0.0', '', None]]

def admin_actions(conn, paragraph_id, new_text=None, delete=False):
    cursor = conn.cursor()
    if delete:
        cursor.execute("DELETE FROM energy_data WHERE id = ?", (paragraph_id,))
        conn.commit()
        st.success(f"Record {paragraph_id} deleted.")
    elif new_text:
        cursor.execute("UPDATE energy_data SET paragraph = ? WHERE id = ?", (new_text, paragraph_id))
        conn.commit()
        st.success(f"Record {paragraph_id} updated.")

# Login and Logout functions
def login(username, password):
    if username == admin_username and password == admin_password:
        st.session_state.logged_in = True
        st.session_state.current_user = username
        st.session_state.login_status = "Logged in successfully!"
        st.session_state.selected_direction = None
        st.rerun()  # Trigger a rerun on successful login
    else:
        st.warning("Incorrect username or password")

def logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]  # Clear all session states on logout
    st.rerun()

# Button to switch tabs

if st.session_state.logged_in:
    if st.session_state.current_user == "admin":
        tab_labels = ["SpatialBuild Energy", "Contribute", "Review Pending Data"]
        tabs = st.tabs(tab_labels) # Create tabs dynamically
        tab0, tab1, tab2= tabs #Assign each tab to a variable
    else:
        tab_labels = ["SpatialBuild Energy", "Contribute", "Your Contributions"]
        tabs = st.tabs(tab_labels)# Create tabs dynamically
        tab0, tab1, tab2 = tabs# Assign each tab to a variable
    
else:
    tab_labels = ["SpatialBuild Energy", "Contribute"]
    tabs = st.tabs(tab_labels)# Create tabs dynamically
    tab0, tab1 = tabs# Assign each tab to a variable

with tab1:
    st.title("We're making it better.")
    whats_next_html = ("""
Future updates will include new features like filters for climate and scale (urban vs. national) to fine-tune recommendations.</p> <strong>Contribute to the mission.</strong>
Log in or sign up to add your studies or references, sharing determinants, energy outputs, and their relationships. After review, your contributions will enhance the database, helping us grow this resource for urban planners, developers, and policymakers.</p>
Let's work together to optimize macro-scale energy use and create sustainable cities. <br><strong>Dive in, explore, and start contributing today.</strong>"""
    )
    st.markdown(whats_next_html, unsafe_allow_html=True)
    # Run this only once to set up the user table

    def initialize_user_table():
        conn = sqlite3.connect("my_database.db")
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT CHECK(role IN ('admin', 'user')) NOT NULL DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
    #initialize_user_table()

    def initialize_admin():
        admin_username = "admin"
        admin_password = os.getenv("ADMIN_PASSWORD", "default_admin_password")
        hashed_password = bcrypt.hashpw(admin_password.encode('utf-8'), bcrypt.gensalt())

        conn = sqlite3.connect("my_database.db")
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO users (username, password, role)
            VALUES (?, ?, 'admin')
        ''', (admin_username, hashed_password))
        conn.commit()
        conn.close()

    #initialize_admin()

    def signup():
        #st.header("Sign Up")
        username = st.text_input("Username", placeholder="Enter your username", key="signup_username")
        password = st.text_input("Password", type="password", placeholder="Enter your password", key="signup_password")
        if st.button("Sign Up"):
            if username and password:
                hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
                try:
                    conn = sqlite3.connect("my_database.db")
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO users (username, password, role)
                        VALUES (?, ?, 'user')
                    ''', (username, hashed_password))
                    conn.commit()
                    conn.close()
                    st.success("Account created successfully!")
                except sqlite3.IntegrityError:
                    st.error("Username already exists.")
            else:
                st.error("Please fill out all fields.")

    def login():
        #st.header("Login")
        username = st.text_input("Username", placeholder="Enter your username", key="login_username")
        password = st.text_input("Password", type="password", placeholder="Enter your password", key="login_password")
        if st.button("Login"):
            conn = sqlite3.connect("my_database.db")
            cursor = conn.cursor()
            cursor.execute("SELECT password, role FROM users WHERE username = ?", (username,))
            user = cursor.fetchone()
            conn.close()

            if user and bcrypt.checkpw(password.encode('utf-8'), user[0]):
                st.session_state.logged_in = True
                st.session_state.current_user = username
                st.session_state.user_role = user[1]
                st.success(f"Welcome, {username}!")
                st.rerun()
            else:
                st.error("Invalid username or password.")


    if "logged_in" in st.session_state and st.session_state.logged_in:
        if st.session_state.user_role == "admin":
            st.sidebar.header("Admin Dashboard") # Admin-specific functionality
            welcome_admin_dashboard = f"As Admin you can Add and Edit/Delete existing records under the SpatialBuild Energy tab.<br>You can accept or reject new user submissions under the Review Pending Contributions tab. New records and unlisted determinant/energy output types can be added to the dataset under the contribute tab.<br>"
            st.sidebar.write(welcome_admin_dashboard, unsafe_allow_html=True)
            contribute()
            with tab2:
                admin_dashboard() #show admin dashboard

            if st.sidebar.button("logout"):
                logout()
                st.rerun()

        elif st.session_state.user_role == "user":             # User-specific functionality
            st.sidebar.header(f"Weclome back {st.session_state.current_user}")
            welcome_user_dashboard = f"As a logged in user you can add your findings to the dataset under the contribute tab.<br>1. Select the relevant determinant.<br>2. Select energy output.<br>3. Select the relationship direction.<br>4. Add your entry and click Save.<br>Your entry will be submitted pending verification.<br>If your study references new or unlisted determinant/energy output types you can add them by choosing Add new determinant/Add new energy output."
            st.sidebar.write(welcome_user_dashboard, unsafe_allow_html=True)
            
            contribute()
            with tab2:
                user_dashboard() #show admin dashboard

            if st.sidebar.button("logout"):
                logout()
                st.rerun()

    else:
        #st.sidebar.header("Login or Sign Up")
        login_tab, signup_tab = st.tabs(["Login", "Sign Up"])
        with login_tab:
            login()
        with signup_tab:
            signup()



# How it works Tab with Criteria Dropdown and Simplified Direction Selection
#elif st.session_state.current_tab == "tab1":
with tab0:
    st.title("Welcome to SpatialBuild Energy")
    welcome_html = ("""<h7>This tool distills insights from over 200 studies on building energy consumption across meso and macro scales, spanning neighborhood, urban, state, regional, national, and global levels. It maps more than 100 factors influencing energy use, showing whether each increases or decreases energy outputs like total consumption, energy use intensity, or heating demand. Designed for urban planners and policymakers, the tool provides insights to craft smarter energy reduction strategies.</p><p><h7>"""
    )
    st.markdown(welcome_html, unsafe_allow_html=True)

    how_it_works_html = ("""
    1. Pick Your Focus: Choose the determinant you want to explore.<br>
    2. Select Energy Outputs: For example energy use intensity or heating demand from our database.<br>
    3. Filter the Results by the direction of the relationship (e.g., increases or decreases), and access the relevant studies with the links provided."""
    )
    st.markdown(how_it_works_html, unsafe_allow_html=True)

    # Criteria Dropdown with Counts and Placeholder
    # Initialize selected_direction in session state if not already set
    if 'selected_criteria_with_count' not in st.session_state:
        st.session_state.selected_criteria_with_count = None
    if 'selected_direction_with_count' not in st.session_state:
        st.session_state.selected_direction_with_count = None
    if 'selected_energy_method_with_count' not in st.session_state:
        st.session_state.selected_energy_method_with_count = None    

    criteria_counts = query_criteria_counts(conn)
    criteria_list = ["Select a determinant"] + [f"{row[0]} [{row[1]}]" for row in criteria_counts]
    selected_criteria_with_count = st.selectbox(
        "Determinant",
        criteria_list,
        index=0 if st.session_state.selected_criteria_with_count is None else criteria_list.index(f"{st.session_state.selected_criteria_with_count} [{[count for crit, count in criteria_counts if crit == st.session_state.selected_criteria][0]}]"),
        format_func=lambda x: x if x == "Select a determinant" else x
    )

    if selected_criteria_with_count != "Select a determinant":
        new_criteria = selected_criteria_with_count.split(" [")[0]
        if new_criteria != st.session_state.selected_criteria:
            st.session_state.selected_criteria = new_criteria
            st.session_state.selected_method = None  # Reset method on new criteria selection
            st.rerun()  # Trigger rerun to apply selection changes

        # Energy Method Dropdown with Counts and Placeholder
        energy_method_counts = query_energy_method_counts(conn, st.session_state.selected_criteria)
        method_list = ["Select an output"] + [f"{row[0]} [{row[1]}]" for row in energy_method_counts]

        selected_method_with_count = st.selectbox(
            "Energy Output(s)",
            method_list,
            index=0 if st.session_state.selected_method is None else method_list.index(f"{st.session_state.selected_method} [{[count for meth, count in energy_method_counts if meth == st.session_state.selected_method][0]}]"),
            format_func=lambda x: x if x == "Select an output" else x
        )

        if selected_method_with_count != "Select an output":
            st.session_state.selected_method = selected_method_with_count.split(" [")[0]
            
            # Query function to get the count for each direction
            def query_direction_counts(conn, selected_criteria, selected_method):
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT direction, COUNT(paragraph) as count
                    FROM energy_data
                    WHERE criteria = ? AND energy_method = ? AND paragraph IS NOT NULL AND paragraph != '' AND paragraph != '0' AND paragraph != '0.0' AND status NOT IN ("pending", "rejected")
                    GROUP BY direction
                ''', (selected_criteria, selected_method))
                return dict(cursor.fetchall())


            # Reset selected_direction when criteria or method changes
            new_criteria = selected_criteria_with_count.split(" [")[0] if selected_criteria_with_count != "Select a determinant" else None
            new_method = selected_method_with_count.split(" [")[0] if selected_method_with_count != "Select an output" else None

            # Reset selected_direction and rerun if criteria or method has changed
            if new_criteria != st.session_state.get("selected_criteria"):
                st.session_state.selected_criteria = new_criteria
                st.session_state.selected_method = None  # Reset method
                #st.session_state.selected_direction = None  # Reset direction
                st.rerun()
            elif new_method != st.session_state.get("selected_method"):
                st.session_state.selected_method = new_method
                #st.session_state.selected_direction = None  # Reset direction
                st.rerun()

            # Ensure criteria and method are selected before showing the direction choice
            if st.session_state.selected_method:
                # Fetch counts for each direction
                direction_counts = query_direction_counts(conn, st.session_state.selected_criteria, st.session_state.selected_method)
                increase_count = direction_counts.get("Increase", 0)
                decrease_count = direction_counts.get("Decrease", 0)

                # Display radio buttons with counts, without default selection
                selected_direction = st.radio(
                    "Please select the direction of the relationship",
                    [f"Increase [{increase_count}]", f"Decrease [{decrease_count}]"],
                    index= None,  # No preselection
                    key="selected_direction"
                )

                # Proceed only if a direction is selected
                if selected_direction:
                    # Remove count from selected direction (e.g., 'Increase' instead of 'Increase [5]')
                    direction_choice = selected_direction.split(" ")[0]

                # Continue with other functionality only if a direction is chosen
                #if st.session_state.get("selected_direction"):
                    paragraphs = query_paragraphs(conn, st.session_state.selected_criteria, st.session_state.selected_method, direction_choice)
                    
                    
                    # Display results or warning #The following study (or studies) shows that an increase ...
                    if paragraphs:
                        # Retrieve the count for the selected direction directly from the dictionary
                        selected_direction_count = st.session_state.selected_direction.split(" ")[1]

                        if selected_direction_count == "[1]":
                            st.markdown(f"<p><b>The following study shows that an increase (or presence) in {st.session_state.selected_criteria} leads to <i>{'higher' if st.session_state.selected_direction.startswith('Increase') else 'lower'}</i> {st.session_state.selected_method}.</b></p>", unsafe_allow_html=True)

                        else:
                            st.markdown(f"<p><b>The following studies show that an increase (or presence) in {st.session_state.selected_criteria} leads to <i>{'higher' if st.session_state.selected_direction.startswith('Increase') else 'lower'}</i> {st.session_state.selected_method}.</b></p>", unsafe_allow_html=True)


                        for count, (para_id, para_text) in enumerate(paragraphs, start=1):
                            # Admin options for logged in users
                            if st.session_state.user_role == "admin":
                                new_text = st.text_area(f"Edit text for record {para_id}", value=para_text, key=f"edit_{para_id}")
                                col1, col2 = st.columns([1, 4])
                                with col1:
                                    if st.button("Save changes", key=f"save_btn_{para_id}"):
                                        admin_actions(conn, para_id, new_text=new_text)
                                        st.rerun()
                                with col2:
                                    if st.session_state.get(f"confirm_delete_{para_id}", False):
                                        st.warning(f"Are you sure you want to delete record {para_id}?")
                                        col_yes, col_no = st.columns(2)
                                        with col_yes:
                                            if st.button("Yes", key=f"confirm_yes_{para_id}"):
                                                admin_actions(conn, para_id, delete=True)
                                                st.session_state[f"confirm_delete_{para_id}"] = False
                                                st.rerun()
                                        with col_no:
                                            if st.button("Cancel", key=f"confirm_no_{para_id}"):
                                                st.session_state[f"confirm_delete_{para_id}"] = False
                                                st.rerun()
                                    else:
                                        if st.button("Delete", key=f"delete_btn_{para_id}"):
                                            st.session_state[f"confirm_delete_{para_id}"] = True
                                            st.rerun()
                            else:
                                new_text = st.markdown(f"Result {count}:<br> {para_text}", unsafe_allow_html=True)
                    else:
                        st.warning(f"No studies have been reported for an increase (or presence) in {st.session_state.selected_criteria} leading to {'higher' if st.session_state.selected_direction == 'Increase' else 'lower'} {st.session_state.selected_method}.")
            
                    # Add New Record Section
                    if st.session_state.logged_in and direction_choice != None:
                        # Only show "Add New Record" button if the form is not currently active
                        if not st.session_state.get("show_new_record_form", False):
                            if st.button("Add New Record", key="add_new_record"):
                                st.session_state.show_new_record_form = True  # Show form once button is clicked

                        # Display the form only when 'show_new_record_form' is True
                        if st.session_state.get("show_new_record_form", False):
                            new_paragraph = st.text_area(
                                f"Add new record for {st.session_state.selected_criteria} and {st.session_state.selected_method} ({direction_choice})",
                                key="new_paragraph"
                            )
                            
                            # Show "Save" button within the form
                            if st.button("Save", key="save_new_record"):
                                # Save record only if text and direction are provided
                                if new_paragraph.strip() and direction_choice:
                                    cursor = conn.cursor()
                                    cursor.execute('''
                                        INSERT INTO energy_data (criteria, energy_method, direction, paragraph, status, user)
                                        VALUES (?, ?, ?, ?, ?, ?)
                                    ''', (st.session_state.selected_criteria, st.session_state.selected_method, direction_choice, new_paragraph, "pending", st.session_state.current_user))
                                    conn.commit()
                                    st.success("New record submitted successfully. Status: pending verification")
                                    
                                    # Hide the form and refresh to show the new record
                                    st.session_state.show_new_record_form = False  # Reset form state  
                                    time.sleep(2)                                  
                                    st.rerun()  # Refresh to display the new record immediately
                                else:
                                    st.warning("Please select a direction and ensure the record is not empty before saving.")

    st.image("bubblechart_placeholder.png")
    st.caption("Bubble chart visualizing studied determinants, energy outputs, and the direction of their relationships based on the literature.")

conn.close()

# Footer with fixed positioning
footer_html = """
    <style>
    .custom_footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: #010101;
        color: grey;
        text-align: center;
        padding: 5px;
    }
    </style>
    <div class="custom_footer">
        <p style='font-size:12px;'>If your study, or a study you are aware of, suggests any of these relationships are currently missing from the database, please email the study to ssk5573@psu.edu.<br> Your contribution will help further develop and improve this tool.</p>
    </div>
"""
#st.markdown(footer_html, unsafe_allow_html=True)

