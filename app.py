import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime
import numpy as np

# --- 1. CONFIGURATION & SETUP ---
st.set_page_config(page_title="Real Exchange Rate Analyzer", page_icon="💱", layout="wide")

# Curated list of major IMF countries including the Euro Area (G163)
COUNTRIES = {
    "G163": "Euro Area", "USA": "United States", "GBR": "United Kingdom",
    "JPN": "Japan", "CAN": "Canada", "AUS": "Australia", "CHE": "Switzerland",
    "CHN": "China", "IND": "India", "BRA": "Brazil", "MEX": "Mexico",
    "ZAF": "South Africa", "KOR": "South Korea", "SGP": "Singapore",
    "NZL": "New Zealand", "SWE": "Sweden", "NOR": "Norway", "DNK": "Denmark",
    "ARG": "Argentina", "TUR": "Turkey", "IDN": "Indonesia", 
    "SAU": "Saudi Arabia", "EGY": "Egypt", "NGA": "Nigeria"
}

# --- 2. DATA FETCHING FUNCTION ---
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_imf_data(iso3, key_template, is_fx=False):
    """Fetches IMF data using the provided API hint. Raises exceptions on failure."""
    if iso3 == "USA" and is_fx:
        # USA USD per USD exchange rate is implicitly 1.0
        dates = pd.date_range('1976-01-01', datetime.date.today(), freq='MS')
        return pd.Series(1.0, index=dates, name='value')

    key = key_template.format(ISO3=iso3)
    url = f"https://api.imf.org/external/sdmx/3.0/data/IFS/{key}?startPeriod=1976-01"
    
    headers = {'Accept': 'application/vnd.sdmx.data+json'}
    response = requests.get(url, headers=headers, timeout=15)
    
    if response.status_code != 200:
        raise ConnectionError(f"IMF API returned status code {response.status_code} for {COUNTRIES[iso3]} ({iso3}).")
        
    data = response.json()
    
    # Recursive generator to flexibly find typical SDMX JSON time-series observations
    def extract_obs(node):
        if isinstance(node, dict):
            if '@TIME_PERIOD' in node and '@OBS_VALUE' in node:
                yield node['@TIME_PERIOD'], node['@OBS_VALUE']
            elif 'TIME_PERIOD' in node and 'OBS_VALUE' in node:
                yield node['TIME_PERIOD'], node['OBS_VALUE']
            for v in node.values():
                yield from extract_obs(v)
        elif isinstance(node, list):
            for item in node:
                yield from extract_obs(item)
    
    extracted = list(extract_obs(data))
    if not extracted:
        raise ValueError(f"No valid time-series data found in the IMF payload for {COUNTRIES[iso3]} ({iso3}).")
        
    dates = [x[0] for x in extracted]
    values = [float(x[1]) for x in extracted]
    
    df = pd.DataFrame({'date': dates, 'value': values})
    # Parse to monthly start 'MS'
    df['date'] = pd.to_datetime(df['date'] + '-01', format='%Y-%m-%d', errors='coerce')
    df = df.dropna().sort_values('date').set_index('date')
    return df['value']

# --- 3. MAIN UI LAYOUT ---
st.title("🌍 Real Exchange Rate (RER) Analyzer")
st.markdown("Analyze the Real and Nominal Exchange Rates dynamically between any two countries.")

# Sidebar Configuration
with st.sidebar:
    st.header("⚙️ Settings")
    c1 = st.selectbox("Country 1 (Base Currency)", options=list(COUNTRIES.keys()), 
                      format_func=lambda x: f"{x} - {COUNTRIES[x]}", index=list(COUNTRIES.keys()).index("USA"))
    
    c2 = st.selectbox("Country 2 (Target Currency)", options=list(COUNTRIES.keys()), 
                      format_func=lambda x: f"{x} - {COUNTRIES[x]}", index=list(COUNTRIES.keys()).index("G163"))
    
    st.divider()
    start_date = st.date_input("Start Month", datetime.date(1976, 1, 1), min_value=datetime.date(1976, 1, 1))
    end_date = st.date_input("End Month", datetime.date.today(), min_value=datetime.date(1976, 1, 1))
    
    st.divider()
    plot_type = st.radio("Select Plot Type", ["Real", "Nominal", "Both"])
    
    st.markdown("---")
    st.markdown("### Methodology")
    st.latex(r"S(t) = \frac{\text{Country}_2}{\text{Country}_1}")
    st.latex(r"RER(t) = S(t) \times \frac{P_1(t)}{P_2(t)}")
    st.latex(r"\text{Index}(t) = 100 \times \frac{RER(t)}{RER^*}")

