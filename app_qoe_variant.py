import streamlit as st
import pandas as pd
import folium
from folium.plugins import Fullscreen
from streamlit_folium import st_folium
import json
import os
import io
import streamlit.components.v1 as components
import plotly.express as px
from st_supabase_connection import SupabaseConnection
import streamlit as st
from PIL import Image
import base64

# Function to read your image and convert it to a format HTML can understand
def get_base64_image(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

# Convert your icon
icon_base64 = get_base64_image("rgpm_icon.png")

custom_icon = Image.open("rgpm_icon.png") 

st.set_page_config(
    page_title="RGPM T6 Profiler", 
    page_icon=custom_icon
)


APP_DIR = os.path.dirname(os.path.abspath(__file__))

# --- AUTHENTICATION GATEKEEPER WITH BRANDING ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

try:
    supabase = st.connection("supabase", type=SupabaseConnection)
except Exception as e:
    st.error(f"Failed to connect to the cloud authentication server. Error: {e}")
    st.stop()

if not st.session_state.authenticated:
   # Custom CSS for the login screen
    st.markdown("""
        <style>
            /* Center the main block and restrict width for a card-like feel */
            .main .block-container {
                max-width: 550px;
                padding-top: 8vh;
            }
            
            /* Form Card Styling - Deep Dark Blue */
            [data-testid="stForm"] {
                background-color: #001b36 !important; 
                border: 1px solid #003b73 !important; 
                border-radius: 8px;
                padding: 25px;
                box-shadow: 0px 8px 16px rgba(0, 0, 0, 0.5);
            }

            /* FORCE FORM LABELS TO WHITE */
            [data-testid="stForm"] label p {
                color: #FFFFFF !important;
            }

            /* Clean up the tabs */
            .stTabs [data-baseweb="tab-list"] {
                gap: 24px;
                justify-content: center;
            }
            .stTabs [data-baseweb="tab"] {
                height: 50px;
                white-space: pre-wrap;
                background-color: transparent;
                border-radius: 4px 4px 0px 0px;
                gap: 1px;
                padding-top: 10px;
                padding-bottom: 10px;
            }
            
            /* Global Background Gradient */
            .stApp {
                background: linear-gradient(
                    to bottom right, 
                    rgba(0, 0, 139, 0.15),   
                    rgba(153, 255, 102, 0.20) 
                );
                background-attachment: fixed;
                background-size: cover;
            }
        </style>
    """, unsafe_allow_html=True)
     
    # Official Titles
    # Using flexbox to center and adding a text-shadow for the glow effect
    st.markdown(f"""
        <div style='display: flex; justify-content: center; align-items: center; gap: 15px; margin-bottom: 5px;'>
            <img src='data:image/png;base64,{icon_base64}' width='75'>
            <h1 style='margin: 0; padding: 0; text-shadow: 0px 0px 12px rgba(0, 88, 163, 0.7);'>RGPM T6 Profiler</h1>
        </div>
    """, unsafe_allow_html=True)
    
    # Your existing subtitle remains exactly the same
    st.markdown("<p style='text-align: center; color: #555; font-size: 16px; margin-top: 0px;'>Globe Telecom • Territory 6 (Visayas)<br>CEI & QoE Spatial Analysis Dashboard</p>", unsafe_allow_html=True)
    st.markdown("---")
    
    # Clean Tab Navigation instead of Radio Buttons
    tab1, tab2 = st.tabs(["🔒 Secure Log In", "📝 Request Access"])
    
    with tab1:
        with st.form("login_form"):
            email = st.text_input("Email Address")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Log In", use_container_width=True)
            
            if submit:
                try:
                    response = supabase.client.auth.sign_in_with_password({"email": email, "password": password})
                    if response.user:
                        st.session_state.authenticated = True
                        st.rerun()
                except Exception:
                    st.error("Invalid email or password. Please try again.")
    
    with tab2:
        with st.form("register_form"):
            st.info("New accounts require email verification before access is granted.")
            reg_email = st.text_input("Email Address")
            reg_password = st.text_input("Password (Min. 6 characters)", type="password")
            reg_submit = st.form_submit_button("Register Account", use_container_width=True)
            
            if reg_submit:
                if len(reg_password) < 6:
                    st.error("Password must be at least 6 characters long.")
                else:
                    try:
                        response = supabase.client.auth.sign_up({"email": reg_email, "password": reg_password})
                        if response.user:
                            st.success("✅ Registration initiated! Please check your email inbox to verify your account.")
                    except Exception as err:
                        st.error(f"Registration failed: {err}")
                        
    st.stop()
    
# Check if Streamlit caught an access token in the URL after a Google redirect
query_params = st.query_params
if "code" in query_params or "access_token" in query_params:
    st.session_state.authenticated = True
    # Clear the URL parameters so it looks clean
    st.query_params.clear()

# If the user is NOT logged in, show the Google login button and stop the app
if not st.session_state.authenticated:
    st.title("🔒 Restricted Access")
    st.markdown("Please log in with your authorized Google account to access the CEI & QOE Profiler Tool.")
    
    try:
        # Generate the secure Google OAuth URL from Supabase
        auth_response = supabase.client.auth.sign_in_with_oauth(
            {
                "provider": "google",
                "options": {
                    "redirect_to": "https://cei-qoe-profiler.streamlit.app/"
                }
            }
        )
        
        # Display the login button
        st.markdown(
            f"""
            <a href="{auth_response.url}" target="_self">
                <button style="background-color:#4285F4; color:white; padding:10px 24px; border:none; border-radius:4px; cursor:pointer; font-size:16px; font-weight:bold;">
                    Sign in with Google
                </button>
            </a>
            """,
            unsafe_allow_html=True
        )
    except Exception as e:
        st.error(f"Failed to load Google Authentication: {e}")
    
    # Halt execution so the rest of the dashboard doesn't load
    st.stop()

# --- STRICT DATA GOVERNANCE: PILOT CEI TEMPLATE VALIDATOR ---
def validate_cei_template(dataframe):
    """Enforces strict column headers to prevent processing errors."""
    required_columns = [
        "Province", "Town", "Brgy", "Monthly",
        "AVG CEI", "AVG Data CEI", "AVG Voice CEI",
        "AVG Stream QOE", "AVG Web QOE", "AVG Game QOE", "AVG Volte QOE"
    ]
    
    missing_cols = [col for col in required_columns if col not in dataframe.columns]
    has_psgc = any('PSGC' in str(col).upper() for col in dataframe.columns)
    
    if missing_cols or not has_psgc:
        error_msg = "🚨 **DATA VALIDATION FAILED**\n\n"
        error_msg += "The uploaded file deviates from the strict Pilot CEI format.\n\n"
        if missing_cols:
            error_msg += f"**Missing or Renamed Columns:**\n{', '.join(missing_cols)}\n\n"
        if not has_psgc:
            error_msg += "**Missing Identifier:**\nA column containing 'PSGC' is strictly required for spatial mapping.\n"
        return False, error_msg
    return True, ""


def _clean_columns(dataframe):
    dataframe = dataframe.copy()
    dataframe.columns = [str(column).strip() for column in dataframe.columns]
    return dataframe

def _find_column(dataframe, *names):
    lookup = {str(column).strip().upper(): column for column in dataframe.columns}
    return next((lookup.get(name.upper()) for name in names if lookup.get(name.upper())), None)

def _find_sheet(sheet_names, requested):
    key = lambda value: ''.join(char for char in str(value).upper() if char.isalnum())
    wanted = key(requested)
    return next((sheet for sheet in sheet_names if key(sheet) == wanted), None)

def _network_psgc(value):
    if pd.isna(value):
        return pd.NA
    text = str(value).strip().split('.')[0]
    if not text or text.lower() == 'nan':
        return pd.NA
    text = text.zfill(9)
    return text[:2] + '0' + text[2:] if len(text) == 9 else text

def _pla_id(value):
    if pd.isna(value):
        return pd.NA
    return str(value).strip().removesuffix('.0')

# --- MASTER XLSB CELL-SITE LOADER (BYTE-STREAM BASED) ---
@st.cache_data(ttl=3600, show_spinner="Loading cell-site network data. This may take a moment...")
def load_master_network_file(file_bytes):
    """Load map coordinates and network summaries from the master XLSB raw byte stream."""
    with pd.ExcelFile(io.BytesIO(file_bytes), engine="pyxlsb") as workbook:
        base_sheet = _find_sheet(workbook.sheet_names, "Technology per Site")
        if base_sheet is None:
            raise ValueError("Missing worksheet: Technology per Site")

        def base_columns(column):
            name = str(column).strip().upper()
            return name in {"PLA ID", "SITE NAME", "SITENAME", "LATITUDE", "LONGITUDE"} or "PSGC" in name

        base = _clean_columns(pd.read_excel(
            workbook, sheet_name=base_sheet, skiprows=1, usecols=base_columns
        ))
        pla_col = _find_column(base, "PLA ID")
        lat_col = _find_column(base, "LATITUDE")
        lon_col = _find_column(base, "LONGITUDE")
        if not all((pla_col, lat_col, lon_col)):
            raise ValueError("Technology per Site must contain PLA ID, Latitude, and Longitude columns.")

        if pla_col != "PLA ID":
            base.rename(columns={pla_col: "PLA ID"}, inplace=True)
        base["PLA ID"] = base["PLA ID"].map(_pla_id)
        base[lat_col] = pd.to_numeric(base[lat_col], errors="coerce")
        base[lon_col] = pd.to_numeric(base[lon_col], errors="coerce")
        for column in [column for column in base.columns if "PSGC" in column.upper()]:
            base[column] = base[column].map(_network_psgc)

        def sector_counts(technology):
            sheet = _find_sheet(workbook.sheet_names, technology)
            if sheet is None:
                return pd.DataFrame(columns=["PLA ID", f"{technology}_Sector_Count"])
            sector_df = _clean_columns(pd.read_excel(
                workbook, sheet_name=sheet, skiprows=1,
                usecols=lambda column: str(column).strip().upper() in {"PLA ID", "SECTOR NAME"},
            ))
            sector_pla = _find_column(sector_df, "PLA ID")
            sector_name = _find_column(sector_df, "SECTOR NAME")
            if sector_pla is None or sector_name is None:
                return pd.DataFrame(columns=["PLA ID", f"{technology}_Sector_Count"])
            sector_df["PLA ID"] = sector_df[sector_pla].map(_pla_id)
            return (sector_df.dropna(subset=["PLA ID"])
                    .groupby("PLA ID")[sector_name].nunique()
                    .rename(f"{technology}_Sector_Count").reset_index())

        for technology in ("2G", "4G", "5G"):
            base = base.merge(sector_counts(technology), on="PLA ID", how="left")

        decommissioned_only_sites = pd.DataFrame()
        decom_sheet = _find_sheet(workbook.sheet_names, "decommissioned")
        if decom_sheet:
            decom = _clean_columns(pd.read_excel(
                workbook, sheet_name=decom_sheet, skiprows=1,
                usecols=lambda column: str(column).strip().upper() in {
                    "PLA ID", "SITE NAME", "SITENAME", "LATITUDE", "LONGITUDE",
                    "TOWN PSGC", "BRGY PSGC", "SITE STATUS", "REASON OF DISMANTLING"
                },
            ))
            decom_pla = _find_column(decom, "PLA ID")
            status_col = _find_column(decom, "SITE STATUS")
            reason_col = _find_column(decom, "REASON OF DISMANTLING")
            decom_lat = _find_column(decom, "LATITUDE")
            decom_lon = _find_column(decom, "LONGITUDE")
            if decom_pla is not None and status_col is not None:
                statuses = pd.DataFrame({
                    "PLA ID": decom[decom_pla].map(_pla_id),
                    "SITE STATUS": decom[status_col],
                    "REASON OF DISMANTLING": decom[reason_col] if reason_col else pd.NA,
                }).dropna(subset=["PLA ID"]).drop_duplicates("PLA ID")
                base = base.merge(statuses, on="PLA ID", how="left")

                if decom_lat is not None and decom_lon is not None:
                    decommissioned_only_sites = pd.DataFrame({
                        "PLA ID": decom[decom_pla].map(_pla_id),
                        lat_col: pd.to_numeric(decom[decom_lat], errors="coerce"),
                        lon_col: pd.to_numeric(decom[decom_lon], errors="coerce"),
                        "SITE STATUS": decom[status_col],
                        "REASON OF DISMANTLING": decom[reason_col] if reason_col else pd.NA,
                    })

                    base_name_col = _find_column(base, "SITE NAME", "SITENAME")
                    decom_name_col = _find_column(decom, "SITE NAME", "SITENAME")
                    if base_name_col and decom_name_col:
                        decommissioned_only_sites[base_name_col] = decom[decom_name_col]

                    for base_psgc_col in [column for column in base.columns if "PSGC" in column.upper()]:
                        decom_psgc_col = _find_column(decom, base_psgc_col)
                        if decom_psgc_col:
                            decommissioned_only_sites[base_psgc_col] = decom[decom_psgc_col].map(_network_psgc)

                    decommissioned_only_sites = decommissioned_only_sites[
                        ~decommissioned_only_sites["PLA ID"].isin(base["PLA ID"])
                    ]

    for column in ("2G_Sector_Count", "4G_Sector_Count", "5G_Sector_Count"):
        base[column] = pd.to_numeric(base.get(column, 0), errors="coerce").fillna(0).astype(int)
    base["SITE STATUS"] = base["SITE STATUS"].fillna("Active") if "SITE STATUS" in base else "Active"
    if "REASON OF DISMANTLING" not in base:
        base["REASON OF DISMANTLING"] = pd.NA
    if not decommissioned_only_sites.empty:
        base = pd.concat([base, decommissioned_only_sites], ignore_index=True, sort=False)
    return base.dropna(subset=[lat_col, lon_col])


# --- LOGGED IN VIEW ---
# Add the Globe Telecom logo to the top of the sidebar
st.sidebar.image(
    "https://upload.wikimedia.org/wikipedia/en/thumb/f/fa/Globe_Telecom_logo.svg/512px-Globe_Telecom_logo.svg.png", 
    use_container_width=True
)
st.sidebar.markdown("---")

# --- SIDEBAR & DATA SOURCE SELECTION ---
st.sidebar.title("QOE PROFILER TOOL")
st.sidebar.markdown("---")

data_source = st.sidebar.radio(
    "Select Data Source:",
    ("Cloud Database (Default)", "Manual File Upload"),
    index=0 
)

df = pd.DataFrame()

if data_source == "Cloud Database (Default)":
    st.sidebar.caption("Browse and select datasets from Supabase Cloud Storage.")
    
    try:
        # 1. Dynamically fetch the list of files in the bucket
        bucket_files = supabase.client.storage.from_("qoe-data").list()
        
        # Extract just the file names, ignoring hidden system placeholders
        available_files = [file['name'] for file in bucket_files if file['name'] != '.emptyFolderPlaceholder']
        
        if not available_files:
            st.sidebar.warning("No files found in the 'qoe-data' bucket.")
        else:
            st.sidebar.markdown("**Select Cloud Files**")
            
            # 2. Use single-select dropdowns for both CEI and Network files to prevent map conflicts
            selected_cei = st.sidebar.selectbox(
                "Select QOE/CEI Data (Single File):", 
                ["--- Select File ---"] + available_files
            )
            
            selected_net = st.sidebar.selectbox(
                "Select Network Grouplist (XLSB):", 
                ["--- Select File ---"] + available_files
            )
            
            # 3. Add a button to execute the download only when the user is ready
            if st.sidebar.button("⬇️ Load Selected Cloud Data", use_container_width=True):
                if selected_cei == "--- Select File ---":
                    st.sidebar.error("Please select a CEI file.")
                elif selected_net == "--- Select File ---":
                    st.sidebar.error("Please select a Network Grouplist file.")
                else:
                    with st.spinner("Streaming selected files from Supabase..."):
                        try:
                            # Download the single CEI file
                            cei_bytes = supabase.client.storage.from_("qoe-data").download(selected_cei)
                            if selected_cei.endswith('.csv'):
                                st.session_state['cloud_df'] = pd.read_csv(io.BytesIO(cei_bytes))
                            else:
                                st.session_state['cloud_df'] = pd.read_excel(io.BytesIO(cei_bytes))
                            
                            # Execute Strict Data Validation
                            is_valid, error_msg = validate_cei_template(st.session_state['cloud_df'])
                            if not is_valid:
                                st.sidebar.error(error_msg)
                                del st.session_state['cloud_df'] # Drop the bad data
                                st.stop()
                            
                            # Download the single Network Grouplist
                            net_bytes = supabase.client.storage.from_("qoe-data").download(selected_net)
                            st.session_state['net_file_bytes'] = net_bytes
                            
                            st.rerun()
                        except Exception as exc:
                            st.sidebar.error(f"Error loading files: {exc}")
        
        # 4. If data is successfully loaded in memory, map it to the main dataframe
        if 'cloud_df' in st.session_state and 'net_file_bytes' in st.session_state:
            df = st.session_state['cloud_df']
            st.sidebar.success("✅ Cloud data loaded securely.")
            
    except Exception as e:
        st.sidebar.error(f"Failed to connect to the database. Error: {e}")

elif data_source == "Manual File Upload":
    st.sidebar.caption("Upload your primary CEI data here.")
    uploaded_cei_file = st.sidebar.file_uploader("Upload QOE/CEI Data (Single File)", type=['csv', 'xlsx', 'xls'], accept_multiple_files=False)
    
    st.sidebar.caption("Upload your Network Grouplist to view cell sites.")
    uploaded_net_file = st.sidebar.file_uploader("Upload Network Grouplist (XLSB)", type=['xlsb'])
    
    if uploaded_cei_file:
        try:
            if uploaded_cei_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_cei_file)
            else:
                df = pd.read_excel(uploaded_cei_file)
                
            # Execute Strict Data Validation
            is_valid, error_msg = validate_cei_template(df)
            if not is_valid:
                st.sidebar.error(error_msg)
                df = pd.DataFrame() # Drop the bad dataframe
                st.stop()
                
        except Exception as exc:
            st.sidebar.error(f"Error loading {uploaded_cei_file.name}: {exc}")
                
    if uploaded_net_file:
        st.session_state['net_file_bytes'] = uploaded_net_file.getvalue()
    else:
        st.session_state.pop('net_file_bytes', None)

