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

# Column positions confirmed from debug output:
# col 1  = queen marker
# col 2  = ticker
# col 3  = company
# col 4  = currency
# col 5  = support level 1 (nan header due to merged cells)
# col 6  = support level 2
# col 7  = support level 3
# col 8  = support level 4
# col 9  = support level 5
# col 10 = last price
# col 11 = conservative IV
# col 12 = base IV  (we want this one)
# col 13 = average IV

COL_QUEEN    = 1
COL_TICKER   = 2
COL_COMPANY  = 3
COL_CURRENCY = 4
COL_S1       = 5
COL_S2       = 6
COL_S3       = 7
COL_S4       = 8
COL_S5       = 9
COL_PRICE    = 10
COL_IV_BASE  = 12


@st.cache_data(ttl=3600)
def load_sheet():
    url = (
        "https://docs.google.com/spreadsheets/d/"
        + SHEET_ID
        + "/gviz/tq?tqx=out:csv&gid="
        + SHEET_GID
    )
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text), header=None)

    # Find date — scan first 6 rows for month name
    sheet_date = "Unknown"
    months = ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"]
    for ri in range(min(6, len(df))):
        for ci in range(df.shape[1]):
            val = str(df.iloc[ri, ci]).strip()
            if val not in ("nan","","None") and any(m in val.lower() for m in months):
                sheet_date = val
                break
        if sheet_date != "Unknown":
            break

    def parse_num(val):
        s = str(val).strip().replace("$","").replace(",","").replace(" ","")
        try:
            return float(s)
        except Exception:
            return None

    # Find header row (contains "Ticker")
    header_row = 6
    for i in range(15):
        row_vals = [str(v).strip().lower() for v in df.iloc[i]]
        if any("ticker" in v for v in row_vals):
            header_row = i
            break

    portfolio = []
    for idx in range(header_row + 1, len(df)):
        row = df.iloc[idx]
        ticker_raw = str(row.iloc[COL_TICKER]).strip()
        if not ticker_raw or ticker_raw in ("nan","Notes:","Ticker"):
            continue
        currency = str(row.iloc[COL_CURRENCY]).strip()
        if currency != "USD":
            continue

        ticker    = ticker_raw.replace("-US","").replace("-HK","")
        company   = str(row.iloc[COL_COMPANY]).strip()
        queen_raw = str(row.iloc[COL_QUEEN]).strip()
        queen     = "Q" in queen_raw or "❤" in queen_raw

        s1 = parse_num(row.iloc[COL_S1])
        s2 = parse_num(row.iloc[COL_S2])
        s3 = parse_num(row.iloc[COL_S3])
        s4 = parse_num(row.iloc[COL_S4])
        s5 = parse_num(row.iloc[COL_S5])
        iv = parse_num(row.iloc[COL_IV_BASE])

        portfolio.append({
            "queen": queen, "ticker": ticker, "name": company,
            "s1": s1, "s2": s2, "s3": s3, "s4": s4, "s5": s5, "iv": iv,
        })

    return df, portfolio, sheet_date


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
        "🔔 " + e["label"] + " (" + str(days) + "d)</span>"
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
                "<div style='margin:3px 0;'>"
                "<span style='font-size:11px;font-weight:700;background:#1e293b;"
                "color:#f8fafc;padding:2px 9px;border-radius:4px;'>"
                "▶ $" + format(price, ",.2f") + " now</span></div>"
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
                "display:flex;justify-content:space-between;align-items:center;'>"
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
                badge = "<span style='color:#b45309;font-size:11px;'>" + str(pct) + "% away ⚠</span>"
            else:
                row_s = "background:#f8fafc;border-left:3px solid #cbd5e1;"
                lbl_s = "color:#475569;"
                badge = "<span style='color:#94a3b8;font-size:11px;'>" + str(pct) + "% above</span>"
            lines.append(
                "<div style='margin:2px 0;" + row_s + "padding:3px 8px;border-radius:3px;"
                "display:flex;justify-content:space-between;align-items:center;'>"
                "<span style='font-size:12px;" + lbl_s + "'>" + label + " <strong>$" + format(val, ",.2f") + "</strong></span>"
                + badge + "</div>"
            )

    if not price_inserted:
        lines.append(
            "<div style='margin:3px 0;'>"
            "<span style='font-size:11px;font-weight:700;background:#1e293b;"
            "color:#f8fafc;padding:2px 9px;border-radius:4px;'>"
            "▶ $" + format(price, ",.2f") + " now</span></div>"
        )
    return "".join(lines)


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


# ── Layout ────────────────────────────────────────────────────────────────────
hc1, hc2 = st.columns([4, 1])
with hc1:
    st.markdown("## 📊 Capital Gains Portfolio")
