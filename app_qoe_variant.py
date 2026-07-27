import streamlit as st
import pandas as pd
import folium
from folium.plugins import Fullscreen
from streamlit_folium import st_folium
import json
import os
import io
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import plotly.express as px

# 1. Page Configuration
st.set_page_config(layout="wide", page_title="CEI & QOE Profiler")

# --- DEFINE GLOBAL STREAMLIT DECORATORS HERE ---
@st.cache_resource
def get_oauth_cache():
    return {}

@st.dialog("Browse Google Drive", width="large")
def drive_file_picker_modal(drive_service):
    # 1. Initialize Browser-Style History Stack
    if 'drive_history' not in st.session_state:
        st.session_state['drive_history'] = [('root', 'My Drive')]
        st.session_state['history_idx'] = 0

    # --- STATE CALLBACK FUNCTIONS ---
    def go_back():
        st.session_state['history_idx'] -= 1

    def go_forward():
        st.session_state['history_idx'] += 1

    def open_folder(folder_id, folder_name):
        idx = st.session_state['history_idx']
        st.session_state['drive_history'] = st.session_state['drive_history'][:idx+1]
        st.session_state['drive_history'].append((folder_id, folder_name))
        st.session_state['history_idx'] += 1
    # --------------------------------

    idx = st.session_state['history_idx']
    curr_id, curr_name = st.session_state['drive_history'][idx]

    # Global Search Bar
    search_term = st.text_input("🔍 Search Drive for a file:", placeholder="Type a filename...")
    st.markdown("---")

    # Navigation Controls
    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        st.button("⬅️ Back", disabled=(idx == 0), on_click=go_back, use_container_width=True)
    with col2:
        st.button("➡️ Forward", disabled=(idx == len(st.session_state['drive_history']) - 1), on_click=go_forward, use_container_width=True)
    with col3:
        if not search_term:
            st.caption(f"📍 **Location:** {curr_name}")
        else:
            st.caption("📍 **Location:** Global Search Results")

    st.markdown("---")

    # Strict MIME types for files we can process
    valid_mimes = (
        "(mimeType='application/vnd.google-apps.spreadsheet' or "
        "mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' or "
        "mimeType='text/csv')"
    )

    try:
        if search_term:
            query = f"name contains '{search_term}' and {valid_mimes} and trashed=false"
        else:
            query = f"'{curr_id}' in parents and (mimeType='application/vnd.google-apps.folder' or {valid_mimes}) and trashed=false"
            
        results = drive_service.files().list(
            q=query,
            pageSize=1000,
            fields="nextPageToken, files(id, name, mimeType)",
            orderBy="folder, name"
        ).execute()
        
        items = results.get('files', [])
        
        folders = [item for item in items if item['mimeType'] == 'application/vnd.google-apps.folder']
        data_files = [item for item in items if item['mimeType'] != 'application/vnd.google-apps.folder']
        
        if folders and not search_term:
            st.markdown("**Folders**")
            for f in folders:
                st.button(f"📁 {f['name']}", key=f"folder_{f['id']}", use_container_width=True, on_click=open_folder, args=(f['id'], f['name']))
        
        st.markdown("**Data Files (Sheets, Excel, CSV)**")
        if data_files:
            file_dict = {f['name']: f for f in data_files}
            selected_file = st.radio("Select a file:", list(file_dict.keys()), label_visibility="collapsed")
            
            if st.button("✅ Load Data", use_container_width=True, type="primary"):
                st.session_state['selected_sheet_id'] = file_dict[selected_file]['id']
                st.session_state['selected_sheet_name'] = file_dict[selected_file]['name']
                st.session_state['selected_sheet_mime'] = file_dict[selected_file]['mimeType']
                
                del st.session_state['drive_history']
                del st.session_state['history_idx']
                
                st.rerun()
        else:
            st.info("No supported data files found.")
            
    except Exception as e:
        st.error(f"Error reading Drive: {e}")
# ------------------------------------------------

st.sidebar.title("QOE PROFILER TOOL")
st.sidebar.markdown("---")

# 1. State Management for the Radio Button
if "source_selection" not in st.session_state:
    if 'code' in st.query_params or 'google_creds' in st.session_state:
        st.session_state["source_selection"] = "Connect via Google"
    else:
        st.session_state["source_selection"] = "Manual File Upload"