# Halt execution if no data is loaded yet
if df.empty:
    # Render the logout button before halting if no data is present
    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Logout", key="logout_empty", use_container_width=True):
        st.session_state.authenticated = False
        supabase.client.auth.sign_out()
        st.rerun()
        
    st.warning("Please upload a file or connect to the database to begin profiling.")
    st.stop()

# --- CRITICAL PSGC CLEANING & YEAR PARSING ---
psgc_col = next((col for col in df.columns if 'PSGC' in col.upper()), None)

if psgc_col:
    def normalize_psgc(val):
        s = str(val).split('.')[0]
        if s == 'nan' or not s:
            return s
        s9 = s.zfill(9)
        if len(s9) == 9:
            return s9[:2] + '0' + s9[2:]
        return s9
    df[psgc_col] = df[psgc_col].apply(normalize_psgc)

if 'Monthly' in df.columns:
    df['Parsed_Date'] = pd.to_datetime(df['Monthly'], errors='coerce')
    df['Parsed_Year'] = df['Parsed_Date'].dt.year

# --- CASCADING SIDEBAR FILTERS ---
st.sidebar.markdown("### FILTERS")

if 'Parsed_Year' in df.columns and 'Monthly' in df.columns:
    years = ["All"] + sorted([str(int(y)) for y in df['Parsed_Year'].dropna().unique()])
    col_yr, col_mo = st.sidebar.columns(2)
    with col_yr:
        selected_year = st.selectbox("YEAR", years)
