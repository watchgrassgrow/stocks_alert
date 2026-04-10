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

st.markdown("""
<style>
  .block-container { padding-top: 1.2rem; padding-bottom: 1rem; }
  h1 { font-size: 1.4rem !important; font-weight: 700 !important; }
</style>
""", unsafe_allow_html=True)

# ── Portfolio — verified against Google Sheet (3 Feb 2026) ───────────────────
# queen, ticker, company, s1, s2, s3, s4, s5, base_iv
PORTFOLIO = [
    (True,  "AAPL",  "Apple Inc",                196,   180,   165,   None,  None,  198.00),
    (True,  "AMZN",  "Amazon.com",               218,   188,   161,   146,   None,  229.00),
    (True,  "GOOGL", "Alphabet Inc",             275,   256,   236,   224,   None,  291.55),
    (True,  "MA",    "Mastercard",               527,   502,   464,   428,   None,  529.00),
    (True,  "META",  "Meta Platforms",           734,   690,   649,   598,   None,  815.00),
    (True,  "MSFT",  "Microsoft",                493,   466,   431,   387,   None,  537.00),
    (True,  "NVDA",  "NVIDIA",                   181,   153,   130,   90,    None,  210.00),
    (True,  "PANW",  "Palo Alto Networks",       191,   177,   165,   145,   None,  202.00),
    (True,  "SPGI",  "S&P Global",               511,   480,   458,   429,   None,  528.00),
    (True,  "TMO",   "Thermo Fisher",            528,   501,   476,   415,   None,  619.00),
    (True,  "WM",    "Waste Management",         223,   213,   200,   None,  None,  231.00),
    (False, "ACN",   "Accenture",                278,   262,   243,   229,   None,  318.00),
    (False, "ASML",  "ASML Holding",             858,   826,   763,   682,   None,  969.00),
    (False, "AVGO",  "Broadcom",                 339,   305,   250,   219,   None,  405.00),
    (False, "AZO",   "Autozone",                 3231,  3004,  2897,  2730,  None,  3272.00),
    (False, "BKNG",  "Booking Holdings",         4148,  3749,  3395,  3166,  None,  4656.00),
    (False, "CELH",  "Celsius Holdings",         51,    47,    41,    37,    None,  84.77),
    (False, "CNSWF", "Constellation Software",   2926,  2574,  2232,  1919,  1845,  3504.50),
    (False, "CPRT",  "Copart",                   51,    48,    46,    42,    38,    53.50),
    (False, "CRM",   "Salesforce",               286,   266,   229,   212,   None,  318.00),
    (False, "CRWD",  "Crowdstrike",              335,   303,   280,   None,  None,  345.00),
    (False, "EVVTY", "Evolution ADR",            98,    86,    72,    66,    None,  143.00),
    (False, "FDS",   "FactSet Research",         344,   293,   249,   None,  None,  363.00),
    (False, "FTNT",  "Fortinet",                 87,    81,    77,    70,    None,  92.02),
    (False, "HCA",   "HCA Healthcare",           428,   402,   388,   371,   None,  445.00),
    (False, "IDXX",  "IDEXX Laboratories",       372,   318,   254,   None,  None,  437.00),
    (False, "LVMUY", "LVMH ADR",                 137,   119,   106,   None,  None,  159.00),
    (False, "LIN",   "Linde plc",                424,   410,   396,   389,   None,  435.98),
    (False, "MELI",  "Mercadolibre",             2023,  1834,  1645,  1481,  None,  2284.00),
    (False, "MSCI",  "MSCI Inc",                 482,   457,   438,   385,   None,  491.00),
    (False, "MSI",   "Motorola Solutions",       405,   388,   369,   None,  None,  408.00),
    (False, "NKE",   "Nike",                     89,    82,    70,    57,    None,  110.00),
    (False, "NOW",   "ServiceNow",               176,   159,   135,   127,   105,   198.00),
    (False, "NVO",   "Novo Nordisk",             67,    58,    45,    None,  None,  73.13),
    (False, "PEP",   "PepsiCo",                  155,   148,   141,   127,   None,  158.00),
    (False, "PLTR",  "Palantir",                 142,   125,   105,   None,  None,  143.00),
    (False, "POOL",  "Pool Corporation",         308,   282,   253,   228,   None,  314.00),
    (False, "UNH",   "UnitedHealth Group",       324,   293,   272,   247,   None,  412.00),
    (False, "V",     "Visa",                     303,   292,   281,   268,   None,  311.00),
    (False, "VEEV",  "Veeva Systems",            257,   235,   217,   202,   None,  270.00),
]