# --- 4. DATA PROCESSING ---
with st.spinner("Fetching IMF API data..."):
    cpi_key_tpl = "{ISO3}.CPI._T.IX.M"
    fx_key_tpl = "{ISO3}.XDC_USD.PA_RT.M"

    try:
        p1_series = fetch_imf_data(c1, cpi_key_tpl, is_fx=False)
        p2_series = fetch_imf_data(c2, cpi_key_tpl, is_fx=False)
        exc1_series = fetch_imf_data(c1, fx_key_tpl, is_fx=True)
        exc2_series = fetch_imf_data(c2, fx_key_tpl, is_fx=True)
    except Exception as e:
        st.error(f"🚨 **Data Fetch Error:** {str(e)}")
        st.info("The IMF API may be temporarily down, or data for the selected countries might be missing/unavailable. Please try different countries or try again later.")
        st.stop()

    # Master DataFrame
    df = pd.DataFrame(index=pd.date_range(start='1976-01-01', end=datetime.date.today(), freq='MS'))
    df = df.join(p1_series.rename('P1'))
    df = df.join(p2_series.rename('P2'))
    df = df.join(exc1_series.rename('EXC1'))
    df = df.join(exc2_series.rename('EXC2'))

    # Forward fill missing data, then backward fill to fix initial gaps
    df.ffill(inplace=True)
    df.bfill(inplace=True)

    # S(t): units of Country 2 currency per 1 unit of Country 1 currency
    # Since EXC is Local / USD: 1 C1 = EXC2 / EXC1 units of C2.
    df['S'] = df['EXC2'] / df['EXC1']

    # RER(t) = S(t) * P1(t) / P2(t)
    df['RER'] = df['S'] * (df['P1'] / df['P2'])

    # Filter data based on user dates
    mask = (df.index.date >= start_date) & (df.index.date <= end_date)
    df_sample = df.loc[mask].copy()

    # RER* = Average over valid selected months
    valid_rer = df_sample['RER'].dropna()
    if not valid_rer.empty:
        rer_star = valid_rer.mean()
        # Real Index(t) calculation
        df_sample['Real_Index'] = 100 * df_sample['RER'] / rer_star
    else:
        df_sample['Real_Index'] = np.nan

# --- 5. PLOTTING ---
if df_sample.empty:
    st.warning("No data available for the selected date range.")
else:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    if plot_type in ["Real", "Both"]:
        fig.add_trace(go.Scatter(x=df_sample.index, y=df_sample['Real_Index'], 
                                 name="Real Index (RER)", line=dict(color='#2E86C1', width=2)), secondary_y=False)
        
    if plot_type in ["Nominal", "Both"]:
        sec_y = True if plot_type == "Both" else False
        fig.add_trace(go.Scatter(x=df_sample.index, y=df_sample['S'], 
                                 name=f"Nominal S(t) [{c2}/{c1}]", line=dict(color='#E74C3C', width=2)), secondary_y=sec_y)

    fig.update_layout(
        title=f"Exchange Rates: {COUNTRIES[c1]} vs {COUNTRIES[c2]}",
        template="plotly_white",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    if plot_type == "Both":
        fig.update_yaxes(title_text="Real Index (Average = 100)", secondary_y=False, color="#2E86C1")
        fig.update_yaxes(title_text=f"Nominal ({c2}/{c1})", secondary_y=True, color="#E74C3C")
    elif plot_type == "Real":
        fig.update_yaxes(title_text="Real Index (Average = 100)", color="#2E86C1")
    else:
        fig.update_yaxes(title_text=f"Nominal ({c2}/{c1})", color="#E74C3C")
        
    st.plotly_chart(fig, use_container_width=True)

# --- 6. DATA EXPORT ---
st.markdown("### ") # Spacing
with st.expander("📊 View Data & Download"):
    st.dataframe(df_sample[['P1', 'P2', 'EXC1', 'EXC2', 'S', 'RER', 'Real_Index']].style.format("{:.4f}"), use_container_width=True)
    
    csv_data = df_sample.to_csv(index_label="Date").encode('utf-8')
    st.download_button(
        label="📥 Download Data as CSV",
        data=csv_data,
        file_name=f"RER_{c1}_to_{c2}_{start_date}_to_{end_date}.csv",
        mime="text/csv"
    )