else:
    selected_year = "All"
    col_yr, col_mo = st.sidebar.columns(2)
    with col_yr:
        st.selectbox("YEAR", ["All"])

temp_df_yr = df.copy()
if selected_year != "All" and 'Parsed_Year' in temp_df_yr.columns:
    temp_df_yr = temp_df_yr[temp_df_yr['Parsed_Year'] == float(selected_year)]

if 'Monthly' in temp_df_yr.columns:
    months = ["All"] + temp_df_yr['Monthly'].dropna().unique().tolist()
    with col_mo:
        selected_month = st.selectbox("MONTH", months)
else:
    selected_month = "All"
    with col_mo:
        st.selectbox("MONTH", ["All"])

temp_df_mo = temp_df_yr.copy()
if selected_month != "All" and 'Monthly' in temp_df_mo.columns:
    temp_df_mo = temp_df_mo[temp_df_mo['Monthly'] == selected_month]

# Initialize decoupled session state keys for geographic filters
if 'map_province' not in st.session_state: st.session_state.map_province = "All"
if 'map_town' not in st.session_state: st.session_state.map_town = "All"
if 'map_brgy' not in st.session_state: st.session_state.map_brgy = "All"

if 'Province' in temp_df_mo.columns:
    provinces = ["All"] + sorted([str(p) for p in temp_df_mo['Province'].dropna().unique()])
    if st.session_state.map_province not in provinces:
        st.session_state.map_province = "All"
    
    prov_idx = provinces.index(st.session_state.map_province)
    selected_province = st.sidebar.selectbox("PROVINCE", provinces, index=prov_idx)
    
    if selected_province != st.session_state.map_province:
        st.session_state.map_province = selected_province
        st.session_state.map_town = "All"
        st.session_state.map_brgy = "All"
        st.rerun()
