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

st.set_page_config(page_title="Capital Gains Portfolio", page_icon="📊", layout="wide")
st.markdown("<style>.block-container{padding-top:1.2rem;}</style>", unsafe_allow_html=True)


@st.cache_data(ttl=3600)
def load_sheet():
    url = (
        "https://docs.google.com/spreadsheets/d/"
        + SHEET_ID
        + "/gviz/tq?tqx=out:csv&gid="
        + SHEET_GID
    )
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text), header=None)
    return df


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
        st.warning("Price fetch error: " + str(e))
        return {}


@st.cache_data(ttl=86400)
def fetch_earnings(tickers):
    today  = datetime.now(SGT).date()
    cutoff = today + timedelta(days=28)
    result = {}
    for ticker in tickers:
        try:
            cal = yf.Ticker(ticker).calendar
            if cal is None or cal.empty:
                continue
            if "Earnings Date" in cal.index:
                raw   = cal.loc["Earnings Date"]
                dates = raw.values if hasattr(raw, "values") else [raw]
                for d in dates:
                    try:
                        ed = pd.Timestamp(d).date()
                        if today <= ed <= cutoff:
                            result[ticker] = {
                                "date": ed,
                                "days_away": (ed - today).days,
                                "label": ed.strftime("%d %b"),
                            }
                            break
                    except Exception:
                        continue
        except Exception:
            continue
    return result


def earnings_badge(ticker, earnings_map):
    e = earnings_map.get(ticker)
    if not e:
        return ""
    days = e["days_away"]
    bg = "#fef2f2" if days <= 7 else "#fffbeb" if days <= 14 else "#f0fdf4"
    fc = "#dc2626" if days <= 7 else "#b45309" if days <= 14 else "#166534"
    return (
        "<span style='background:" + bg + ";color:" + fc + ";"
        "font-size:10px;font-weight:700;padding:1px 6px;border-radius:4px;"
        "margin-left:4px;white-space:nowrap;'>"
        "🔔 Earnings " + e["label"] + " (" + str(days) + "d)</span>"
    )


def support_ladder_html(price, s1, s2, s3, s4, s5, iv):
    all_levels = []
    if iv:
        all_levels.append(("IV", iv, "iv"))
    for label, val in [("S1",s1),("S2",s2),("S3",s3),("S4",s4),("S5",s5)]:
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
                "<div style='margin:3px 0;'><span style='font-size:11px;font-weight:700;"
                "background:#1e293b;color:#f8fafc;padding:2px 9px;border-radius:4px;'>"
                "▶ $" + format(price, ",.2f") + " current price</span></div>"
            )
            price_inserted = True

        pct = round((price - val) / price * 100, 1) if price else 0

        if kind == "iv":
            if price >= val:
                badge = "<span style='color:#b91c1c;font-size:11px;font-weight:600;'>" + str(abs(pct)) + "% above IV</span>"
                row_s = "background:#fef2f2;border-left:3px solid #f87171;"
                lbl_s = "color:#991b1b;font-weight:700;"
            else:
                badge = "<span style='color:#1d4ed8;font-size:11px;font-weight:600;'>" + str(abs(pct)) + "% discount</span>"
                row_s = "background:#eff6ff;border-left:3px solid #3b82f6;"
                lbl_s = "color:#1e40af;font-weight:700;"
            lines.append(
                "<div style='margin:2px 0;" + row_s + "padding:3px 8px;border-radius:3px;"
                "display:flex;justify-content:space-between;align-items:center;gap:8px;'>"
                "<span style='font-size:12px;" + lbl_s + "'>📘 " + label + " $" + format(val, ",.2f") + "</span>"
                + badge + "</div>"
            )
        else:
            if price <= val:
                row_s = "background:#fef2f2;border-left:3px solid #ef4444;"
                lbl_s = "color:#991b1b;"
                badge = "<span style='color:#dc2626;font-size:11px;font-weight:700;'>HIT " + str(abs(pct)) + "% below</span>"
            elif 0 < pct < 5:
                row_s = "background:#fffbeb;border-left:3px solid #f59e0b;"
                lbl_s = "color:#78350f;"
                badge = "<span style='color:#b45309;font-size:11px;font-weight:600;'>⚠ " + str(pct) + "% away</span>"
            else:
                row_s = "background:#f8fafc;border-left:3px solid #cbd5e1;"
                lbl_s = "color:#475569;"
                badge = "<span style='color:#94a3b8;font-size:11px;'>" + str(pct) + "% above</span>"
            lines.append(
                "<div style='margin:2px 0;" + row_s + "padding:3px 8px;border-radius:3px;"
                "display:flex;justify-content:space-between;align-items:center;gap:8px;'>"
                "<span style='font-size:12px;" + lbl_s + "'>" + label + " <strong>$" + format(val, ",.2f") + "</strong></span>"
                + badge + "</div>"
            )

    if not price_inserted:
        lines.append(
            "<div style='margin:3px 0;'><span style='font-size:11px;font-weight:700;"
            "background:#1e293b;color:#f8fafc;padding:2px 9px;border-radius:4px;'>"
            "▶ $" + format(price, ",.2f") + " current price</span></div>"
        )
    return "".join(lines)


