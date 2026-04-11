"""
Capital Gains Portfolio — Real-time Dashboard
- Reads support levels + IV live from Google Sheet
- Fetches earnings dates from yfinance
- Deploy free at streamlit.io/cloud
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz
import io

SGT = pytz.timezone("Asia/Singapore")

SHEET_ID  = "1HzoXu5c5dyq4qYn6halQixRz1CkY_JrSuk-_6izKUsQ"
SHEET_GID = "333931792"
CSV_URL   = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={SHEET_GID}"

st.set_page_config(page_title="Capital Gains Portfolio", page_icon="📊", layout="wide")
st.markdown("<style>.block-container{padding-top:1.2rem;}</style>", unsafe_allow_html=True)


# ── Load sheet ────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def load_sheet():
    resp = requests.get(CSV_URL, timeout=15)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text), header=None)

    # Find the actual last-modified date by scanning the sheet fetch time
    # K2 label row=1,col=10; date value row=1,col=11
    try:
        # Date is in col K (index 10) per sheet screenshot
        sheet_label_date = str(df.iloc[1, 10]).strip()
        if sheet_label_date in ("nan", "", "None"):
            for col_idx in [11, 9, 12]:
                val = str(df.iloc[1, col_idx]).strip()
                if val not in ("nan", "", "None") and any(c.isdigit() for c in val):
                    sheet_label_date = val
                    break
    except Exception:
        sheet_label_date = "Unknown"

    portfolio = []
    for idx in range(7, len(df)):
        row = df.iloc[idx]
        ticker_raw = str(row.iloc[2]).strip()
        if not ticker_raw or ticker_raw in ("nan", "Notes:"):
            break
        currency = str(row.iloc[5]).strip()
        if currency != "USD":
            continue

        ticker  = ticker_raw.replace("-US", "").replace("-HK", "")
        company = str(row.iloc[3]).strip()
        queen_raw = str(row.iloc[1]).strip()
        queen = "Q" in queen_raw or "❤" in queen_raw

        def parse_num(val):
            s = str(val).strip().replace("$", "").replace(",", "").replace(" ", "")
            try:
                return float(s)
            except Exception:
                return None

        portfolio.append({
            "queen": queen, "ticker": ticker, "name": company,
            "s1": parse_num(row.iloc[6]),
            "s2": parse_num(row.iloc[7]),
            "s3": parse_num(row.iloc[8]),
            "s4": parse_num(row.iloc[9]),
            "s5": parse_num(row.iloc[10]),
            "iv": parse_num(row.iloc[13]),
        })

    fetched_at = datetime.now(SGT).strftime("%d %b %Y, %I:%M %p SGT")
    return portfolio, sheet_label_date, fetched_at


# ── Fetch prices ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def fetch_prices(tickers):
    try:
        data = yf.download(list(tickers), period="1d", interval="1m",
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


# ── Fetch earnings dates ──────────────────────────────────────────────────────
@st.cache_data(ttl=86400)  # refresh once a day
def fetch_earnings(tickers):
    """
    Returns dict: ticker -> {"date": date_obj, "days_away": int, "confirmed": bool}
    Only includes earnings within the next 28 days.
    """
    today = datetime.now(SGT).date()
    cutoff = today + timedelta(days=28)
    earnings = {}

    for ticker in tickers:
        try:
            info = yf.Ticker(ticker).calendar
            if info is None or info.empty:
                continue
            # calendar returns a DataFrame; earnings date is in index "Earnings Date"
            if "Earnings Date" in info.index:
                raw = info.loc["Earnings Date"]
                # can be a single value or two values (range)
                dates = raw.values if hasattr(raw, "values") else [raw]
                for d in dates:
                    try:
                        ed = pd.Timestamp(d).date()
                        if today <= ed <= cutoff:
                            days_away = (ed - today).days
                            earnings[ticker] = {
                                "date": ed,
                                "days_away": days_away,
                                "label": ed.strftime("%d %b"),
                            }
                            break
                    except Exception:
                        continue
        except Exception:
            continue

    return earnings


# ── Earnings badge HTML ───────────────────────────────────────────────────────
def earnings_badge(ticker, earnings_map):
    e = earnings_map.get(ticker)
    if not e:
        return ""
    days = e["days_away"]
    label = e["label"]
    if days <= 7:
        bg, color = "#fef2f2", "#dc2626"
        icon = "🔔"
        urgency = f"in {days}d"
    elif days <= 14:
        bg, color = "#fffbeb", "#b45309"
        icon = "📅"
        urgency = f"in {days}d"
    else:
        bg, color = "#f0fdf4", "#166534"
        icon = "📅"
        urgency = f"in {days}d"

    return (
        f"<span style='display:inline-block;background:{bg};color:{color};"
        f"border:1px solid {color}33;font-size:10px;font-weight:700;"
        f"padding:1px 6px;border-radius:4px;margin-left:4px;white-space:nowrap;'>"
        f"{icon} Earnings {label} ({urgency})</span>"
    )


# ── Support ladder ────────────────────────────────────────────────────────────
def support_ladder_html(price, s1, s2, s3, s4, s5, iv):
    all_levels = []
    if iv:
        all_levels.append(("IV", iv, "iv"))
    for label, val in [("S1", s1), ("S2", s2), ("S3", s3), ("S4", s4), ("S5", s5)]:
        if val is not None:
            all_levels.append((label, val, "support"))
    all_levels.sort(key=lambda x: x[1], reverse=True)

    if price is None:
        return "<span style='color:#aaa;font-size:12px;'>No price data</span>"

    lines = []
    price_inserted = False

    for label, val, kind in all_levels:
        if not price_inserted and price >= val:
            lines.append(
                f"<div style='margin:3px 0;'><span style='font-size:11px;font-weight:700;"
                f"background:#1e293b;color:#f8fafc;padding:2px 9px;border-radius:4px;'>"
                f"▶ ${price:,.2f} current price</span></div>"
            )
            price_inserted = True

        pct = round((price - val) / price * 100, 1) if price else 0

        if kind == "iv":
            if price >= val:
                badge = f"<span style='color:#b91c1c;font-size:11px;font-weight:600;'>{abs(pct):.1f}% above IV ↑</span>"
                row_s = "background:#fef2f2;border-left:3px solid #f87171;"
                lbl_s = "color:#991b1b;font-weight:700;"
            else:
                badge = f"<span style='color:#1d4ed8;font-size:11px;font-weight:600;'>{abs(pct):.1f}% discount ✓</span>"
                row_s = "background:#eff6ff;border-left:3px solid #3b82f6;"
                lbl_s = "color:#1e40af;font-weight:700;"
            lines.append(
                f"<div style='margin:2px 0;{row_s}padding:3px 8px;border-radius:3px;"
                f"display:flex;justify-content:space-between;align-items:center;gap:8px;'>"
                f"<span style='font-size:12px;{lbl_s}'>📘 {label} ${val:,.2f}</span>{badge}</div>"
            )
        else:
            if price <= val:
                row_s = "background:#fef2f2;border-left:3px solid #ef4444;"
                lbl_s = "color:#991b1b;"
                badge = f"<span style='color:#dc2626;font-size:11px;font-weight:700;'>✅ HIT · {abs(pct):.1f}% below</span>"
            elif 0 < pct < 5:
                row_s = "background:#fffbeb;border-left:3px solid #f59e0b;"
                lbl_s = "color:#78350f;"
                badge = f"<span style='color:#b45309;font-size:11px;font-weight:600;'>⚠ {pct:.1f}% away · watch</span>"
            else:
                row_s = "background:#f8fafc;border-left:3px solid #cbd5e1;"
                lbl_s = "color:#475569;"
                badge = f"<span style='color:#94a3b8;font-size:11px;'>{pct:.1f}% above</span>"
            lines.append(
                f"<div style='margin:2px 0;{row_s}padding:3px 8px;border-radius:3px;"
                f"display:flex;justify-content:space-between;align-items:center;gap:8px;'>"
                f"<span style='font-size:12px;{lbl_s}'>{label} <strong>${val:,.2f}</strong></span>{badge}</div>"
            )

    if not price_inserted:
        lines.append(
            f"<div style='margin:3px 0;'><span style='font-size:11px;font-weight:700;"
            f"background:#1e293b;color:#f8fafc;padding:2px 9px;border-radius:4px;'>"
            f"▶ ${price:,.2f} current price</span></div>"
        )
    return "".join(lines)


# ── Build rows ────────────────────────────────────────────────────────────────
def build_rows(portfolio, prices, earnings_map):
    rows = []
    for p in portfolio:
        price = prices.get(p["ticker"])
        s1, s2, s3, s4, s5, iv = p["s1"], p["s2"], p["s3"], p["s4"], p["s5"], p["iv"]

        hit_level, next_level = None, None
        for label, val in [("S1", s1), ("S2", s2), ("S3", s3), ("S4", s4), ("S5", s5)]:
            if val is None:
                continue
            if price and price <= val:
                hit_level = label
            elif hit_level and next_level is None:
                next_level = f"{label} ${val:,.0f}"
                break

        iv_discount = round((iv - price) / iv * 100, 1) if (iv and price) else None
        undervalued = iv_discount is not None and iv_discount > 0
        near_s1     = bool(price and s1 and price > s1 and (price - s1) / price < 0.05)
        has_earnings = p["ticker"] in earnings_map

        rows.append({
            **p, "price": price,
            "hit_level": hit_level, "next_level": next_level,
            "iv_discount": iv_discount, "undervalued": undervalued,
            "near_s1": near_s1, "has_earnings": has_earnings,
            "earnings": earnings_map.get(p["ticker"]),
            "_ladder": support_ladder_html(price, s1, s2, s3, s4, s5, iv),
        })
    return rows


# ── App ───────────────────────────────────────────────────────────────────────
now_sgt = datetime.now(SGT).strftime("%d %b %Y, %I:%M %p SGT")

with st.spinner("Loading portfolio from Google Sheet…"):
    portfolio, sheet_label_date, fetched_at = load_sheet()

if not portfolio:
    st.error("Could not load from Google Sheet. Ensure it is set to 'Anyone with link can view'.")
    st.stop()

tickers = tuple(p["ticker"] for p in portfolio)

col_h1, col_h2 = st.columns([4, 1])
with col_h1:
    st.markdown("## 📊 Capital Gains Portfolio")
with col_h2:
    if st.button("🔄 Refresh all", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# Data freshness info box
today_str = datetime.now(SGT).strftime("%d %b %Y")
st.markdown(
    f"<div style='background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;"
    f"padding:10px 16px;margin-bottom:12px;font-size:13px;line-height:2;'>"
    f"📋 <b>Support & IV last updated (per sheet cell K2):</b> "
    f"<span style='color:#b45309;font-weight:700;'>{sheet_label_date}</span>"
    f"&nbsp;&nbsp;·&nbsp;&nbsp;"
    f"⚠️ <i>If this date looks stale, the sheet owner needs to refresh the data and update cell L2.</i><br>"
    f"💰 <b>Live prices as of:</b> <span style='color:#1e40af;font-weight:700;'>{fetched_at}</span>"
    f"</div>",
    unsafe_allow_html=True
)

with st.spinner("Fetching live prices…"):
    prices = fetch_prices(tickers)

with st.spinner("Fetching earnings dates (next 4 weeks)…"):
    earnings_map = fetch_earnings(tickers)

rows = build_rows(portfolio, prices, earnings_map)

# Summary metrics
triggered    = sum(1 for r in rows if r["hit_level"] and r["undervalued"])
near         = sum(1 for r in rows if r["near_s1"] and r["undervalued"])
below_iv     = sum(1 for r in rows if r["undervalued"])
earn_upcoming = len(earnings_map)

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Total positions", len(rows))
m2.metric("🔴 Support hit + undervalued", triggered)
m3.metric("🟡 Near S1 + undervalued", near)
m4.metric("✅ Below IV", below_iv)
m5.metric("🔔 Earnings next 4 weeks", earn_upcoming)

# Earnings callout banner
if earnings_map:
    sorted_earnings = sorted(earnings_map.items(), key=lambda x: x[1]["days_away"])
    earn_items = " &nbsp;·&nbsp; ".join(
        f"<b>{t}</b> {e['label']} ({e['days_away']}d)"
        for t, e in sorted_earnings
    )
    st.markdown(
        f"<div style='background:#fffbeb;border:1px solid #f59e0b;border-radius:8px;"
        f"padding:10px 16px;margin-bottom:4px;font-size:13px;'>"
        f"🔔 <b>Upcoming earnings (next 28 days):</b> &nbsp; {earn_items}"
        f"</div>",
        unsafe_allow_html=True
    )

st.divider()

# Filters
fc1, fc2, fc3 = st.columns([2, 2, 3])
with fc1:
    view = st.selectbox("Filter", [
        "All positions",
        "★ Heavenly Queens only",
        "🔴 Support hit",
        "🟡 Near S1 (<5%)",
        "✅ Undervalued (below IV)",
        "🔺 Overvalued (above IV)",
        "🔔 Earnings next 4 weeks",
    ])
with fc2:
    sort_by = st.selectbox("Sort by", [
        "IV Discount ↓ (best value first)",
        "Closest to S1 ↑",
        "Earnings date ↑ (soonest first)",
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
elif view == "🔔 Earnings next 4 weeks":
    filtered = [r for r in filtered if r["has_earnings"]]

if sort_by == "IV Discount ↓ (best value first)":
    filtered.sort(key=lambda r: -(r["iv_discount"] or -9999))
elif sort_by == "Closest to S1 ↑":
    filtered.sort(key=lambda r: (r["price"] - r["s1"]) / r["price"] if (r["price"] and r["s1"]) else 9999)
elif sort_by == "Earnings date ↑ (soonest first)":
    filtered.sort(key=lambda r: r["earnings"]["days_away"] if r["earnings"] else 9999)
else:
    filtered.sort(key=lambda r: r["ticker"])

# Table
st.markdown(f"**{len(filtered)} positions shown**")
header_cols = st.columns([1.4, 2.2, 1.2, 1.1, 4])
for col, label in zip(header_cols, ["Ticker", "Company", "Live price", "IV discount",
                                      "Buy point ladder  (IV → S1 → S2 → S3…)"]):
    col.markdown(
        f"<span style='font-size:11px;font-weight:700;color:#6b7280;"
        f"text-transform:uppercase;letter-spacing:0.06em;'>{label}</span>",
        unsafe_allow_html=True
    )
st.markdown("<hr style='margin:4px 0 6px;border-color:#e5e7eb;'>", unsafe_allow_html=True)

for r in filtered:
    c1, c2, c3, c4, c5 = st.columns([1.4, 2.2, 1.2, 1.1, 4])
    queen_color = "#D4537E" if r["queen"] else "#1e293b"
    queen_mark  = "★ " if r["queen"] else ""

    with c1:
        st.markdown(
            f"<div style='padding-top:4px;'>"
            f"<span style='font-weight:700;font-size:14px;color:{queen_color};'>{queen_mark}{r['ticker']}</span>"
            f"{earnings_badge(r['ticker'], earnings_map)}"
            f"</div>",
            unsafe_allow_html=True
        )
    with c2:
        st.markdown(
            f"<div style='padding-top:4px;font-size:13px;color:#374151;'>{r['name']}</div>",
            unsafe_allow_html=True
        )
    with c3:
        price_str = f"${r['price']:,.2f}" if r["price"] else "—"
        st.markdown(
            f"<div style='padding-top:4px;font-weight:700;font-size:14px;'>{price_str}</div>",
            unsafe_allow_html=True
        )
    with c4:
        if r["iv_discount"] is not None:
            color = "#2d7a2d" if r["iv_discount"] > 0 else "#c0392b"
            sign  = "+" if r["iv_discount"] > 0 else ""
            st.markdown(
                f"<div style='padding-top:4px;font-weight:700;font-size:14px;color:{color};'>"
                f"{sign}{r['iv_discount']:.1f}%</div>",
                unsafe_allow_html=True
            )
        else:
            st.markdown("<div style='padding-top:4px;color:#aaa;font-size:13px;'>No IV</div>",
                        unsafe_allow_html=True)
    with c5:
        st.markdown(r["_ladder"], unsafe_allow_html=True)

    st.markdown("<hr style='margin:4px 0;border-color:#f3f4f6;'>", unsafe_allow_html=True)

st.caption(
    f"Prices from Yahoo Finance (15 min delay). "
    f"Support & IV from Google Sheet (cell K2 date: {sheet_label_date}). "
    f"Earnings dates from Yahoo Finance. Not financial advice."
)