US_TICKERS = [p[1] for p in PORTFOLIO]


@st.cache_data(ttl=300)
def fetch_prices():
    try:
        data = yf.download(US_TICKERS, period="1d", interval="1m",
                           progress=False, auto_adjust=True)
        prices = {}
        close = data["Close"]
        if hasattr(close, "columns"):
            for t in US_TICKERS:
                if t in close.columns:
                    val = close[t].dropna()
                    if not val.empty:
                        prices[t] = round(float(val.iloc[-1]), 2)
        return prices
    except Exception as e:
        st.warning(f"Price fetch error: {e}")
        return {}


def support_ladder_html(price, s1, s2, s3, s4, s5, iv):
    """
    Vertical price ladder — IV at top, supports below, current price shown inline.
    Each level is colour-coded: hit (red), near (amber), safe (slate), IV (blue).
    """
    all_levels = []
    if iv:
        all_levels.append(("IV", iv, "iv"))
    for label, val in [("S1", s1), ("S2", s2), ("S3", s3), ("S4", s4), ("S5", s5)]:
        if val is not None:
            all_levels.append((label, val, "support"))

    all_levels.sort(key=lambda x: x[1], reverse=True)  # highest first

    if price is None:
        return "<span style='color:#aaa;font-size:12px;'>No price data</span>"

    lines = []
    price_inserted = False

    for i, (label, val, kind) in enumerate(all_levels):
        # Insert current price arrow when we cross it going down
        if not price_inserted and price >= val:
            lines.append(
                f"<div style='margin:3px 0;'>"
                f"<span style='font-size:11px; font-weight:700; background:#1e293b; color:#f8fafc; "
                f"padding:2px 9px; border-radius:4px;'>▶ ${price:,.2f} &nbsp;current price</span>"
                f"</div>"
            )
            price_inserted = True

        pct = round((price - val) / price * 100, 1) if price else 0

        if kind == "iv":
            if price >= val:
                badge = f"<span style='color:#b91c1c; font-size:11px; font-weight:600;'>{abs(pct):.1f}% above IV ↑</span>"
                row_style = "background:#fef2f2; border-left:3px solid #f87171;"
                label_style = "color:#991b1b; font-weight:700;"
            else:
                badge = f"<span style='color:#1d4ed8; font-size:11px; font-weight:600;'>{abs(pct):.1f}% discount ✓</span>"
                row_style = "background:#eff6ff; border-left:3px solid #3b82f6;"
                label_style = "color:#1e40af; font-weight:700;"
            lines.append(
                f"<div style='margin:2px 0; {row_style} padding:3px 8px; border-radius:3px; "
                f"display:flex; justify-content:space-between; align-items:center; gap:8px;'>"
                f"<span style='font-size:12px; {label_style}'>📘 {label} &nbsp;${val:,.2f}</span>"
                f"{badge}</div>"
            )

        else:
            if price <= val:
                row_style = "background:#fef2f2; border-left:3px solid #ef4444;"
                label_style = "color:#991b1b;"
                badge = f"<span style='color:#dc2626; font-size:11px; font-weight:700;'>✅ HIT · {abs(pct):.1f}% below</span>"
            elif 0 < pct < 5:
                row_style = "background:#fffbeb; border-left:3px solid #f59e0b;"
                label_style = "color:#78350f;"
                badge = f"<span style='color:#b45309; font-size:11px; font-weight:600;'>⚠ {pct:.1f}% away · watch</span>"
            else:
                row_style = "background:#f8fafc; border-left:3px solid #cbd5e1;"
                label_style = "color:#475569;"
                badge = f"<span style='color:#94a3b8; font-size:11px;'>{pct:.1f}% above</span>"

            lines.append(
                f"<div style='margin:2px 0; {row_style} padding:3px 8px; border-radius:3px; "
                f"display:flex; justify-content:space-between; align-items:center; gap:8px;'>"
                f"<span style='font-size:12px; {label_style}'>{label} &nbsp;<strong>${val:,.2f}</strong></span>"
                f"{badge}</div>"
            )

    if not price_inserted:
        lines.append(
            f"<div style='margin:3px 0;'>"
            f"<span style='font-size:11px; font-weight:700; background:#1e293b; color:#f8fafc; "
            f"padding:2px 9px; border-radius:4px;'>▶ ${price:,.2f} &nbsp;current price</span>"
            f"</div>"
        )

    return "".join(lines)