else:
    selected_province = "All"

temp_df_prov = temp_df_mo.copy()
if selected_province != "All" and 'Province' in temp_df_prov.columns:
    temp_df_prov = temp_df_prov[temp_df_prov['Province'] == selected_province]

if 'Town' in temp_df_prov.columns:
    towns = ["All"] + sorted([str(t) for t in temp_df_prov['Town'].dropna().unique()])
    if st.session_state.map_town not in towns:
        st.session_state.map_town = "All"
        
    town_idx = towns.index(st.session_state.map_town)
    selected_town = st.sidebar.selectbox("TOWN", towns, index=town_idx)
    
    if selected_town != st.session_state.map_town:
        st.session_state.map_town = selected_town
        st.session_state.map_brgy = "All"
        st.rerun()
else:
    selected_town = "All"

temp_df_town = temp_df_prov.copy()
if selected_town != "All" and 'Town' in temp_df_town.columns:
    temp_df_town = temp_df_town[temp_df_town['Town'] == selected_town]

if 'Brgy' in temp_df_town.columns:
    brgys = ["All"] + sorted([str(b) for b in temp_df_town['Brgy'].dropna().unique()])
    if st.session_state.map_brgy not in brgys:
        st.session_state.map_brgy = "All"
        
    brgy_idx = brgys.index(st.session_state.map_brgy)
    selected_brgy = st.sidebar.selectbox("BARANGAY", brgys, index=brgy_idx)
    
    if selected_brgy != st.session_state.map_brgy:
        st.session_state.map_brgy = selected_brgy
        st.rerun()