def parse_portfolio(df):
    # Find header row containing "Ticker"
    header_row = None
    for i in range(min(15, len(df))):
        row_vals = [str(v).strip().lower() for v in df.iloc[i]]
        if any("ticker" in v for v in row_vals):
            header_row = i
            break

    if header_row is None:
        return [], "Header not found", {}

    headers = [str(v).strip() for v in df.iloc[header_row]]

    # Find date in first 6 rows
    sheet_label_date = "Unknown"
    date_keywords = ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"]
    for ri in range(min(6, len(df))):
        for ci in range(df.shape[1]):
            val = str(df.iloc[ri, ci]).strip()
            if val not in ("nan","","None") and any(k in val.lower() for k in date_keywords):
                sheet_label_date = val
                break
        if sheet_label_date != "Unknown":
            break

    # Find columns by scanning header for key substrings
    # Strategy: find the FIRST col containing "support" -> that is S1, next is S2, etc
    col_ticker   = None
    col_company  = None
    col_currency = None
    col_queen    = None
    col_iv       = None
    support_cols = []
    last_price_col = None

    for idx, h in enumerate(headers):
        hl = h.lower().strip()
        if "ticker" in hl:
            col_ticker = idx
            col_queen  = idx - 1 if idx > 0 else None
        elif "company" in hl:
            col_company = idx
        elif "currency" in hl:
            col_currency = idx
        elif "support" in hl and "level" in hl:
            support_cols.append(idx)
        elif "support" in hl and len(support_cols) < 5:
            support_cols.append(idx)
        elif "base iv" in hl or (("base" in hl) and ("iv" in hl)):
            col_iv = idx
        elif "average iv" in hl or (("average" in hl) and ("iv" in hl)):
            if col_iv is None:
                col_iv = idx
        elif "last price" in hl or "last" in hl and "price" in hl:
            last_price_col = idx

    # If IV not found by name, it is typically 2 cols after last price
    if col_iv is None and last_price_col is not None:
        col_iv = last_price_col + 2

    # Map support cols to s1-s5
    col_s1 = support_cols[0] if len(support_cols) > 0 else None
    col_s2 = support_cols[1] if len(support_cols) > 1 else None
    col_s3 = support_cols[2] if len(support_cols) > 2 else None
    col_s4 = support_cols[3] if len(support_cols) > 3 else None
    col_s5 = support_cols[4] if len(support_cols) > 4 else None

    col_map = {
        "ticker": col_ticker, "company": col_company, "currency": col_currency,
        "queen": col_queen,
        "s1": col_s1, "s2": col_s2, "s3": col_s3, "s4": col_s4, "s5": col_s5,
        "iv": col_iv,
        "last_price": last_price_col,
        "all_headers": headers,
    }

    def parse_num(val):
        s = str(val).strip().replace("$","").replace(",","").replace(" ","")
        try:
            return float(s)
        except Exception:
            return None

    portfolio = []
    for idx in range(header_row + 1, len(df)):
        row = df.iloc[idx]
        ticker_raw = str(row.iloc[col_ticker]).strip() if col_ticker is not None else ""
        if not ticker_raw or ticker_raw in ("nan", "Notes:", "Ticker"):
            continue
        currency = str(row.iloc[col_currency]).strip() if col_currency is not None else ""
        if currency != "USD":
            continue
        ticker  = ticker_raw.replace("-US","").replace("-HK","")
        company = str(row.iloc[col_company]).strip() if col_company is not None else ticker
        queen_raw = str(row.iloc[col_queen]).strip() if col_queen is not None else ""
        queen = "Q" in queen_raw or "❤" in queen_raw

        portfolio.append({
            "queen": queen, "ticker": ticker, "name": company,
            "s1": parse_num(row.iloc[col_s1]) if col_s1 is not None else None,
            "s2": parse_num(row.iloc[col_s2]) if col_s2 is not None else None,
            "s3": parse_num(row.iloc[col_s3]) if col_s3 is not None else None,
            "s4": parse_num(row.iloc[col_s4]) if col_s4 is not None else None,
            "s5": parse_num(row.iloc[col_s5]) if col_s5 is not None else None,
            "iv":  parse_num(row.iloc[col_iv])  if col_iv  is not None else None,
        })

    return portfolio, sheet_label_date, col_map