def build_rows(prices):
    rows = []
    for queen, ticker, name, s1, s2, s3, s4, s5, iv in PORTFOLIO:
        price = prices.get(ticker)

        hit_level, next_level = None, None
        support_pairs = [("S1", s1), ("S2", s2), ("S3", s3), ("S4", s4), ("S5", s5)]
        for label, val in support_pairs:
            if val is None:
                continue
            if price and price <= val:
                hit_level = label
            elif hit_level and next_level is None:
                next_level = f"{label} ${val:,.0f}"
                break

        iv_discount = round((iv - price) / iv * 100, 1) if (iv and price) else None
        undervalued = iv_discount is not None and iv_discount > 0
        near_s1 = bool(price and s1 and price > s1 and (price - s1) / price < 0.05)

        rows.append({
            "queen": queen, "ticker": ticker, "name": name,
            "price": price, "s1": s1, "s2": s2, "s3": s3, "s4": s4, "s5": s5,
            "iv": iv, "hit_level": hit_level, "next_level": next_level,
            "iv_discount": iv_discount, "undervalued": undervalued, "near_s1": near_s1,
            "_ladder": support_ladder_html(price, s1, s2, s3, s4, s5, iv),
        })
    return rows


# ── Header ────────────────────────────────────────────────────────────────────
now_sgt = datetime.now(SGT).strftime("%d %b %Y, %I:%M %p SGT")
hc1, hc2 = st.columns([4, 1])
with hc1:
    st.markdown("## 📊 Capital Gains Portfolio")
    st.caption(f"US stocks only · ★ = Heavenly Queen · prices auto-refresh every 5 min · {now_sgt}")