data_source = st.sidebar.radio(
    "Select Data Source:",
    ("Manual File Upload", "Connect via Google"),
    key="source_selection" 
)

df = pd.DataFrame()

if data_source == "Manual File Upload":
    st.sidebar.caption("Ensure your Excel/CSV files contain a PSGC Code column. Upload up to 5 files.")
    uploaded_files = st.sidebar.file_uploader("Upload QOE/CEI Data (Max 5)", type=['csv', 'xlsx', 'xls'], accept_multiple_files=True)
    
    if uploaded_files:
        if len(uploaded_files) > 5:
            st.sidebar.error("Error: You can upload a maximum of 5 files at a time.")
        else:
            temp_dfs = []
            for uploaded_file in uploaded_files:
                try:
                    if uploaded_file.name.endswith('.csv'):
                        temp_df = pd.read_csv(uploaded_file)
                    else:
                        temp_df = pd.read_excel(uploaded_file)
                    temp_dfs.append(temp_df)
                except Exception as exc:
                    st.sidebar.error(f"Error loading {uploaded_file.name}: {exc}")
            
            if temp_dfs:
                df = pd.concat(temp_dfs, ignore_index=True)

elif data_source == "Connect via Google":
    st.sidebar.caption("Authenticate to browse your Google Sheets.")
    
    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets.readonly',
        'https://www.googleapis.com/auth/drive.metadata.readonly',
        'https://www.googleapis.com/auth/drive.readonly' 
    ]
    
    oauth_cache = get_oauth_cache()
    
    if not os.path.exists('client_secret.json'):
        st.sidebar.error("Missing client_secret.json file.")
    else:
        REDIRECT_URI = 'http://localhost:8501/' 
        
        flow = Flow.from_client_secrets_file(
            'client_secret.json',
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI
        )

        # Handle Login Flow
        if 'google_creds' not in st.session_state:
            if 'code' not in st.query_params:
                auth_url, state = flow.authorization_url(prompt='consent')
                if hasattr(flow, 'code_verifier'):
                    oauth_cache[state] = flow.code_verifier
                st.sidebar.markdown(f"**[Login with Google]({auth_url})**")
            else:
                try:
                    code = st.query_params['code']
                    state = st.query_params.get('state')
                    if state in oauth_cache:
                        flow.code_verifier = oauth_cache[state]
                        
                    flow.fetch_token(code=code)
                    st.session_state['google_creds'] = flow.credentials
                    st.query_params.clear()
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(f"Authentication error: {e}")
                    
        # Handle the File Picker Trigger
        if 'google_creds' in st.session_state:
            creds = st.session_state['google_creds']
            try:
                drive_service = build('drive', 'v3', credentials=creds)
                sheets_service = build('sheets', 'v4', credentials=creds)
                
                st.sidebar.success("Secure connection established.")
                
                if st.sidebar.button("📂 Browse Google Drive", use_container_width=True):
                    drive_file_picker_modal(drive_service)
                
                # Process the data if a file was successfully selected
                if 'selected_sheet_id' in st.session_state and 'google_df' not in st.session_state:
                    selected_id = st.session_state['selected_sheet_id']
                    sheet_name = st.session_state['selected_sheet_name']
                    mime_type = st.session_state.get('selected_sheet_mime', '')
                    
                    with st.spinner(f"Downloading {sheet_name}..."):
                        try:
                            # ROUTE 1: Native Google Sheets
                            if mime_type == 'application/vnd.google-apps.spreadsheet':
                                result = sheets_service.spreadsheets().values().get(
                                    spreadsheetId=selected_id, 
                                    range='Sheet1!A:Z'
                                ).execute()
                                
                                values = result.get('values', [])
                                if values:
                                    st.session_state['google_df'] = pd.DataFrame(values[1:], columns=values[0])
                                    st.rerun()
                                else:
                                    st.sidebar.warning("The selected Google Sheet is empty.")
                                    del st.session_state['selected_sheet_id']
                            
                            # ROUTE 2: Binary Excel or CSV Files
                            else:
                                request = drive_service.files().get_media(fileId=selected_id)
                                file_content = request.execute()
                                
                                if mime_type == 'text/csv' or sheet_name.lower().endswith('.csv'):
                                    st.session_state['google_df'] = pd.read_csv(io.BytesIO(file_content))
                                else:
                                    st.session_state['google_df'] = pd.read_excel(io.BytesIO(file_content))
                                st.rerun()
                        
                        except Exception as dl_error:
                            st.sidebar.error(f"Download Error: Ensure 'Sheet1' exists if using Google Sheets. {dl_error}")
                            del st.session_state['selected_sheet_id']
                            
            except Exception as e:
                st.sidebar.error(f"API error: {e}")

    # Lock in the final data
    if 'google_df' in st.session_state:
        df = st.session_state['google_df']
        st.sidebar.info(f"Loaded: **{st.session_state.get('selected_sheet_name', 'Google Sheet')}**")

