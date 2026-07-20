import streamlit as st
import pandas as pd
import folium
from folium.plugins import Fullscreen
from streamlit_folium import st_folium
import json
import os

# 1. Page Configuration
st.set_page_config(layout="wide", page_title="CEI & QOE Profiler")

# 2. Sidebar File Uploader
st.sidebar.title("QOE PROFILER TOOL")
st.sidebar.markdown("---")
st.sidebar.caption("Ensure your Excel file contains a PSGC Code column.")
uploaded_file = st.sidebar.file_uploader("Upload QOE/CEI Data (CSV/Excel)", type=['csv', 'xlsx', 'xls'])

# 3. Data Loading & Cleaning
@st.cache_data
def load_data(file):
    if file is not None:
        try:
            if file.name.endswith('.csv'):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)
            return df
        except Exception as exc:
            st.sidebar.error(f"Error loading file: {exc}")
    return pd.DataFrame()

df = load_data(uploaded_file)

if df.empty:
    st.warning("Please upload a valid CEI/QOE Excel or CSV file to begin profiling.")
    st.stop()

# --- CRITICAL PSGC CLEANING ---
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
# ------------------------------

# 4. Dynamic Sidebar Controls
if 'Monthly' in df.columns:
    months = ["All"] + df['Monthly'].dropna().unique().tolist()
    selected_month = st.sidebar.selectbox("MONTH", months)
else:
    selected_month = "All"

if 'Province' in df.columns:
    provinces = ["All"] + df['Province'].dropna().unique().tolist()
    selected_province = st.sidebar.selectbox("PROVINCE", provinces)
else:
    selected_province = "All"

if 'Town' in df.columns:
    towns = ["All"] + df['Town'].dropna().unique().tolist()
    selected_town = st.sidebar.selectbox("TOWN", towns)
else:
    selected_town = "All"

if 'Brgy' in df.columns:
    brgys = ["All"] + df['Brgy'].dropna().unique().tolist()
    selected_brgy = st.sidebar.selectbox("BARANGAY", brgys)
else:
    selected_brgy = "All"

# 5. Apply Filters
filtered_df = df.copy()
if selected_month != "All" and 'Monthly' in filtered_df.columns:
    filtered_df = filtered_df[filtered_df['Monthly'] == selected_month]
if selected_province != "All" and 'Province' in filtered_df.columns:
    filtered_df = filtered_df[filtered_df['Province'] == selected_province]
if selected_town != "All" and 'Town' in filtered_df.columns:
    filtered_df = filtered_df[filtered_df['Town'] == selected_town]
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
        'brgy': 'barangays.geojson',
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
    avg_cei = get_avg(filtered_df, 'AVG CEI')
    st.metric(label="Overall AVG CEI", value=f"{avg_cei:.2f}")
    st.write(f"**AVG Data CEI:** {get_avg(filtered_df, 'AVG Data CEI'):.2f}")
    st.write(f"**AVG Voice CEI:** {get_avg(filtered_df, 'AVG Voice CEI'):.2f}")

    st.markdown("---")
    st.markdown("**QUALITY OF EXPERIENCE (QoE)**")
    st.write(f"**AVG Stream QOE:** {get_avg(filtered_df, 'AVG Stream QOE'):.2f}")
    st.write(f"**AVG Game QOE:** {get_avg(filtered_df, 'AVG Game QOE'):.2f}")
    st.write(f"**AVG Web QOE:** {get_avg(filtered_df, 'AVG Web QOE'):.2f}")
    st.write(f"**AVG Volte QOE:** {get_avg(filtered_df, 'AVG Volte QOE'):.2f}")

with col2:
    st.subheader("Geographic Profiling Map")
    
    m = folium.Map(location=[12.8797, 121.7740], zoom_start=6)
    
    # --- ADD FULLSCREEN BUTTON HERE ---
    Fullscreen(
        position='topright',
        title='Expand me',
        title_cancel='Exit me',
        force_separate_button=True
    ).add_to(m)
    # ----------------------------------
    
    if psgc_col and master_geo_data and not filtered_df.empty:
        active_psgcs = set(filtered_df[psgc_col].tolist())
        
        filtered_geo_features = []
        for feature in master_geo_data['features']:
            props = feature['properties']
            
            psgc_match = props.get('psgc_code') in active_psgcs
            
            adm_code = props.get('ADM4_PCODE', props.get('ADM3_PCODE', props.get('ADM2_PCODE', '')))
            adm_match = False
            clean_adm = ""
            if adm_code and adm_code.startswith('PH'):
                clean_adm = adm_code[2:].ljust(10, '0')
                adm_match = clean_adm in active_psgcs
            
            if psgc_match or adm_match:
                matched_key = props.get('psgc_code') if psgc_match else clean_adm
                feature['properties']['unified_key'] = matched_key
                filtered_geo_features.append(feature)
        
        lightweight_geo_data = {
            "type": "FeatureCollection",
            "features": filtered_geo_features
        }
        
        if lightweight_geo_data['features']:
            folium.Choropleth(
                geo_data=lightweight_geo_data,
                name="choropleth",
                data=filtered_df,
                columns=[psgc_col, 'AVG CEI'], 
                key_on="feature.properties.unified_key", 
                fill_color="YlGnBu",
                fill_opacity=0.8,
                line_opacity=0.5,
                legend_name="Average CEI Score",
                missing_kwds={'color': 'lightgrey'}
            ).add_to(m)
            
            m.fit_bounds(m.get_bounds())
        else:
            st.info("No matching map boundaries found for the current data selection.")
    else:
        st.info(f"Ensure you have a PSGC column in your data and the local .geojson files are placed in the 'geojson_data' folder.")

    st_folium(m, use_container_width=True, height=700)

# --- FULL-WIDTH RAW DATA VIEW ---
st.markdown("---")
st.write("**RAW DATA VIEW:**")
st.dataframe(filtered_df, use_container_width=True)