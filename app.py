"""Real Exchange Rate Explorer — Streamlit app using IMF CPI and exchange-rate data.

Definitions
-----------
S(t)   = units of Country 2 currency per 1 unit of Country 1 currency
P1, P2 = monthly CPI of Country 1 / Country 2
RER(t) = S(t) * P1(t) / P2(t)
RER*   = mean of RER(t) over valid months in the selected sample
Real Index(t) = 100 * RER(t) / RER*
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from plotly.subplots import make_subplots

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
IMF_BASE = "https://api.imf.org/external/sdmx/3.0"
START = pd.Period("1976-01", freq="M")
EURO_AREA = "G163"
ACCEPT_HEADERS = [
    "application/vnd.sdmx.data+json; version=2.0.0",
    "application/json",
]

COUNTRIES: dict[str, str] = {
    "G163": "Euro area",
    "AFG": "Afghanistan", "ALB": "Albania", "DZA": "Algeria", "AGO": "Angola",
    "ATG": "Antigua and Barbuda", "ARG": "Argentina", "ARM": "Armenia",
    "ABW": "Aruba", "AUS": "Australia", "AUT": "Austria", "AZE": "Azerbaijan",
    "BHS": "Bahamas", "BHR": "Bahrain", "BGD": "Bangladesh", "BRB": "Barbados",
    "BLR": "Belarus", "BEL": "Belgium", "BLZ": "Belize", "BEN": "Benin",
    "BTN": "Bhutan", "BOL": "Bolivia", "BIH": "Bosnia and Herzegovina",
    "BWA": "Botswana", "BRA": "Brazil", "BRN": "Brunei Darussalam",
    "BGR": "Bulgaria", "BFA": "Burkina Faso", "BDI": "Burundi",
    "CPV": "Cabo Verde", "KHM": "Cambodia", "CMR": "Cameroon", "CAN": "Canada",
    "CAF": "Central African Republic", "TCD": "Chad", "CHL": "Chile",
    "CHN": "China", "COL": "Colombia", "COM": "Comoros",
    "COD": "Congo, Dem. Rep.", "COG": "Congo, Rep.", "CRI": "Costa Rica",
    "CIV": "Côte d'Ivoire", "HRV": "Croatia", "CYP": "Cyprus",
    "CZE": "Czech Republic", "DNK": "Denmark", "DJI": "Djibouti",
    "DMA": "Dominica", "DOM": "Dominican Republic", "ECU": "Ecuador",
    "EGY": "Egypt", "SLV": "El Salvador", "GNQ": "Equatorial Guinea",
    "ERI": "Eritrea", "EST": "Estonia", "SWZ": "Eswatini", "ETH": "Ethiopia",
    "FJI": "Fiji", "FIN": "Finland", "FRA": "France", "GAB": "Gabon",
    "GMB": "Gambia", "GEO": "Georgia", "DEU": "Germany", "GHA": "Ghana",
    "GRC": "Greece", "GRD": "Grenada", "GTM": "Guatemala", "GIN": "Guinea",
    "GNB": "Guinea-Bissau", "GUY": "Guyana", "HTI": "Haiti", "HND": "Honduras",
    "HKG": "Hong Kong SAR", "HUN": "Hungary", "ISL": "Iceland", "IND": "India",
    "IDN": "Indonesia", "IRN": "Iran", "IRQ": "Iraq", "IRL": "Ireland",
    "ISR": "Israel", "ITA": "Italy", "JAM": "Jamaica", "JPN": "Japan",
    "JOR": "Jordan", "KAZ": "Kazakhstan", "KEN": "Kenya", "KIR": "Kiribati",
    "KOR": "Korea, Rep.", "XKX": "Kosovo", "KWT": "Kuwait",
    "KGZ": "Kyrgyz Republic", "LAO": "Lao PDR", "LVA": "Latvia", "LBN": "Lebanon",
    "LSO": "Lesotho", "LBR": "Liberia", "LBY": "Libya", "LTU": "Lithuania",
    "LUX": "Luxembourg", "MAC": "Macao SAR", "MDG": "Madagascar", "MWI": "Malawi",
    "MYS": "Malaysia", "MDV": "Maldives", "MLI": "Mali", "MLT": "Malta",
    "MHL": "Marshall Islands", "MRT": "Mauritania", "MUS": "Mauritius",
    "MEX": "Mexico", "FSM": "Micronesia", "MDA": "Moldova", "MNG": "Mongolia",
    "MNE": "Montenegro", "MAR": "Morocco", "MOZ": "Mozambique", "MMR": "Myanmar",
    "NAM": "Namibia", "NRU": "Nauru", "NPL": "Nepal", "NLD": "Netherlands",
    "NZL": "New Zealand", "NIC": "Nicaragua", "NER": "Niger", "NGA": "Nigeria",
    "MKD": "North Macedonia", "NOR": "Norway", "OMN": "Oman", "PAK": "Pakistan",
    "PLW": "Palau", "PAN": "Panama", "PNG": "Papua New Guinea", "PRY": "Paraguay",
    "PER": "Peru", "PHL": "Philippines", "POL": "Poland", "PRT": "Portugal",
    "PRI": "Puerto Rico", "QAT": "Qatar", "ROU": "Romania", "RUS": "Russia",
    "RWA": "Rwanda", "WSM": "Samoa", "SMR": "San Marino",
    "STP": "São Tomé and Príncipe", "SAU": "Saudi Arabia", "SEN": "Senegal",
    "SRB": "Serbia", "SYC": "Seychelles", "SLE": "Sierra Leone",
    "SGP": "Singapore", "SVK": "Slovak Republic", "SVN": "Slovenia",
    "SLB": "Solomon Islands", "SOM": "Somalia", "ZAF": "South Africa",
    "SSD": "South Sudan", "ESP": "Spain", "LKA": "Sri Lanka",
    "KNA": "St. Kitts and Nevis", "LCA": "St. Lucia",
    "VCT": "St. Vincent and the Grenadines", "SDN": "Sudan", "SUR": "Suriname",
    "SWE": "Sweden", "CHE": "Switzerland", "SYR": "Syria", "TWN": "Taiwan",
    "TJK": "Tajikistan", "TZA": "Tanzania", "THA": "Thailand",
    "TLS": "Timor-Leste", "TGO": "Togo", "TON": "Tonga",
    "TTO": "Trinidad and Tobago", "TUN": "Tunisia", "TUR": "Türkiye",
    "TKM": "Turkmenistan", "TUV": "Tuvalu", "UGA": "Uganda", "UKR": "Ukraine",
    "ARE": "United Arab Emirates", "GBR": "United Kingdom",
    "USA": "United States", "URY": "Uruguay", "UZB": "Uzbekistan",
    "VUT": "Vanuatu", "VEN": "Venezuela", "VNM": "Vietnam",
    "PSE": "West Bank and Gaza", "YEM": "Yemen", "ZMB": "Zambia", "ZWE": "Zimbabwe",
}

REAL_COLOR = "#4F46E5"
NOMINAL_COLOR = "#F59E0B"


# --------------------------------------------------------------------------- #
# IMF data access
# --------------------------------------------------------------------------- #
class IMFError(RuntimeError):
    pass


def _parse_sdmx_json(payload: dict) -> pd.Series:
    """Parse an SDMX-JSON (1.0 or 2.0) payload into a monthly pd.Series."""
    data = payload.get("data", payload)
    structure = data.get("structures", [None])[0] if "structures" in data else data.get("structure")
    datasets = data.get("dataSets", [])
    if not structure or not datasets:
        return pd.Series(dtype=float)

    dims = structure.get("dimensions", {})
    series_dims = dims.get("series", []) or []
    obs_dims = dims.get("observation", []) or []

    def time_values(dim_list):
        for i, d in enumerate(dim_list):
            if d.get("id") == "TIME_PERIOD":
                return i, [v.get("id") or v.get("value") for v in d.get("values", [])]
        return None, None

    pattern = re.compile(r"^(\d{4})-(?:M)?(\d{2})$")
    records: dict[pd.Period, float] = {}

    def add(time_id, raw):
        m = pattern.match(str(time_id))
        if not m or raw in (None, ""):
            return
        try:
            records[pd.Period(f"{m.group(1)}-{m.group(2)}", freq="M")] = float(raw)
        except (ValueError, TypeError):
            return

    ds = datasets[0]
    if ds.get("series"):
        _, times = time_values(obs_dims)
        if times is None:
            return pd.Series(dtype=float)
        # Use the first series that actually contains observations.
        for s in ds["series"].values():
            obs = s.get("observations", {})
            if not obs:
                continue
            for idx, val in obs.items():
                add(times[int(idx)], val[0] if isinstance(val, list) else val)
            break
    elif ds.get("observations"):  # flat / all-dimensions layout
        t_pos, times = time_values(obs_dims)
        if times is None:
            return pd.Series(dtype=float)
        for key, val in ds["observations"].items():
            parts = key.split(":")
            add(times[int(parts[t_pos])], val[0] if isinstance(val, list) else val)

    if not records:
        return pd.Series(dtype=float)
    s = pd.Series(records).sort_index()
    return s[s.index >= START]


def _fetch(dataflow: str, key: str) -> pd.Series:
    """Fetch one IMF series; returns an empty Series if it does not exist."""
    url = f"{IMF_BASE}/data/dataflow/IMF.STA/{dataflow}/+/{key}"
    last_err = None
    for accept in ACCEPT_HEADERS:
        for attempt in range(3):
            try:
                r = requests.get(url, headers={"Accept": accept}, timeout=45)
            except requests.RequestException as e:
                last_err = e
                continue
            if r.status_code in (404, 204):
                return pd.Series(dtype=float)
            if r.status_code == 406:  # try the next Accept header
                last_err = IMFError(f"HTTP 406 for {key}")
                break
            if r.status_code >= 400:
                last_err = IMFError(f"HTTP {r.status_code} for {key}")
                continue
            try:
                return _parse_sdmx_json(r.json())
            except ValueError as e:
                last_err = e
    raise IMFError(f"Could not retrieve {dataflow} {key}: {last_err}")


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def get_cpi(iso3: str) -> pd.Series:
    return _fetch("CPI", f"{iso3}.CPI._T.IX.M")


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def get_fx_per_usd(iso3: str) -> tuple[pd.Series, str]:
    """Local currency units per USD (period average). Returns (series, note)."""
    if iso3 == "USA":
        idx = pd.period_range(START, pd.Period.now("M"), freq="M")
        return pd.Series(1.0, index=idx), ""
    s = _fetch("ER", f"{iso3}.XDC_USD.PA_RT.M")
    if s.empty and iso3 == EURO_AREA:
        # Fallback: Germany's series is denominated in euro from 1999 onward.
        s = _fetch("ER", "DEU.XDC_USD.PA_RT.M")
        s = s[s.index >= pd.Period("1999-01", freq="M")]
        if not s.empty:
            return s, "Euro-area exchange rate proxied by euro-denominated data (from 1999)."
    return s, ""


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def load_pair(c1: str, c2: str) -> dict:
    jobs = {
        "p1": lambda: get_cpi(c1),
        "p2": lambda: get_cpi(c2),
        "e1": lambda: get_fx_per_usd(c1),
        "e2": lambda: get_fx_per_usd(c2),
    }
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {k: ex.submit(fn) for k, fn in jobs.items()}
        out = {k: f.result() for k, f in futures.items()}
    return {
        "p1": out["p1"], "p2": out["p2"],
        "e1": out["e1"][0], "e2": out["e2"][0],
        "notes": [n for n in (out["e1"][1], out["e2"][1]) if n],
    }


def build_frame(d: dict) -> pd.DataFrame:
    df = pd.concat(
        {"fx1_per_usd": d["e1"], "fx2_per_usd": d["e2"], "cpi1": d["p1"], "cpi2": d["p2"]},
        axis=1,
    ).sort_index()
    # S = (C2 per USD) / (C1 per USD) = units of C2 per unit of C1
    df["S"] = df["fx2_per_usd"] / df["fx1_per_usd"]
    df["RER"] = df["S"] * df["cpi1"] / df["cpi2"]
    return df


# --------------------------------------------------------------------------- #
# UI helpers
# --------------------------------------------------------------------------- #
def inject_css() -> None:
    st.markdown(
        """
        <style>
        .block-container {max-width: 1100px; padding-top: 2.2rem;}
        h1 {font-weight: 700; letter-spacing: -0.02em; margin-bottom: 0.1rem;}
        .subtitle {color: #6B7280; margin-bottom: 1.4rem; font-size: 1.02rem;}
        [data-testid="stMetric"] {
            background: rgba(127,127,127,0.07); border-radius: 14px;
            padding: 14px 18px; border: 1px solid rgba(127,127,127,0.15);
        }
        [data-testid="stMetricLabel"] {opacity: 0.7;}
        .formula {color: #6B7280; font-size: 0.9rem; margin-top: -0.4rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def make_chart(sample: pd.DataFrame, view: str, n1: str, n2: str) -> go.Figure:
    x = sample.index.to_timestamp()
    fig = make_subplots(specs=[[{"secondary_y": view == "Both"}]])

    if view in ("Real", "Both"):
        fig.add_trace(
            go.Scatter(x=x, y=sample["real_index"], name="Real index (RER* = 100)",
                       line=dict(color=REAL_COLOR, width=2.4),
                       hovertemplate="%{x|%b %Y}<br>Real index: %{y:.2f}<extra></extra>"),
            secondary_y=False,
        )
        fig.add_hline(y=100, line=dict(color=REAL_COLOR, width=1, dash="dot"), opacity=0.5)
    if view in ("Nominal", "Both"):
        fig.add_trace(
            go.Scatter(x=x, y=sample["S"], name=f"Nominal S ({n2} per {n1})",
                       line=dict(color=NOMINAL_COLOR, width=2.4),
                       hovertemplate="%{x|%b %Y}<br>S: %{y:,.4f}<extra></extra>"),
            secondary_y=(view == "Both"),
        )

    if view == "Real":
        fig.update_yaxes(title_text="Real index")
    elif view == "Nominal":
        fig.update_yaxes(title_text=f"{n2} per 1 {n1}")
    else:
        fig.update_yaxes(title_text="Real index", secondary_y=False,
                         title_font_color=REAL_COLOR)
        fig.update_yaxes(title_text=f"{n2} per 1 {n1}", secondary_y=True,
                         title_font_color=NOMINAL_COLOR, showgrid=False)

    fig.update_layout(
        template="plotly_white", height=470, hovermode="x unified",
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", y=1.08, x=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, system-ui, sans-serif"),
    )
    fig.update_xaxes(showgrid=False, rangeslider=dict(visible=False))
    fig.update_yaxes(gridcolor="rgba(127,127,127,0.18)", zeroline=False)
    return fig


def fmt_range(s: pd.Series) -> str:
    return f"{s.index.min()} → {s.index.max()}" if not s.empty else "no data"


# --------------------------------------------------------------------------- #
# App
# --------------------------------------------------------------------------- #
def main() -> None:
    st.set_page_config(page_title="Real Exchange Rate Explorer", page_icon="💱", layout="centered")
    inject_css()

    st.title("Real Exchange Rate Explorer")
    st.markdown(
        '<div class="subtitle">Compare nominal and CPI-based real exchange rates '
        "for any two IMF economies, monthly since 1976.</div>",
        unsafe_allow_html=True,
    )

    codes = list(COUNTRIES)
    col_a, col_b = st.columns(2)
    c1 = col_a.selectbox("Country 1 (base)", codes, index=codes.index("USA"),
                         format_func=lambda c: COUNTRIES[c])
    c2 = col_b.selectbox("Country 2 (quote)", codes, index=codes.index("JPN"),
                         format_func=lambda c: COUNTRIES[c])
    n1, n2 = COUNTRIES[c1], COUNTRIES[c2]

    if c1 == c2:
        st.info("Pick two different economies to compare.")
        return

    try:
        with st.spinner("Fetching data from the IMF…"):
            data = load_pair(c1, c2)
    except IMFError as e:
        st.error(f"The IMF data service did not respond as expected. {e}")
        return
    except Exception as e:  # noqa: BLE001
        st.error(f"Unexpected error while loading data: {e}")
        return

    frame = build_frame(data)
    valid = frame.dropna(subset=["S", "cpi1", "cpi2", "RER"])

    with st.expander("Data coverage", expanded=valid.empty):
        st.markdown(
            f"- **{n1} CPI:** {fmt_range(data['p1'])}\n"
            f"- **{n2} CPI:** {fmt_range(data['p2'])}\n"
            f"- **{n1} exchange rate:** {fmt_range(data['e1'])}\n"
            f"- **{n2} exchange rate:** {fmt_range(data['e2'])}\n"
            f"- **Months with all inputs:** {len(valid):,}"
        )
        for note in data["notes"]:
            st.caption(note)

    if valid.empty:
        st.warning("No months have complete CPI and exchange-rate data for this pair. "
                   "Try another combination.")
        return

    # --- Controls ---------------------------------------------------------- #
    months = list(valid.index)
    start, end = st.select_slider(
        "Sample period",
        options=months,
        value=(months[0], months[-1]),
        format_func=lambda p: p.strftime("%b %Y"),
        key=f"range_{c1}_{c2}",
    )
    view = st.segmented_control("Chart", ["Real", "Nominal", "Both"], default="Both",
                                key="view") or "Both"

    # --- Calculations (RER* recomputed for every selected sample) ---------- #
    sample = valid.loc[start:end].copy()
    rer_star = sample["RER"].mean()
    sample["rer_star"] = rer_star
    sample["real_index"] = 100 * sample["RER"] / rer_star

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("RER* (sample mean)", f"{rer_star:,.4f}")
    m2.metric(f"Latest S ({sample.index[-1].strftime('%b %Y')})", f"{sample['S'].iloc[-1]:,.4f}")
    m3.metric("Latest real index", f"{sample['real_index'].iloc[-1]:.1f}")
    m4.metric("Valid months", f"{len(sample):,}")

    st.plotly_chart(make_chart(sample, view, n1, n2), width="stretch")

    st.markdown(
        f'<div class="formula">S = {n2} per 1 {n1}. RER = S × P₁ / P₂. '
        f"An index above 100 means {n1} is relatively more expensive than its sample average "
        f"(real appreciation of the {n1} currency).</div>",
        unsafe_allow_html=True,
    )

    # --- CSV export -------------------------------------------------------- #
    out = pd.DataFrame({
        "date": sample.index.strftime("%Y-%m"),
        f"{c1}_currency_per_USD": sample["fx1_per_usd"].values,
        f"{c2}_currency_per_USD": sample["fx2_per_usd"].values,
        "S_country2_per_country1": sample["S"].values,
        "P1_cpi_country1": sample["cpi1"].values,
        "P2_cpi_country2": sample["cpi2"].values,
        "RER": sample["RER"].values,
        "RER_star": sample["rer_star"].values,
        "Real_Index": sample["real_index"].values,
    })
    st.download_button(
        "⬇  Download CSV",
        out.to_csv(index=False).encode("utf-8"),
        file_name=f"rer_{c1}_{c2}_{start}_{end}.csv".replace("/", "-"),
        mime="text/csv",
        width="stretch",
    )
    st.caption("Source: IMF (CPI and period-average exchange rates). "
               "Coverage varies by country; only months with all inputs are used.")


if __name__ == "__main__":
    main()