# Halt execution if no data is loaded yet
if df.empty:
    st.warning("Please upload a file or authenticate via Google to begin profiling.")
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
# ----------------------------------------------

# 4. Cascading Sidebar Controls (Hierarchical Filtering)
st.sidebar.markdown("### FILTERS")

# Filter A: Year & Month Side-by-Side
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

# Subset dataframe based on Year selection first
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

# Subset dataframe further based on Month selection
temp_df_mo = temp_df_yr.copy()
if selected_month != "All" and 'Monthly' in temp_df_mo.columns:
    temp_df_mo = temp_df_mo[temp_df_mo['Monthly'] == selected_month]

# Filter B: Province
if 'Province' in temp_df_mo.columns:
    provinces = ["All"] + temp_df_mo['Province'].dropna().unique().tolist()
    selected_province = st.sidebar.selectbox("PROVINCE", provinces)
else:
    selected_province = "All"

temp_df_prov = temp_df_mo.copy()
if selected_province != "All" and 'Province' in temp_df_prov.columns:
    temp_df_prov = temp_df_prov[temp_df_prov['Province'] == selected_province]

# Filter C: Town
if 'Town' in temp_df_prov.columns:
    towns = ["All"] + temp_df_prov['Town'].dropna().unique().tolist()
    selected_town = st.sidebar.selectbox("TOWN", towns)
else:
    selected_town = "All"

temp_df_town = temp_df_prov.copy()
if selected_town != "All" and 'Town' in temp_df_town.columns:
    temp_df_town = temp_df_town[temp_df_town['Town'] == selected_town]

# Filter D: Barangay
if 'Brgy' in temp_df_town.columns:
    brgys = ["All"] + temp_df_town['Brgy'].dropna().unique().tolist()
    selected_brgy = st.sidebar.selectbox("BARANGAY", brgys)
else:
    selected_brgy = "All"

# 5. Apply Final Cascaded Filters to Main Dataset
filtered_df = temp_df_town.copy()
if selected_brgy != "All" and 'Brgy' in filtered_df.columns:
    filtered_df = filtered_df[filtered_df['Brgy'] == selected_brgy]

if filtered_df.empty:
    st.warning("No data available for the selected filters.")
    st.stop()

def get_avg(dataframe, col_name):
    if col_name in dataframe.columns:
        return dataframe[col_name].mean()
    return 0.0

# --- OFFLINE GEOJSON LOADING & FILTERING ---
@st.cache_data
def load_local_geojson(level):
    folder_name = "geojson_data"
    
    file_map = {
        'brgy': 'visayas_barangays.geojson',
        'town': 'municipalities.geojson',
        'province': 'provinces.geojson'
    }
    
    filename = file_map.get(level)
    if not filename:
        return None
        
    base_dir = os.path.dirname(__file__)
    file_path = os.path.join(base_dir, folder_name, filename)
    
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        st.sidebar.error(f"Missing map file: Could not find {filename} in the {folder_name} folder.")
        return None

if 'Brgy' in df.columns:
    master_geo_data = load_local_geojson('brgy')
elif 'Town' in df.columns:
    master_geo_data = load_local_geojson('town')
else:
    master_geo_data = load_local_geojson('province')
# ------------------------------------------

# 6. Main Dashboard Layout
col1, col2 = st.columns([1, 2.5]) 