def build_rows(portfolio, prices, earnings_map):
    rows = []
    for p in portfolio:
        price = prices.get(p["ticker"])
        s1,s2,s3,s4,s5,iv = p["s1"],p["s2"],p["s3"],p["s4"],p["s5"],p["iv"]
        hit_level, next_level = None, None
        for label, val in [("S1",s1),("S2",s2),("S3",s3),("S4",s4),("S5",s5)]:
            if val is None: continue
            if price and price <= val:
                hit_level = label
            elif hit_level and next_level is None:
                next_level = label + " $" + format(val, ",.0f")
                break
        iv_discount = round((iv - price) / iv * 100, 1) if (iv and price) else None
        undervalued = iv_discount is not None and iv_discount > 0
        near_s1 = bool(price and s1 and price > s1 and (price - s1) / price < 0.05)
        rows.append({
            **p, "price": price,
            "hit_level": hit_level, "next_level": next_level,
            "iv_discount": iv_discount, "undervalued": undervalued,
            "near_s1": near_s1,
            "has_earnings": p["ticker"] in earnings_map,
            "earnings": earnings_map.get(p["ticker"]),
            "_ladder": support_ladder_html(price, s1, s2, s3, s4, s5, iv),
        })
    return rows


# ── App layout ────────────────────────────────────────────────────────────────
hc1, hc2 = st.columns([4, 1])
with hc1:
    st.markdown("## 📊 Capital Gains Portfolio")
