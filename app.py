"""
Capital Gains Portfolio — Real-time Dashboard
Deploy free at streamlit.io/cloud
"""

import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import pytz

SGT = pytz.timezone("Asia/Singapore")

st.set_page_config(
    page_title="Capital Gains Portfolio",
    page_icon="📊",
    layout="wide",
)

# ── Inline CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }
  h1 { font-size: 1.4rem !important; font-weight: 600 !important; }
  .metric-card { background: #f7f7f5; border-radius: 10px; padding: 14px 18px; }
  .metric-label { font-size: 12px; color: #888; margin-bottom: 2px; }
  .metric-val { font-size: 26px; font-weight: 700; }
  .queen { color: #D4537E; }
  .green { color: #2d7a2d; }
  .red { color: #c0392b; }
  .amber { color: #b7770d; }
  .gray { color: #888; }
</style>
""", unsafe_allow_html=True)

# ── Portfolio data ────────────────────────────────────────────────────────────
PORTFOLIO = [
    # queen, ticker, company, s1, s2, s3, s4, iv
    (True,  "AAPL",  "Apple Inc",                196,  180,  165,  None, 198),
    (True,  "AMZN",  "Amazon.com",               218,  188,  161,  146,  229),
    (True,  "GOOGL", "Alphabet Inc",             275,  256,  236,  224,  291.55),
    (True,  "MA",    "Mastercard",               527,  502,  464,  428,  529),
    (True,  "META",  "Meta Platforms",           734,  690,  649,  598,  815),
    (True,  "MSFT",  "Microsoft",                493,  466,  431,  387,  537),
    (True,  "NVDA",  "NVIDIA",                   181,  153,  130,  90,   210),
    (True,  "PANW",  "Palo Alto Networks",       191,  177,  165,  145,  202),
    (True,  "SPGI",  "S&P Global",               511,  480,  458,  429,  528),
    (True,  "TMO",   "Thermo Fisher",            528,  501,  476,  415,  619),
    (True,  "WM",    "Waste Management",         223,  213,  200,  None, 231),
    (False, "ACN",   "Accenture",                278,  262,  243,  229,  318),
    (False, "ASML",  "ASML Holding",             858,  826,  763,  682,  969),
    (False, "AVGO",  "Broadcom",                 339,  305,  250,  219,  405),
    (False, "AZO",   "Autozone",                 3231, 3004, 2897, 2730, 3272),
    (False, "BKNG",  "Booking Holdings",         4148, 3749, 3395, 3166, 4656),
    (False, "CELH",  "Celsius Holdings",         51,   47,   41,   37,   84.77),
    (False, "CNSWF", "Constellation Software",   2926, 2574, 2232, 1919, 3504.5),
    (False, "CPRT",  "Copart",                   51,   48,   46,   42,   53.5),
    (False, "CRM",   "Salesforce",               286,  266,  229,  212,  318),
    (False, "CRWD",  "Crowdstrike",              335,  303,  280,  None, 345),
    (False, "EVVTY", "Evolution ADR",            98,   86,   72,   66,   143),
    (False, "FDS",   "FactSet Research",         344,  293,  249,  None, 363),
    (False, "FTNT",  "Fortinet",                 87,   81,   77,   70,   92.02),
    (False, "HCA",   "HCA Healthcare",           428,  402,  388,  371,  445),
    (False, "IDXX",  "IDEXX Laboratories",       372,  318,  254,  None, 437),
    (False, "LVMUY", "LVMH ADR",                 137,  119,  106,  None, 159),
    (False, "LIN",   "Linde plc",                424,  410,  396,  389,  435.98),
    (False, "MELI",  "Mercadolibre",             2023, 1834, 1645, 1481, 2284),
    (False, "MSCI",  "MSCI Inc",                 482,  457,  438,  385,  491),
    (False, "MSI",   "Motorola Solutions",       405,  388,  369,  None, 408),
    (False, "NKE",   "Nike",                     89,   82,   70,   57,   110),
    (False, "NOW",   "ServiceNow",               176,  159,  135,  127,  198),
    (False, "NVO",   "Novo Nordisk",             67,   58,   45,   None, 73.13),
    (False, "PEP",   "PepsiCo",                  155,  148,  141,  127,  158),
    (False, "PLTR",  "Palantir",                 142,  125,  105,  None, 143),
    (False, "POOL",  "Pool Corporation",         308,  282,  253,  228,  314),
    (False, "UNH",   "UnitedHealth Group",       324,  293,  272,  247,  412),
    (False, "V",     "Visa",                     303,  292,  281,  268,  311),
    (False, "VEEV",  "Veeva Systems",            257,  235,  217,  202,  270),
]

@st.cache_data(ttl=300)  # refresh every 5 minutes
def fetch_prices():
    tickers = [p[1] for p in PORTFOLIO]
    try:
        data = yf.download(tickers, period="1d", interval="1m",
                           progress=False, auto_adjust=True)
        prices = {}
        close = data["Close"]
        if hasattr(close, "columns"):
            for t in tickers:
                if t in close.columns:
                    val = close[t].dropna()
                    if not val.empty:
                        prices[t] = round(float(val.iloc[-1]), 2)
        return prices
    except Exception as e:
        st.warning(f"Price fetch error: {e}")
        return {}

def get_trigger(price, s1, s2, s3, s4):
    if s1 and price <= s1: return "🔴 S1"
    if s2 and price <= s2: return "🔴 S2"
    if s3 and price <= s3: return "🔴 S3"
    if s4 and price <= s4: return "🔴 S4"
    if s1 and (price - s1) / price < 0.05: return "🟡 Near S1"
    return "🟢 OK"

def build_df(prices):
    rows = []
    for queen, ticker, name, s1, s2, s3, s4, iv in PORTFOLIO:
        price = prices.get(ticker)
        if price is None:
            continue
        iv_discount = round((iv - price) / iv * 100, 1) if iv else None
        pct_to_s1   = round((price - s1) / price * 100, 1) if s1 else None
        trigger     = get_trigger(price, s1, s2, s3, s4)
        rows.append({
            "Queen": "★" if queen else "",
            "Ticker": ticker,
            "Company": name,
            "Price": price,
            "Support 1": s1,
            "Support 2": s2,
            "Support 3": s3,
            "Base IV": iv,
            "IV Discount %": iv_discount,
            "% Above S1": pct_to_s1,
            "Trigger": trigger,
            "_queen": queen,
            "_undervalued": iv_discount is not None and iv_discount > 0,
            "_iv_discount": iv_discount if iv_discount is not None else -999,
        })
    return pd.DataFrame(rows)

# ── Header ────────────────────────────────────────────────────────────────────
now_sgt = datetime.now(SGT).strftime("%d %b %Y, %I:%M %p SGT")
st.markdown(f"## 📊 Capital Gains Portfolio")
st.caption(f"US stocks only · ★ = Heavenly Queen · Prices auto-refresh every 5 min · {now_sgt}")

# ── Fetch prices ──────────────────────────────────────────────────────────────
with st.spinner("Fetching live prices…"):
    prices = fetch_prices()

if not prices:
    st.error("Could not fetch prices. Please try refreshing.")
    st.stop()

df = build_df(prices)

# ── Summary cards ─────────────────────────────────────────────────────────────
triggered  = len(df[df["Trigger"].str.startswith("🔴")])
near_s1    = len(df[df["Trigger"] == "🟡 Near S1"])
below_iv   = len(df[df["_undervalued"]])
total      = len(df)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total positions", total)
c2.metric("🔴 At/below support", triggered)
c3.metric("🟡 Near support (<5%)", near_s1)
c4.metric("✅ Below IV (buy zone)", below_iv)

st.divider()

# ── Filters ───────────────────────────────────────────────────────────────────
col_f1, col_f2, col_f3 = st.columns([2, 2, 3])
with col_f1:
    view = st.selectbox("View", [
        "All positions",
        "★ Heavenly Queens only",
        "🔴 Triggered (at/below support)",
        "🟡 Near support (<5%)",
        "✅ Undervalued (below IV)",
        "🔺 Overvalued (above IV)",
    ])
with col_f2:
    sort_by = st.selectbox("Sort by", [
        "IV Discount % ↓",
        "% Above S1 ↑ (closest to trigger)",
        "Ticker A–Z",
    ])
with col_f3:
    search = st.text_input("Search ticker / company", placeholder="e.g. NVDA or Apple")

# Apply filters
filtered = df.copy()
if search:
    filtered = filtered[
        filtered["Ticker"].str.contains(search, case=False) |
        filtered["Company"].str.contains(search, case=False)
    ]
if view == "★ Heavenly Queens only":
    filtered = filtered[filtered["_queen"]]
elif view == "🔴 Triggered (at/below support)":
    filtered = filtered[filtered["Trigger"].str.startswith("🔴")]
elif view == "🟡 Near support (<5%)":
    filtered = filtered[filtered["Trigger"].str.startswith("🟡")]
elif view == "✅ Undervalued (below IV)":
    filtered = filtered[filtered["_undervalued"]]
elif view == "🔺 Overvalued (above IV)":
    filtered = filtered[~filtered["_undervalued"] & filtered["IV Discount %"].notna()]

# Apply sort
if sort_by == "IV Discount % ↓":
    filtered = filtered.sort_values("_iv_discount", ascending=False)
elif sort_by == "% Above S1 ↑ (closest to trigger)":
    filtered = filtered.sort_values("% Above S1", ascending=True, na_position="last")
else:
    filtered = filtered.sort_values("Ticker")

# ── Prioritised sections (default All view) ───────────────────────────────────
def render_table(data, title=None):
    if title:
        st.markdown(f"**{title}**")
    display_cols = ["Queen","Ticker","Company","Price","Support 1","Support 2","Base IV","IV Discount %","% Above S1","Trigger"]
    display = data[display_cols].copy()

    def color_iv(val):
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return ""
        return "color: #2d7a2d; font-weight:600" if val > 0 else "color: #c0392b"

    def color_trigger(val):
        if "🔴" in str(val): return "color: #c0392b; font-weight:600"
        if "🟡" in str(val): return "color: #b7770d; font-weight:600"
        return "color: #2d7a2d"

    styled = display.style \
        .applymap(color_iv, subset=["IV Discount %"]) \
        .applymap(color_trigger, subset=["Trigger"]) \
        .format({
            "Price":       lambda x: f"${x:,.2f}" if pd.notna(x) else "—",
            "Support 1":   lambda x: f"${x:,.2f}" if pd.notna(x) else "—",
            "Support 2":   lambda x: f"${x:,.2f}" if pd.notna(x) else "—",
            "Base IV":     lambda x: f"${x:,.2f}" if pd.notna(x) else "—",
            "IV Discount %": lambda x: f"{x:+.1f}%" if pd.notna(x) else "—",
            "% Above S1":  lambda x: f"{x:.1f}%" if pd.notna(x) else "—",
        }, na_rep="—") \
        .hide(axis="index")

    st.dataframe(styled, use_container_width=True, height=min(50 + len(data) * 36, 500))

if view == "All positions" and not search:
    queens_under  = filtered[filtered["_queen"] & filtered["_undervalued"]].sort_values("_iv_discount", ascending=False)
    others_under  = filtered[~filtered["_queen"] & filtered["_undervalued"]].sort_values("_iv_discount", ascending=False)
    overvalued    = filtered[~filtered["_undervalued"] & filtered["IV Discount %"].notna()].sort_values("_iv_discount", ascending=False)
    no_iv         = filtered[filtered["IV Discount %"].isna()]

    render_table(queens_under, "★ Heavenly Queens — Undervalued")
    render_table(others_under, "Other US Stocks — Undervalued")
    render_table(overvalued,   "Overvalued / Above IV")
    if not no_iv.empty:
        render_table(no_iv, "ETFs / No IV data")
else:
    render_table(filtered)

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption("Prices from Yahoo Finance (15 min delay). Support levels updated 3 Feb 2026. Not financial advice.")
if st.button("🔄 Refresh prices now"):
    st.cache_data.clear()
    st.rerun()