with col1:
    st.subheader("PERFORMANCE METRICS")
    st.caption("Averages based on current filter selection.")
    
    st.markdown("---")
    st.markdown("**CUSTOMER EXPERIENCE INDEX (CEI)**")
    
    # 1. Main Overall Metric
    st.metric(
        label="Overall AVG CEI", 
        value=f"{get_avg(filtered_df, 'AVG CEI'):.2f}",
        help="**Source:** Derived directly from the 'AVG CEI' column in your dataset.\n\n**Calculation:** The arithmetic mean (average) of all overall CEI scores matching your current Year, Month, and Location filters."
    )
    
    cei_col1, cei_col2 = st.columns(2)
    with cei_col1:
        st.metric(
            label="Data CEI", 
            value=f"{get_avg(filtered_df, 'AVG Data CEI'):.2f}",
            help="**Source:** 'AVG Data CEI' column.\n\n**Calculation:** The calculated average of data-specific customer experience index scores across the filtered selection."
        )
    with cei_col2:
        st.metric(
            label="Voice CEI", 
            value=f"{get_avg(filtered_df, 'AVG Voice CEI'):.2f}",
            help="**Source:** 'AVG Voice CEI' column.\n\n**Calculation:** The calculated average of voice-specific customer experience index scores across the filtered selection."
        )

    st.markdown("---")
    st.markdown("**QUALITY OF EXPERIENCE (QoE)**")
    
    qoe_col1, qoe_col2 = st.columns(2)
    with qoe_col1:
        st.metric(
            label="Stream QoE", 
            value=f"{get_avg(filtered_df, 'AVG Stream QOE'):.2f}",
            help="**Source:** 'AVG Stream QOE' column.\n\n**Calculation:** The mean score representing the video and audio streaming quality of experience."
        )
        st.metric(
            label="Web QoE", 
            value=f"{get_avg(filtered_df, 'AVG Web QOE'):.2f}",
            help="**Source:** 'AVG Web QOE' column.\n\n**Calculation:** The mean score representing the web browsing quality of experience."
        )
    with qoe_col2:
        st.metric(
            label="Game QoE", 
            value=f"{get_avg(filtered_df, 'AVG Game QOE'):.2f}",
            help="**Source:** 'AVG Game QOE' column.\n\n**Calculation:** The mean score representing the mobile gaming quality of experience."
        )
        st.metric(
            label="VoLTE QoE", 
            value=f"{get_avg(filtered_df, 'AVG Volte QOE'):.2f}",
            help="**Source:** 'AVG Volte QOE' column.\n\n**Calculation:** The mean score representing the Voice over LTE network quality of experience."
        )