with hc2:
    if st.button("🔄 Refresh all", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

with st.spinner("Loading portfolio from Google Sheet..."):
    try:
        df = load_sheet()
    except Exception as e:
        st.error("Could not fetch Google Sheet: " + str(e))
        st.info("Ensure the sheet is shared: Share → Anyone with the link → Viewer")
        st.stop()

portfolio, sheet_label_date, col_map = parse_portfolio(df)

with st.expander("🔍 Debug: sheet structure (collapse once working)", expanded=not bool(portfolio)):
    st.write("**Columns detected:**", {k:v for k,v in col_map.items() if k != "all_headers"})
    st.write("**All headers found:**", col_map.get("all_headers", []))
    st.write("**Rows parsed:**", len(portfolio))
    st.write("**Data date:**", sheet_label_date)
    st.write("**First 12 rows:**")
    st.dataframe(df.head(12), use_container_width=True)
    if portfolio:
        st.write("**First 3 parsed rows:**", portfolio[:3])
    else:
        st.warning("No US stocks found. Share screenshot of debug info above.")
        st.stop()

tickers = tuple(p["ticker"] for p in portfolio)
now_sgt = datetime.now(SGT).strftime("%d %b %Y, %I:%M %p SGT")

st.markdown(
    "<div style='background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;"
    "padding:10px 16px;margin-bottom:12px;font-size:13px;line-height:2;'>"
    "📋 <b>Support & IV last updated:</b> "
    "<span style='color:#1e40af;font-weight:700;'>" + sheet_label_date + "</span>"
    "&nbsp;&nbsp;·&nbsp;&nbsp;"
    "💰 <b>Prices fetched:</b> <span style='color:#1e40af;font-weight:700;'>" + now_sgt + "</span>"
    "</div>",
    unsafe_allow_html=True
)

with st.spinner("Fetching live prices..."):
    prices = fetch_prices(tickers)
with st.spinner("Fetching earnings dates..."):
    earnings_map = fetch_earnings(tickers)

rows = build_rows(portfolio, prices, earnings_map)

m1,m2,m3,m4,m5 = st.columns(5)
m1.metric("Total positions",              len(rows))
m2.metric("🔴 Support hit + undervalued", sum(1 for r in rows if r["hit_level"] and r["undervalued"]))
m3.metric("🟡 Near S1 + undervalued",     sum(1 for r in rows if r["near_s1"] and r["undervalued"]))
m4.metric("✅ Below IV",                   sum(1 for r in rows if r["undervalued"]))
m5.metric("🔔 Earnings in 28 days",        len(earnings_map))

if earnings_map:
    items = " · ".join(
        t + " " + e["label"] + " (" + str(e["days_away"]) + "d)"
        for t, e in sorted(earnings_map.items(), key=lambda x: x[1]["days_away"])
    )
    st.info("🔔 Upcoming earnings: " + items)

st.divider()

fc1,fc2,fc3 = st.columns([2,2,3])
with fc1:
    view = st.selectbox("Filter", [
        "All positions","Queens only",
        "Support hit","Near S1","Undervalued","Overvalued","Earnings next 4 weeks",
    ])
with fc2:
    sort_by = st.selectbox("Sort by", [
        "IV Discount","Closest to S1","Earnings date","Ticker",
    ])
with fc3:
    search = st.text_input("Search", placeholder="Ticker or company...")

filtered = list(rows)
if search:
    q = search.lower()
    filtered = [r for r in filtered if q in r["ticker"].lower() or q in r["name"].lower()]
if view == "Queens only":        filtered = [r for r in filtered if r["queen"]]
elif view == "Support hit":      filtered = [r for r in filtered if r["hit_level"]]
elif view == "Near S1":          filtered = [r for r in filtered if r["near_s1"]]
elif view == "Undervalued":      filtered = [r for r in filtered if r["undervalued"]]
elif view == "Overvalued":       filtered = [r for r in filtered if not r["undervalued"] and r["iv_discount"] is not None]
elif view == "Earnings next 4 weeks": filtered = [r for r in filtered if r["has_earnings"]]

if sort_by == "IV Discount":
    filtered.sort(key=lambda r: -(r["iv_discount"] or -9999))
elif sort_by == "Closest to S1":
    filtered.sort(key=lambda r: (r["price"]-r["s1"])/r["price"] if (r["price"] and r["s1"]) else 9999)
elif sort_by == "Earnings date":
    filtered.sort(key=lambda r: r["earnings"]["days_away"] if r["earnings"] else 9999)
else:
    filtered.sort(key=lambda r: r["ticker"])

st.markdown("**" + str(len(filtered)) + " positions shown**")
hcols = st.columns([1.4,2.2,1.2,1.1,4])
lbls = ["Ticker","Company","Price","IV disc","Buy point ladder"]
for col, lbl in zip(hcols, lbls):
    col.markdown(
        "<span style='font-size:11px;font-weight:700;color:#6b7280;"
        "text-transform:uppercase;'>" + lbl + "</span>",
        unsafe_allow_html=True
    )
st.markdown("<hr style='margin:4px 0 6px;border-color:#e5e7eb;'>", unsafe_allow_html=True)

for r in filtered:
    c1,c2,c3,c4,c5 = st.columns([1.4,2.2,1.2,1.1,4])
    qc = "#D4537E" if r["queen"] else "#1e293b"
    qm = "★ " if r["queen"] else ""
    with c1:
        st.markdown(
            "<div style='padding-top:4px;'>"
            "<span style='font-weight:700;font-size:14px;color:" + qc + ";'>" + qm + r["ticker"] + "</span>"
            + earnings_badge(r["ticker"], earnings_map) + "</div>",
            unsafe_allow_html=True
        )
    with c2:
        st.markdown(
            "<div style='padding-top:4px;font-size:13px;color:#374151;'>" + r["name"] + "</div>",
            unsafe_allow_html=True
        )
    with c3:
        ps = "$" + format(r["price"], ",.2f") if r["price"] else "-"
        st.markdown(
            "<div style='padding-top:4px;font-weight:700;font-size:14px;'>" + ps + "</div>",
            unsafe_allow_html=True
        )
    with c4:
        if r["iv_discount"] is not None:
            cl = "#2d7a2d" if r["iv_discount"] > 0 else "#c0392b"
            sg = "+" if r["iv_discount"] > 0 else ""
            st.markdown(
                "<div style='padding-top:4px;font-weight:700;font-size:14px;color:" + cl + ";'>"
                + sg + str(r["iv_discount"]) + "%</div>",
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                "<div style='padding-top:4px;color:#aaa;font-size:13px;'>No IV</div>",
                unsafe_allow_html=True
            )
    with c5:
        st.markdown(r["_ladder"], unsafe_allow_html=True)
    st.markdown("<hr style='margin:4px 0;border-color:#f3f4f6;'>", unsafe_allow_html=True)

st.caption(
    "Prices: Yahoo Finance (15 min delay). "
    "Support & IV: Google Sheet (updated " + sheet_label_date + "). "
    "Earnings: Yahoo Finance. Not financial advice."
)