else:
    selected_brgy = "All"

filtered_df = temp_df_town.copy()
if selected_brgy != "All" and 'Brgy' in filtered_df.columns:
    filtered_df = filtered_df[filtered_df['Brgy'] == selected_brgy]

st.sidebar.markdown("### DASHBOARD SETTINGS")

with st.sidebar.expander("🌍 Map Styling", expanded=True):
    basemap_choice = st.selectbox(
        "Map Layout",
        ("OpenStreetMap (Colored)", "CartoDB Voyager", "CartoDB Positron"),
        index=2,
        help="Choose the background map style."
    )
    polygon_opacity = st.slider("Polygon Shading Opacity", 0.10, 0.90, 0.55, 0.05)
    polygon_border_opacity = st.slider("Polygon Border Opacity", 0.10, 1.00, 0.70, 0.05)

with st.sidebar.expander("📍 Site Markers", expanded=True):
    marker_icon_name = st.selectbox(
        "Marker Icon Shape",
        ["Map Pin", "Signal Bars", "WiFi", "Crosshairs", "Star"],
        index=0,
        help="Select the icon used to display cell sites on the map."
    )
    show_active = st.checkbox("Show Active Sites", value=False)
    show_decom = st.checkbox("Show Decommissioned Sites", value=False)

fa_icon_map = {
    "Map Pin": "map-pin",
    "Signal Bars": "signal",
    "WiFi": "wifi",
    "Crosshairs": "crosshairs",
    "Star": "star"
}
selected_fa_icon = fa_icon_map[marker_icon_name]

# --- LOGOUT BUTTON AT THE VERY BOTTOM ---
# This renders the button at the bottom of the filters if the data loaded successfully.
st.sidebar.markdown("---")
if st.sidebar.button("🚪 Logout", key="logout_full", use_container_width=True):
    st.session_state.authenticated = False
    supabase.client.auth.sign_out()
    st.rerun()

if filtered_df.empty:
    st.warning("No data available for the selected filters.")
    st.stop()

def get_avg(dataframe, col_name):
    if col_name in dataframe.columns:
        return dataframe[col_name].mean()
    return 0.0

# --- OFFLINE GEOJSON LOADING ---
@st.cache_data
def load_local_geojson(level):
    folder_name = "geojson_data"
    file_map = {'brgy': 'visayas_barangays.geojson', 'town': 'municipalities.geojson', 'province': 'provinces.geojson'}
    filename = file_map.get(level)
    if not filename: return None
    base_dir = os.path.dirname(__file__)
    file_path = os.path.join(base_dir, folder_name, filename)
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

if 'Brgy' in df.columns: master_geo_data = load_local_geojson('brgy')
elif 'Town' in df.columns: master_geo_data = load_local_geojson('town')
else: master_geo_data = load_local_geojson('province')

# --- MAIN DASHBOARD LAYOUT ---
col1, col2 = st.columns([1, 2.5]) 

with col1:
    st.subheader("PERFORMANCE METRICS")
    st.caption("Averages based on current filter selection.")
    st.markdown("---")
    st.markdown("**CUSTOMER EXPERIENCE INDEX (CEI)**")
    st.metric("Overall AVG CEI", f"{get_avg(filtered_df, 'AVG CEI'):.2f}")
    
    cei_col1, cei_col2 = st.columns(2)
    with cei_col1: st.metric("Data CEI", f"{get_avg(filtered_df, 'AVG Data CEI'):.2f}")
    with cei_col2: st.metric("Voice CEI", f"{get_avg(filtered_df, 'AVG Voice CEI'):.2f}")

    st.markdown("---")
    st.markdown("**QUALITY OF EXPERIENCE (QoE)**")
    
    qoe_col1, qoe_col2 = st.columns(2)
    with qoe_col1:
        st.metric("Stream QoE", f"{get_avg(filtered_df, 'AVG Stream QOE'):.2f}")
        st.metric("Web QoE", f"{get_avg(filtered_df, 'AVG Web QOE'):.2f}")
    with qoe_col2:
        st.metric("Game QoE", f"{get_avg(filtered_df, 'AVG Game QOE'):.2f}")
        st.metric("VoLTE QoE", f"{get_avg(filtered_df, 'AVG Volte QOE'):.2f}")