with col2:
    st.subheader("Geographic Profiling Map")
    
    m = folium.Map(location=[12.8797, 121.7740], zoom_start=6, tiles="CartoDB positron")
    
    Fullscreen(
        position='topleft',
        title='Expand me',
        title_cancel='Exit me',
        force_separate_button=True
    ).add_to(m)
    
    if psgc_col and master_geo_data and not filtered_df.empty:
        active_psgcs = set(filtered_df[psgc_col].tolist())
        
        # Centralized calculation for overall CEI consistency
        overall_avg_cei = round(get_avg(filtered_df, 'AVG CEI'), 2)
        
        filtered_geo_features = []
        for feature in master_geo_data['features']:
            props = feature['properties']
            
            # 1. Try to find the exact PSGC code
            raw_psgc = props.get('psgc_code')
            psgc_match = raw_psgc in active_psgcs if raw_psgc else False
            
            # 2. Try to find the ADM PCODE
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
                
                # 3. Get Location Name
                loc_name = (props.get('adm4_name') or props.get('ADM4_EN') or 
                            props.get('adm3_name') or props.get('ADM3_EN') or 
                            props.get('adm2_name') or props.get('ADM2_EN') or 'Unknown Location')
                
                feature['properties']['unified_key'] = matched_key
                feature['properties']['Location'] = loc_name
                
                # --- ALIGNED OVERALL CEI (Using Mean Across Grouped Subset) ---
                feature['properties']['Avg_CEI'] = round(loc_df['AVG CEI'].mean(), 2) if not loc_df.empty else overall_avg_cei
                feature['properties']['Data_CEI'] = round(loc_df['AVG Data CEI'].mean(), 2) if not loc_df.empty else 0.0
                feature['properties']['Voice_CEI'] = round(loc_df['AVG Voice CEI'].mean(), 2) if not loc_df.empty else 0.0
                
                filtered_geo_features.append(feature)
        
        lightweight_geo_data = {
            "type": "FeatureCollection",
            "features": filtered_geo_features
        }
        
        if lightweight_geo_data['features']:
            # 1. Base Choropleth with Native Hover Highlighting
            choro = folium.Choropleth(
                geo_data=lightweight_geo_data,
                name="choropleth",
                data=filtered_df,
                columns=[psgc_col, 'AVG CEI'], 
                key_on="feature.properties.unified_key", 
                fill_color="YlGnBu",
                fill_opacity=0.8,
                line_opacity=0.5,
                legend_name="Average CEI Score",
                missing_kwds={'color': 'lightgrey'},
                highlight=True
            ).add_to(m)
            
            # 2. Hover Tooltip
            tooltip = folium.features.GeoJsonTooltip(
                fields=['Location', 'Avg_CEI'],
                aliases=['Location:', 'Overall CEI:'],
                style="background-color: white; color: #333333; font-family: arial; font-size: 13px; padding: 8px; border-radius: 4px; box-shadow: 2px 2px 5px rgba(0,0,0,0.3);"
            )
            choro.geojson.add_child(tooltip)
            
            # 3. Click Popup
            popup = folium.features.GeoJsonPopup(
                fields=['Location', 'Avg_CEI', 'Data_CEI', 'Voice_CEI'],
                aliases=['Location:', 'Overall CEI:', 'Data CEI:', 'Voice CEI:'],
                style="font-family: arial; font-size: 12px; font-weight: bold;",
                max_width=250
            )
            choro.geojson.add_child(popup)
            
            # 4. Legend & Popup Styling + Layer Control Position Fix
            ui_styles = """
            <style>
            svg.leaflet-control.legend, .legend {
                background-color: rgba(255, 255, 255, 0.9) !important;
                border-radius: 8px !important;
                padding: 15px !important;
                box-shadow: 0 2px 6px rgba(0,0,0,0.4) !important;
                margin-top: 15px !important; 
                margin-right: 15px !important;
            }
            .leaflet-popup {
                margin-bottom: 40px !important;
            }
            /* Hide Leaflet Attribution Watermark */
            .leaflet-control-attribution {
                display: none !important;
            }
            /* Layer Icon positioned directly below the Fullscreen Control Icon */
            .leaflet-control-layer-preview {
                background: white;
                border: 2px solid rgba(0,0,0,0.2);
                border-radius: 4px;
                cursor: pointer;
                padding: 4px 7px;
                font-size: 16px;
                box-shadow: 0 1px 5px rgba(0,0,0,0.4);
                text-align: center;
                user-select: none;
                margin-top: 6px !important; /* Stacked right under Fullscreen */
                width: 30px;
                height: 30px;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .leaflet-control-layer-preview:hover {
                background: #f4f4f4;
            }
            </style>
            """
            m.get_root().html.add_child(folium.Element(ui_styles))
            
            # 5. Press-and-Hold Original Color Preview & Grayscale Toggle JavaScript
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
                        div.innerHTML = '🥞';
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

                all_features.forEach(function(layer) {
                    layer.off('click');
                    
                    layer.on('click', function(e) {
                        selected_feature = e.target;
                        applyGrayscaleState();
                        
                        if (!L.Browser.ie && !L.Browser.opera && !L.Browser.edge) {
                            e.target.bringToFront();
                        }
                    });
                });

                folium_map.off('click');
                folium_map.on('click', function(e) {
                    selected_feature = null;
                    restoreOriginalColors();
                });
                
                return true;
            }

            var checkMapExists = setInterval(function() {
                if (bindMapInteractions()) {
                    clearInterval(checkMapExists);
                }
            }, 500);
            </script>
            """
            m.get_root().html.add_child(folium.Element(click_and_reset_js))
            
            m.fit_bounds(m.get_bounds())
        else:
            st.info("No matching map boundaries found for the current data selection.")
    else:
        st.info(f"Ensure you have a PSGC column in your data and the local .geojson files are placed in the 'geojson_data' folder.")

    st_folium(m, use_container_width=True, height=700, returned_objects=[])


# --- TABBED DATA VIEW SECTION ---
st.markdown("---")

tab_custom_css = """
<style>
div[data-baseweb="tab-list"] {
    border-bottom: 2px solid #000000 !important;
}

button[data-baseweb="tab"] {
    border: 2px solid #a0a0a0 !important;
    border-radius: 8px 8px 0px 0px !important;
    padding: 12px 24px !important;
    margin-right: 6px !important;
    font-weight: 900 !important;
    font-size: 18px !important;
    background-color: #f1f3f6 !important;
    color: #555555 !important;
}