with hc2:
    if st.button("🔄 Refresh all", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

with st.spinner("Loading portfolio from Google Sheet..."):
    try:
        df, portfolio, sheet_date = load_sheet()
    except Exception as e:
        st.error("Could not fetch Google Sheet: " + str(e))
        st.info("Ensure sheet is shared: Share → Anyone with the link → Viewer")
        st.stop()

# Debug expander — keep visible until confirmed working
with st.expander("🔍 Debug (collapse once data looks correct)", expanded=not bool(portfolio)):
    st.write("Rows parsed: " + str(len(portfolio)))
    st.write("Date found: " + sheet_date)
    st.write("First 3 stocks:", portfolio[:3] if portfolio else "none")
    st.write("Raw sheet row 8 (first data row):")
    st.write(list(df.iloc[7]))
    if not portfolio:
        st.stop()

tickers = tuple(p["ticker"] for p in portfolio)
now_sgt = datetime.now(SGT).strftime("%d %b %Y, %I:%M %p SGT")

st.markdown(
    "<div style='background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;"
    "padding:10px 16px;margin-bottom:12px;font-size:13px;'>"
    "📋 <b>Support & IV data:</b> "
    "<span style='color:#1e40af;font-weight:700;'>" + sheet_date + "</span>"
    " &nbsp;·&nbsp; "
    "💰 <b>Prices:</b> <span style='color:#1e40af;font-weight:700;'>" + now_sgt + "</span>"
    "</div>",
    unsafe_allow_html=True
)

with st.spinner("Fetching live prices..."):
    prices = fetch_prices(tickers)
with st.spinner("Fetching earnings dates..."):
    earnings_map = fetch_earnings(tickers)

rows = build_rows(portfolio, prices, earnings_map)

m1,m2,m3,m4,m5 = st.columns(5)
m1.metric("Positions",                   len(rows))
m2.metric("🔴 Support hit+undervalued",  sum(1 for r in rows if r["hit_level"] and r["undervalued"]))
m3.metric("🟡 Near S1+undervalued",      sum(1 for r in rows if r["near_s1"] and r["undervalued"]))
m4.metric("✅ Below IV",                  sum(1 for r in rows if r["undervalued"]))
m5.metric("🔔 Earnings ≤28d",            len(earnings_map))

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
        "All","Queens only","Support hit","Near S1",
        "Undervalued","Overvalued","Earnings next 4 weeks",
    ], index=1)
with fc2:
    sort_by = st.selectbox("Sort by", ["IV Discount","Closest to S1","Earnings date","Ticker"])
with fc3:
    search = st.text_input("Search", placeholder="Ticker or company...")

filtered = list(rows)
if search:
    q = search.lower()
    filtered = [r for r in filtered if q in r["ticker"].lower() or q in r["name"].lower()]
if view == "Queens only":             filtered = [r for r in filtered if r["queen"]]
elif view == "Support hit":           filtered = [r for r in filtered if r["hit_level"]]
elif view == "Near S1":               filtered = [r for r in filtered if r["near_s1"]]
elif view == "Undervalued":           filtered = [r for r in filtered if r["undervalued"]]
elif view == "Overvalued":            filtered = [r for r in filtered if not r["undervalued"] and r["iv_discount"] is not None]
elif view == "Earnings next 4 weeks": filtered = [r for r in filtered if r["has_earnings"]]

if sort_by == "IV Discount":
    filtered.sort(key=lambda r: -(r["iv_discount"] or -9999))
elif sort_by == "Closest to S1":
    filtered.sort(key=lambda r: (r["price"]-r["s1"])/r["price"] if (r["price"] and r["s1"]) else 9999)
elif sort_by == "Earnings date":
    filtered.sort(key=lambda r: r["earnings"]["days_away"] if r["earnings"] else 9999)
else:
    filtered.sort(key=lambda r: r["ticker"])

st.markdown("**" + str(len(filtered)) + " positions**")
hcols = st.columns([1.4,2.2,1.2,1.1,4])
for col, lbl in zip(hcols, ["Ticker","Company","Price","IV disc","Buy ladder (IV→S1→S2→S3...)"]):
    col.markdown(
        "<span style='font-size:11px;font-weight:700;color:#6b7280;text-transform:uppercase;'>"
        + lbl + "</span>", unsafe_allow_html=True
    )
st.markdown("<hr style='margin:4px 0 6px;border-color:#e5e7eb;'>", unsafe_allow_html=True)

for r in filtered:
    c1,c2,c3,c4,c5 = st.columns([1.4,2.2,1.2,1.1,4])
    qc = "#D4537E" if r["queen"] else "#1e293b"
    qm = "★ " if r["queen"] else ""
    with c1:
        st.markdown(
            "<div style='padding-top:4px;'>"
            "<span style='font-weight:700;font-size:14px;color:" + qc + ";'>"
            + qm + r["ticker"] + "</span>"
            + earnings_badge(r["ticker"], earnings_map) + "</div>",
            unsafe_allow_html=True
        )
    with c2:
        st.markdown(
            "<div style='padding-top:4px;font-size:13px;color:#374151;'>"
            + r["name"] + "</div>", unsafe_allow_html=True
        )
    with c3:
        ps = "$" + format(r["price"], ",.2f") if r["price"] else "-"
        st.markdown(
            "<div style='padding-top:4px;font-weight:700;font-size:14px;'>"
            + ps + "</div>", unsafe_allow_html=True
        )
    with c4:
        if r["iv_discount"] is not None:
            cl = "#2d7a2d" if r["iv_discount"] > 0 else "#c0392b"
            sg = "+" if r["iv_discount"] > 0 else ""
            st.markdown(
                "<div style='padding-top:4px;font-weight:700;font-size:14px;color:" + cl + ";'>"
                + sg + str(r["iv_discount"]) + "%</div>", unsafe_allow_html=True
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
    "Support & IV: Google Sheet (" + sheet_date + "). "
    "Earnings: Yahoo Finance. Not financial advice."
)