with col2:
    header_col, popup_col = st.columns([3, 1])
    with header_col:
        st.subheader("Geographic Profiling Map")
    
    if st.session_state.get('net_file_bytes') is None and (show_active or show_decom):
        st.warning("⚠️ Please upload the Network Grouplist (XLSB) file in the sidebar to view cell site markers.")

    tile_map = {
        "OpenStreetMap (Colored)": "OpenStreetMap",
        "CartoDB Voyager": "CartoDB Voyager",
        "CartoDB Positron": "CartoDB positron",
    }
    
    m = folium.Map(location=[12.8797, 121.7740], zoom_start=6, tiles=tile_map[basemap_choice])
    Fullscreen(position='topleft', force_separate_button=True).add_to(m)
    
    if psgc_col and master_geo_data and not filtered_df.empty:
        active_psgcs = set(filtered_df[psgc_col].tolist())
        overall_avg_cei = round(get_avg(filtered_df, 'AVG CEI'), 2)
        
        filtered_geo_features = []
        for feature in master_geo_data['features']:
            props = feature['properties']
            raw_psgc = props.get('psgc_code')
            psgc_match = raw_psgc in active_psgcs if raw_psgc else False
            
            adm_code = (props.get('adm4_pcode') or props.get('ADM4_PCODE') or 
                        props.get('adm3_pcode') or props.get('ADM3_PCODE') or 
                        props.get('adm2_pcode') or props.get('ADM2_PCODE') or '')
            
            adm_match = False
            clean_adm = ""
            if adm_code and adm_code.startswith('PH'):
                clean_adm = adm_code[2:].ljust(10, '0')
                adm_match = clean_adm in active_psgcs
            
            if psgc_match or adm_match:
                matched_key = raw_psgc if psgc_match else clean_adm
                loc_df = filtered_df[filtered_df[psgc_col] == matched_key]
                loc_name = (props.get('adm4_name') or props.get('ADM4_EN') or 
                            props.get('adm3_name') or props.get('ADM3_EN') or 
                            props.get('adm2_name') or props.get('ADM2_EN') or 'Unknown Location')
                
                feature['properties']['unified_key'] = matched_key
                feature['properties']['Location'] = loc_name
                feature['properties']['Avg_CEI'] = round(loc_df['AVG CEI'].mean(), 2) if not loc_df.empty else overall_avg_cei
                feature['properties']['Data_CEI'] = round(loc_df['AVG Data CEI'].mean(), 2) if not loc_df.empty else 0.0
                feature['properties']['Voice_CEI'] = round(loc_df['AVG Voice CEI'].mean(), 2) if not loc_df.empty else 0.0
                
                filtered_geo_features.append(feature)
        
        lightweight_geo_data = {"type": "FeatureCollection", "features": filtered_geo_features}

        filtered_sites = pd.DataFrame()
        if st.session_state.get('net_file_bytes') is not None:
            try:
                site_coords_df = load_master_network_file(st.session_state['net_file_bytes'])
                
                if not site_coords_df.empty:
                    site_psgc_cols = [column for column in site_coords_df.columns if "PSGC" in column.upper()]
                    lat_col = _find_column(site_coords_df, "LATITUDE")
                    lon_col = _find_column(site_coords_df, "LONGITUDE")
                    name_col = _find_column(site_coords_df, "SITE NAME", "SITENAME")
                    
                    if site_psgc_cols and lat_col and lon_col:
                        site_mask = pd.Series(False, index=site_coords_df.index)
                        for site_psgc_col in site_psgc_cols:
                            site_mask = site_mask | site_coords_df[site_psgc_col].isin(active_psgcs)
                        filtered_sites = site_coords_df[site_mask].copy()
                        
                        is_active_site = filtered_sites["SITE STATUS"].astype(str).str.upper().eq("ACTIVE")
                        if show_active and not show_decom:
                            filtered_sites = filtered_sites[is_active_site]
                        elif show_decom and not show_active:
                            filtered_sites = filtered_sites[~is_active_site]
                        elif not show_active and not show_decom:
                            filtered_sites = filtered_sites.iloc[0:0]
            except Exception as network_error:
                st.error(f"Unable to process cell-site data: {network_error}")

        with popup_col:
            with st.popover("📊 View Cell Site Data", use_container_width=True):
                if filtered_sites.empty:
                    st.info("No cell-site data is available for this selection.")
                else:
                    st.markdown("**Filtered Cell Site Data**")
                    st.dataframe(filtered_sites, use_container_width=True, height=400)

        if lightweight_geo_data['features']:
            choro = folium.Choropleth(
                geo_data=lightweight_geo_data,
                name="choropleth", data=filtered_df, columns=[psgc_col, 'AVG CEI'], 
                key_on="feature.properties.unified_key", fill_color="YlGnBu",
                fill_opacity=polygon_opacity, line_opacity=polygon_border_opacity, 
                legend_name="Average CEI Score", highlight=True
            ).add_to(m)
            
            tooltip = folium.features.GeoJsonTooltip(fields=['Location', 'Avg_CEI'], aliases=['Location:', 'Overall CEI:'], style="background-color: white; color: #333333; font-family: arial; padding: 8px;")
            choro.geojson.add_child(tooltip)
            
            if not filtered_sites.empty:
                for _, row in filtered_sites.iterrows():
                    status = str(row.get("SITE STATUS", "Active"))
                    is_active = status.upper() == "ACTIVE"
                    site_name = row.get(name_col, "Unknown Site") if name_col else "Unknown Site"
                    tooltip_html = (
                        f"<b>Site:</b> {site_name}<br>"
                        f"<b>Status:</b> {status}<br>"
                        f"<b>2G Sectors:</b> {row.get('2G_Sector_Count', 0)}<br>"
                        f"<b>4G Sectors:</b> {row.get('4G_Sector_Count', 0)}<br>"
                        f"<b>5G Sectors:</b> {row.get('5G_Sector_Count', 0)}"
                    )
                    if not is_active:
                        tooltip_html += f"<br><b>Reason:</b> {row.get('REASON OF DISMANTLING', 'N/A')}"
                    marker_color = "red" if is_active else "lightgray"
                    
                    folium.Marker(
                        location=[row[lat_col], row[lon_col]],
                        icon=folium.Icon(
                            color=marker_color, 
                            icon=selected_fa_icon, 
                            prefix="fa"
                        ),
                        tooltip=tooltip_html,
                    ).add_to(m)
            
            ui_styles = """<style>
            svg.leaflet-control.legend, .legend {background-color: rgba(255, 255, 255, 0.9) !important; border-radius: 8px !important; padding: 15px !important; box-shadow: 0 2px 6px rgba(0,0,0,0.4) !important; margin-top: 15px !important; margin-right: 15px !important;}
            .leaflet-control-attribution {display: none !important;}
            .leaflet-control-layer-preview {background: white; border: 2px solid rgba(0,0,0,0.2); border-radius: 4px; cursor: pointer; padding: 4px 7px; font-size: 16px; margin-top: 6px !important; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center;}
            .leaflet-div-icon {background: transparent !important; border: none !important;}
            .site-marker-icon {transform: scale(var(--site-marker-scale, 0.9)); transform-origin: center; transition: transform 0.15s ease; opacity: 0.95;}
            </style>"""
            m.get_root().html.add_child(folium.Element(ui_styles))
            
            click_and_reset_js = """
            <script>
            function bindMapInteractions() {
                var folium_map = null;
                for (var key in window) {
                    if (key.startsWith("map_") && window[key] instanceof L.Map) {
                        folium_map = window[key];
                        break;
                    }
                }

                if (!folium_map) return false;

                function updateMarkerScale() {
                    var zoom = folium_map.getZoom();
                    var scale = zoom <= 4 ? 0.55 : zoom <= 6 ? 0.7 : zoom <= 8 ? 0.85 : 1.0;
                    document.documentElement.style.setProperty('--site-marker-scale', scale);
                }

                folium_map.on('zoomend', updateMarkerScale);
                updateMarkerScale();

                var all_features = [];
                var selected_feature = null;
                
                folium_map.eachLayer(function(layer) {
                    if (layer.feature && layer.setStyle) {
                        all_features.push(layer);
                        if (!layer.originalStyle) {
                            layer.originalStyle = {
                                color: layer.options.color,
                                fillColor: layer.options.fillColor,
                                weight: layer.options.weight,
                                opacity: layer.options.opacity,
                                fillOpacity: layer.options.fillOpacity
                            };
                        }
                    }
                });

                if (all_features.length === 0) return false;

                function restoreOriginalColors() {
                    all_features.forEach(function(layer) {
                        if (layer.originalStyle) {
                            layer.setStyle(layer.originalStyle);
                        }
                    });
                }

                function applyGrayscaleState() {
                    all_features.forEach(function(layer) {
                        if (selected_feature && layer === selected_feature) {
                            layer.setStyle({
                                fillColor: layer.originalStyle.fillColor,
                                color: '#ff0000',
                                weight: 4,
                                fillOpacity: 0.9,
                                opacity: 1
                            });
                        } else {
                            layer.setStyle({
                                fillColor: '#cccccc',
                                color: '#d3d3d3',
                                fillOpacity: 0.7,
                                opacity: 0.4,
                                weight: 1
                            });
                        }
                    });
                }

                if (!folium_map._layerControlAdded) {
                    var layerControl = L.control({ position: 'topleft' });
                    layerControl.onAdd = function(map) {
                        var div = L.DomUtil.create('div', 'leaflet-control-layer-preview');
                        div.innerHTML = '🔘';
                        div.title = 'Hold to view original colors';
                        
                        L.DomEvent.disableClickPropagation(div);

                        L.DomEvent.on(div, 'mousedown touchstart', function(e) {
                            restoreOriginalColors();
                        });

                        L.DomEvent.on(div, 'mouseup mouseleave touchend', function(e) {
                            applyGrayscaleState();
                        });

                        return div;
                    };
                    layerControl.addTo(folium_map);
                    folium_map._layerControlAdded = true;
                }

                folium_map.eachLayer(function(layer) {
                    if (layer.feature && layer.setStyle) {
                        layer.on('mouseover', function() {
                            selected_feature = layer;
                            applyGrayscaleState();
                        });
                        layer.on('mouseout', function() {
                            selected_feature = null;
                            restoreOriginalColors();
                        });
                    }
                });

                return true;
            }

            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', bindMapInteractions);
            } else {
                bindMapInteractions();
            }
            </script>
            """
            m.get_root().html.add_child(folium.Element(click_and_reset_js))
            m.fit_bounds(m.get_bounds())
        else:
            st.info("No matching map boundaries found for the current data selection.")

    # Render map and listen for clicks on the choropleth polygons
    map_output = st_folium(
        m, 
        use_container_width=True, 
        height=700, 
        returned_objects=["last_active_drawing"]
    )

    # Process the click event
    if map_output and map_output.get("last_active_drawing"):
        clicked_location = map_output["last_active_drawing"]["properties"].get("Location")

        if clicked_location:
            needs_rerun = False
            
            # 1. Did they click a Province?
            if 'Province' in df.columns and clicked_location in df['Province'].values:
                if st.session_state.map_province != clicked_location:
                    st.session_state.map_province = clicked_location
                    st.session_state.map_town = "All"
                    st.session_state.map_brgy = "All"
                    needs_rerun = True
                    
            # 2. Did they click a Town?
            elif 'Town' in df.columns and clicked_location in df['Town'].values:
                if st.session_state.map_town != clicked_location:
                    # Backfill the Province
                    if 'Province' in df.columns:
                        parent_province = df[df['Town'] == clicked_location]['Province'].dropna().iloc[0]
                        st.session_state.map_province = str(parent_province)
                    
                    st.session_state.map_town = clicked_location
                    st.session_state.map_brgy = "All"
                    needs_rerun = True
                    
            # 3. Did they click a Barangay?
            elif 'Brgy' in df.columns and clicked_location in df['Brgy'].values:
                if st.session_state.map_brgy != clicked_location:
                    # Backfill both Province and Town
                    match_row = df[df['Brgy'] == clicked_location].iloc[0]
                    
                    if 'Province' in df.columns:
                        st.session_state.map_province = str(match_row['Province'])
                    if 'Town' in df.columns:
                        st.session_state.map_town = str(match_row['Town'])
                        
                    st.session_state.map_brgy = clicked_location
                    needs_rerun = True

            # Force the dashboard to reload with the fully synchronized constraints
            if needs_rerun:
                st.rerun()