button[data-baseweb="tab"][aria-selected="true"] {
    border: 2px solid #000000 !important;
    border-bottom: 3px solid #ffffff !important;
    background-color: #ffffff !important;
    color: #000000 !important;
}
</style>
"""
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
            col_target = cols[idx % len(cols)]
            with col_target:
                is_checked = st.checkbox(col_name, value=(idx == 0), key=f"chk_{col_name}")
                if is_checked:
                    selected_metrics.append(col_name)
        
        if selected_metrics:
            st.markdown("---")
            agg_view = st.radio(
                "Timeline View:", 
                ["Monthly (Continuous)", "Year-over-Year (Overlaid Compare)"], 
                horizontal=True
            )
            
            chart_data = filtered_df.copy()
            chart_data['Parsed_Date'] = pd.to_datetime(chart_data[time_col], errors='coerce')
            
            if agg_view == "Year-over-Year (Overlaid Compare)":
                chart_data['Month_Num'] = chart_data['Parsed_Date'].dt.month
                chart_data['Month'] = chart_data['Parsed_Date'].dt.strftime('%b')
                chart_data['Year'] = chart_data['Parsed_Date'].dt.year.astype(str)
                
                grouped = chart_data.groupby(['Month_Num', 'Month', 'Year'])[selected_metrics].mean().reset_index()
                
                pivot_df = pd.pivot_table(
                    grouped,
                    values=selected_metrics,
                    index=['Month_Num', 'Month'],
                    columns=['Year']
                )
                
                pivot_df.columns = [f"{metric} ({year})" for metric, year in pivot_df.columns]
                pivot_df = pivot_df.sort_index(level='Month_Num')
                pivot_df = pivot_df.reset_index(level='Month')
                pivot_df.index = pivot_df['Month']
                pivot_df.drop(columns=['Month'], inplace=True)
                
                pivot_df = pivot_df.round(2)
                
                fig = px.line(
                    pivot_df, 
                    markers=True,
                    color_discrete_sequence=px.colors.qualitative.Set1,
                    labels={"value": "Score", "variable": "Metric", "Month": "Month"} 
                )
                
                fig.update_traces(hovertemplate="%{y:.2f}")
                
                fig.update_layout(
                    xaxis_title="Month",
                    yaxis_title="Average Score",
                    legend_title_text="Metrics by Year",
                    hovermode="x unified",
                    xaxis=dict(
                        tickmode="linear", 
                        tickangle=-45,
                        showgrid=True,
                        gridcolor="rgba(128, 128, 128, 0.1)",
                        griddash="dot"
                    ),
                    yaxis=dict(
                        showgrid=True,
                        gridcolor="rgba(128, 128, 128, 0.1)",
                        griddash="dot"
                    ),
                    margin=dict(l=0, r=0, t=30, b=0)
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
            else:
                chart_data = chart_data.groupby('Parsed_Date')[selected_metrics].mean().reset_index()
                chart_data = chart_data.sort_values(by='Parsed_Date')
                
                chart_data = chart_data.round(2) 
                
                fig = px.line(
                    chart_data, 
                    x='Parsed_Date', 
                    y=selected_metrics,
                    markers=True,
                    color_discrete_sequence=px.colors.qualitative.Set1,
                    labels={"value": "Score", "variable": "Metric", "Parsed_Date": "Month"} 
                )
                
                fig.update_traces(hovertemplate="%{y:.2f}")
                
                fig.update_layout(
                    xaxis_title="Timeline",
                    yaxis_title="Average Score",
                    legend_title_text="Metrics Overlay",
                    hovermode="x unified",
                    xaxis=dict(
                        tickformat="%b %Y", 
                        ticklabelmode="period",
                        dtick="M1",        
                        tickangle=-45,
                        showgrid=True,
                        gridcolor="rgba(128, 128, 128, 0.1)",
                        griddash="dot"
                    ),
                    yaxis=dict(
                        showgrid=True,
                        gridcolor="rgba(128, 128, 128, 0.1)",
                        griddash="dot"
                    ),
                    margin=dict(l=0, r=0, t=30, b=0)
                )
                
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Please select at least one metric checkbox above to render the trend line chart.")
    else:
        st.caption("Trend line chart unavailable: Missing 'Monthly' time column or numeric 'AVG' performance metrics in the dataset.")
                                  
with tab_data:
    st.write("**RAW DATA VIEW:**")
    st.dataframe(filtered_df, use_container_width=True)