with hc2:
    if st.button("🔄 Refresh prices", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

with st.spinner("Fetching live prices…"):
    prices = fetch_prices()

if not prices:
    st.error("Could not fetch prices. Try refreshing.")
    st.stop()

rows = build_rows(prices)

# ── Summary metrics ───────────────────────────────────────────────────────────
triggered = sum(1 for r in rows if r["hit_level"] and r["undervalued"])
near      = sum(1 for r in rows if r["near_s1"] and r["undervalued"])
below_iv  = sum(1 for r in rows if r["undervalued"])

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total positions", len(rows))
m2.metric("🔴 Support hit + undervalued", triggered)
m3.metric("🟡 Near S1 (<5%) + undervalued", near)
m4.metric("✅ Below IV (buy zone)", below_iv)

st.divider()

# ── Filters ───────────────────────────────────────────────────────────────────
fc1, fc2, fc3 = st.columns([2, 2, 3])
with fc1:
    view = st.selectbox("Filter", [
        "All positions",
        "★ Heavenly Queens only",
        "🔴 Support hit",
        "🟡 Near S1 (<5%)",
        "✅ Undervalued (below IV)",
        "🔺 Overvalued (above IV)",
    ])
with fc2:
    sort_by = st.selectbox("Sort by", [
        "IV Discount ↓ (best value first)",
        "Closest to S1 ↑",
        "Ticker A–Z",
    ])
with fc3:
    search = st.text_input("Search", placeholder="Ticker or company name…")

filtered = list(rows)
if search:
    q = search.lower()
    filtered = [r for r in filtered if q in r["ticker"].lower() or q in r["name"].lower()]
if view == "★ Heavenly Queens only":
    filtered = [r for r in filtered if r["queen"]]
elif view == "🔴 Support hit":
    filtered = [r for r in filtered if r["hit_level"]]
elif view == "🟡 Near S1 (<5%)":
    filtered = [r for r in filtered if r["near_s1"]]
elif view == "✅ Undervalued (below IV)":
    filtered = [r for r in filtered if r["undervalued"]]
elif view == "🔺 Overvalued (above IV)":
    filtered = [r for r in filtered if not r["undervalued"] and r["iv_discount"] is not None]

if sort_by == "IV Discount ↓ (best value first)":
    filtered.sort(key=lambda r: -(r["iv_discount"] or -9999))
elif sort_by == "Closest to S1 ↑":
    filtered.sort(key=lambda r: (r["price"] - r["s1"]) / r["price"] if (r["price"] and r["s1"]) else 9999)
else:
    filtered.sort(key=lambda r: r["ticker"])

# ── Table ─────────────────────────────────────────────────────────────────────
st.markdown(f"**{len(filtered)} positions shown**")

header_cols = st.columns([1.2, 2, 1.2, 1.1, 4])
for col, label in zip(header_cols, ["Ticker", "Company", "Live price", "IV discount", "Buy point ladder  (IV at top → S1 → S2 → S3…)"]):
    col.markdown(
        f"<span style='font-size:11px; font-weight:700; color:#6b7280; "
        f"text-transform:uppercase; letter-spacing:0.06em;'>{label}</span>",
        unsafe_allow_html=True
    )

st.markdown("<hr style='margin:4px 0 6px; border-color:#e5e7eb;'>", unsafe_allow_html=True)

for r in filtered:
    c1, c2, c3, c4, c5 = st.columns([1.2, 2, 1.2, 1.1, 4])

    queen_color = "#D4537E" if r["queen"] else "#1e293b"
    queen_mark  = "★ " if r["queen"] else ""

    with c1:
        st.markdown(
            f"<div style='padding-top:4px;'>"
            f"<span style='font-weight:700; font-size:14px; color:{queen_color};'>{queen_mark}{r['ticker']}</span>"
            f"</div>",
            unsafe_allow_html=True
        )
    with c2:
        st.markdown(
            f"<div style='padding-top:4px;'>"
            f"<span style='font-size:13px; color:#374151;'>{r['name']}</span>"
            f"</div>",
            unsafe_allow_html=True
        )
    with c3:
        price_str = f"${r['price']:,.2f}" if r["price"] else "—"
        st.markdown(
            f"<div style='padding-top:4px;'>"
            f"<span style='font-weight:700; font-size:14px;'>{price_str}</span>"
            f"</div>",
            unsafe_allow_html=True
        )
    with c4:
        if r["iv_discount"] is not None:
            color = "#2d7a2d" if r["iv_discount"] > 0 else "#c0392b"
            sign  = "+" if r["iv_discount"] > 0 else ""
            st.markdown(
                f"<div style='padding-top:4px;'>"
                f"<span style='font-weight:700; font-size:14px; color:{color};'>{sign}{r['iv_discount']:.1f}%</span>"
                f"</div>",
                unsafe_allow_html=True
            )
        else:
            st.markdown("<div style='padding-top:4px; color:#aaa; font-size:13px;'>No IV</div>", unsafe_allow_html=True)
    with c5:
        st.markdown(r["_ladder"], unsafe_allow_html=True)

    st.markdown("<hr style='margin:4px 0; border-color:#f3f4f6;'>", unsafe_allow_html=True)

st.caption("Prices from Yahoo Finance (15 min delay). Support levels from Google Sheet, last updated 3 Feb 2026. Not financial advice.")