# --- TABBED DATA VIEW SECTION ---
st.markdown("---")
tab_custom_css = """<style>div[data-baseweb="tab-list"] {border-bottom: 2px solid #000000 !important;} button[data-baseweb="tab"] {border: 2px solid #a0a0a0 !important; border-radius: 8px 8px 0px 0px !important; padding: 12px 24px !important; margin-right: 6px !important; font-weight: 900 !important; font-size: 18px !important; background-color: #f1f3f6 !important; color: #555555 !important;} button[data-baseweb="tab"][aria-selected="true"] {border: 2px solid #000000 !important; border-bottom: 3px solid #ffffff !important; background-color: #ffffff !important; color: #000000 !important;}</style>"""
st.markdown(tab_custom_css, unsafe_allow_html=True)

tab_chart, tab_data = st.tabs(["Performance Trend Line Chart", "Raw Data File"])

with tab_chart:
    avg_columns = [col for col in filtered_df.columns if 'AVG' in col.upper()]
    time_col = 'Monthly' if 'Monthly' in filtered_df.columns else None

    if avg_columns and time_col:
        st.markdown("**Select metrics to display on the chart:**")
        cols = st.columns(min(len(avg_columns), 4))
        selected_metrics = []
        for idx, col_name in enumerate(avg_columns):
            with cols[idx % len(cols)]:
                if st.checkbox(col_name, value=(idx == 0), key=f"chk_{col_name}"):
                    selected_metrics.append(col_name)
        
        if selected_metrics:
            st.markdown("---")
            agg_view = st.radio("Timeline View:", ["Monthly (Continuous)", "Year-over-Year (Overlaid Compare)"], horizontal=True)
            chart_data = filtered_df.copy()
            chart_data['Parsed_Date'] = pd.to_datetime(chart_data[time_col], errors='coerce')
            
            if agg_view == "Year-over-Year (Overlaid Compare)":
                chart_data['Month_Num'] = chart_data['Parsed_Date'].dt.month
                chart_data['Month'] = chart_data['Parsed_Date'].dt.strftime('%b')
                chart_data['Year'] = chart_data['Parsed_Date'].dt.year.astype(str)
                grouped = chart_data.groupby(['Month_Num', 'Month', 'Year'])[selected_metrics].mean().reset_index()
                pivot_df = pd.pivot_table(grouped, values=selected_metrics, index=['Month_Num', 'Month'], columns=['Year'])
                pivot_df.columns = [f"{metric} ({year})" for metric, year in pivot_df.columns]
                pivot_df = pivot_df.sort_index(level='Month_Num').reset_index(level='Month')
                pivot_df.index = pivot_df['Month']
                pivot_df.drop(columns=['Month'], inplace=True)
                pivot_df = pivot_df.round(2)
                
                fig = px.line(pivot_df, markers=True, color_discrete_sequence=px.colors.qualitative.Set1, labels={"value": "Score", "variable": "Metric", "Month": "Month"})
                fig.update_traces(hovertemplate="%{y:.2f}")
                fig.update_layout(xaxis_title="Month", yaxis_title="Average Score", hovermode="x unified", xaxis=dict(tickmode="linear", tickangle=-45, showgrid=True, gridcolor="rgba(128, 128, 128, 0.1)", griddash="dot"), yaxis=dict(showgrid=True, gridcolor="rgba(128, 128, 128, 0.1)", griddash="dot"), margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig, use_container_width=True)
            else:
                chart_data = chart_data.groupby('Parsed_Date')[selected_metrics].mean().reset_index()
                chart_data = chart_data.sort_values(by='Parsed_Date').round(2) 
                
                fig = px.line(chart_data, x='Parsed_Date', y=selected_metrics, markers=True, color_discrete_sequence=px.colors.qualitative.Set1, labels={"value": "Score", "variable": "Metric", "Parsed_Date": "Month"})
                fig.update_traces(hovertemplate="%{y:.2f}")
                fig.update_layout(xaxis_title="Timeline", yaxis_title="Average Score", hovermode="x unified", xaxis=dict(tickformat="%b %Y", ticklabelmode="period", dtick="M1", tickangle=-45, showgrid=True, gridcolor="rgba(128, 128, 128, 0.1)", griddash="dot"), yaxis=dict(showgrid=True, gridcolor="rgba(128, 128, 128, 0.1)", griddash="dot"), margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Please select at least one metric checkbox above to render the trend line chart.")
    else:
        st.caption("Trend line chart unavailable: Missing time or metric columns.")
                                  
with tab_data:
    st.write("**RAW DATA VIEW:**")
    st.dataframe(filtered_df, use_container_width=True)