“””
Capital Gains Portfolio — Real-time Dashboard
“””

import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz
import io

SGT = pytz.timezone(“Asia/Singapore”)

SHEET_ID  = “1HzoXu5c5dyq4qYn6halQixRz1CkY_JrSuk-_6izKUsQ”
SHEET_GID = “333931792”

st.set_page_config(page_title=“Capital Gains Portfolio”, page_icon=“📊”, layout=“wide”)
st.markdown(”<style>.block-container{padding-top:1.2rem;}</style>”, unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def load_sheet():
url = (f”https://docs.google.com/spreadsheets/d/{SHEET_ID}”
f”/gviz/tq?tqx=out:csv&gid={SHEET_GID}”)
headers = {“User-Agent”: “Mozilla/5.0”}
resp = requests.get(url, headers=headers, timeout=20)
resp.raise_for_status()
raw = resp.text
df = pd.read_csv(io.StringIO(raw), header=None)
return df, raw[:2000]  # return df + first 2000 chars for debugging

@st.cache_data(ttl=300)
def fetch_prices(tickers):
try:
data = yf.download(list(tickers), period=“1d”, interval=“1m”,
progress=False, auto_adjust=True)
prices = {}
close = data[“Close”]
if hasattr(close, “columns”):
for t in tickers:
if t in close.columns:
val = close[t].dropna()
if not val.empty:
prices[t] = round(float(val.iloc[-1]), 2)
return prices
except Exception as e:
st.warning(f”Price fetch error: {e}”)
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
if “Earnings Date” in cal.index:
raw   = cal.loc[“Earnings Date”]
dates = raw.values if hasattr(raw, “values”) else [raw]
for d in dates:
try:
ed = pd.Timestamp(d).date()
if today <= ed <= cutoff:
result[ticker] = {
“date”: ed,
“days_away”: (ed - today).days,
“label”: ed.strftime(”%d %b”),
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
return “”
days = e[“days_away”]
bg   = “#fef2f2” if days <= 7 else “#fffbeb” if days <= 14 else “#f0fdf4”
fc   = “#dc2626” if days <= 7 else “#b45309” if days <= 14 else “#166534”
return (f”<span style='background:{bg};color:{fc};border:1px solid {fc}44;"
f"font-size:10px;font-weight:700;padding:1px 6px;border-radius:4px;"
f"margin-left:4px;white-space:nowrap;'>”
f”🔔 Earnings {e[‘label’]} ({days}d)</span>”)

def support_ladder_html(price, s1, s2, s3, s4, s5, iv):
all_levels = []
if iv:
all_levels.append((“IV”, iv, “iv”))
for label, val in [(“S1”,s1),(“S2”,s2),(“S3”,s3),(“S4”,s4),(“S5”,s5)]:
if val is not None:
all_levels.append((label, val, “support”))
all_levels.sort(key=lambda x: x[1], reverse=True)

```
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
```

def parse_portfolio(df):
“””
Auto-detect the header row and data rows by scanning for ‘Ticker’ keyword,
then parse currency, support levels and IV from correct columns.
“””

```
# Step 1: find the header row (contains "Ticker")
header_row = None
for i in range(min(15, len(df))):
    row_vals = [str(v).strip().lower() for v in df.iloc[i]]
    if any("ticker" in v for v in row_vals):
        header_row = i
        break

if header_row is None:
    return [], "Header row not found", {}

headers = [str(v).strip() for v in df.iloc[header_row]]

# Step 2: find column indices by header name
def find_col(keywords):
    for idx, h in enumerate(headers):
        hl = h.lower()
        if all(k.lower() in hl for k in keywords):
            return idx
    return None

col_ticker   = find_col(["ticker"])
col_company  = find_col(["company"])
col_currency = find_col(["currency"])
col_s1       = find_col(["support", "1"])
col_s2       = find_col(["support", "2"])
col_s3       = find_col(["support", "3"])
col_s4       = find_col(["support", "4"])
col_s5       = find_col(["support", "5"])
col_iv       = find_col(["base", "iv"])
if col_iv is None:
    col_iv = find_col(["average", "iv"])

# Column B (queen marker) is always one left of ticker
col_queen = (col_ticker - 1) if col_ticker and col_ticker > 0 else None

# Find the date: scan rows 0-5 for a month keyword
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

col_map = {
    "ticker": col_ticker, "company": col_company, "currency": col_currency,
    "s1": col_s1, "s2": col_s2, "s3": col_s3, "s4": col_s4, "s5": col_s5,
    "iv": col_iv, "queen": col_queen,
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

    # Stop at empty or notes rows
    ticker_raw = str(row.iloc[col_ticker]).strip() if col_ticker is not None else ""
    if not ticker_raw or ticker_raw in ("nan", "Notes:", "Ticker"):
        continue

    currency = str(row.iloc[col_currency]).strip() if col_currency is not None else ""
    if currency != "USD":
        continue

    ticker  = ticker_raw.replace("-US","").replace("-HK","")
    company = str(row.iloc[col_company]).strip() if col_company is not None else ticker

    queen_raw = str(row.iloc[col_queen]).strip() if col_queen is not None else ""
    queen = "Q" in queen_raw or "❤" in queen_raw or "q" in queen_raw.lower()

    portfolio.append({
        "queen":   queen,
        "ticker":  ticker,
        "name":    company,
        "s1": parse_num(row.iloc[col_s1]) if col_s1 is not None else None,
        "s2": parse_num(row.iloc[col_s2]) if col_s2 is not None else None,
        "s3": parse_num(row.iloc[col_s3]) if col_s3 is not None else None,
        "s4": parse_num(row.iloc[col_s4]) if col_s4 is not None else None,
        "s5": parse_num(row.iloc[col_s5]) if col_s5 is not None else None,
        "iv": parse_num(row.iloc[col_iv]) if col_iv is not None else None,
    })

return portfolio, sheet_label_date, col_map
```

def build_rows(portfolio, prices, earnings_map):
rows = []
for p in portfolio:
price = prices.get(p[“ticker”])
s1,s2,s3,s4,s5,iv = p[“s1”],p[“s2”],p[“s3”],p[“s4”],p[“s5”],p[“iv”]

```
    hit_level, next_level = None, None
    for label, val in [("S1",s1),("S2",s2),("S3",s3),("S4",s4),("S5",s5)]:
        if val is None: continue
        if price and price <= val:
            hit_level = label
        elif hit_level and next_level is None:
            next_level = f"{label} ${val:,.0f}"
            break

    iv_discount = round((iv - price) / iv * 100, 1) if (iv and price) else None
    undervalued = iv_discount is not None and iv_discount > 0
    near_s1     = bool(price and s1 and price > s1 and (price - s1) / price < 0.05)

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
```

# ── App layout ────────────────────────────────────────────────────────────────

hc1, hc2 = st.columns([4, 1])
with hc1:
st.markdown(”## 📊 Capital Gains Portfolio”)
with hc2:
if st.button(“🔄 Refresh all”, use_container_width=True):
st.cache_data.clear()
st.rerun()

with st.spinner(“Loading portfolio from Google Sheet…”):
try:
df, raw_preview = load_sheet()
except Exception as e:
st.error(f”**Could not fetch Google Sheet.** {e}”)
st.info(“Ensure the sheet is shared: **Share → Anyone with the link → Viewer**”)
st.stop()

portfolio, sheet_label_date, col_map = parse_portfolio(df)

# ── Debug expander — shows raw sheet so we can verify structure ───────────────

with st.expander(“🔍 Debug: raw sheet structure (first 12 rows)”, expanded=not bool(portfolio)):
st.write(”**Column map detected:**”, col_map)
st.write(”**Rows detected in portfolio:**”, len(portfolio))
st.write(f”**Date found:** {sheet_label_date}”)
st.write(”**First 12 rows of sheet:**”)
st.dataframe(df.head(12), use_container_width=True)
if not portfolio:
st.warning(“No US stocks parsed. Use the table above to identify the correct row/column layout and report back.”)
st.stop()

tickers = tuple(p[“ticker”] for p in portfolio)

now_sgt = datetime.now(SGT).strftime(”%d %b %Y, %I:%M %p SGT”)
st.markdown(
f”<div style='background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;"
f"padding:10px 16px;margin-bottom:12px;font-size:13px;line-height:2;'>”
f”📋 <b>Support & IV last updated:</b> “
f”<span style='color:#1e40af;font-weight:700;'>{sheet_label_date}</span>”
f”  ·  ”
f”💰 <b>Prices fetched:</b> <span style='color:#1e40af;font-weight:700;'>{now_sgt}</span>”
f”</div>”,
unsafe_allow_html=True
)

with st.spinner(“Fetching live prices…”):
prices = fetch_prices(tickers)
with st.spinner(“Fetching earnings dates…”):
earnings_map = fetch_earnings(tickers)

rows = build_rows(portfolio, prices, earnings_map)

m1,m2,m3,m4,m5 = st.columns(5)
m1.metric(“Total positions”,             len(rows))
m2.metric(“🔴 Support hit + undervalued”, sum(1 for r in rows if r[“hit_level”] and r[“undervalued”]))
m3.metric(“🟡 Near S1 + undervalued”,     sum(1 for r in rows if r[“near_s1”] and r[“undervalued”]))
m4.metric(“✅ Below IV”,                   sum(1 for r in rows if r[“undervalued”]))
m5.metric(“🔔 Earnings ≤28 days”,          len(earnings_map))

if earnings_map:
items = “  ·  “.join(
f”<b>{t}</b> {e[‘label’]} ({e[‘days_away’]}d)”
for t, e in sorted(earnings_map.items(), key=lambda x: x[1][“days_away”])
)
st.markdown(
f”<div style='background:#fffbeb;border:1px solid #f59e0b;border-radius:8px;"
f"padding:10px 16px;margin-bottom:4px;font-size:13px;'>”
f”🔔 <b>Upcoming earnings:</b>  {items}</div>”,
unsafe_allow_html=True
)

st.divider()

fc1,fc2,fc3 = st.columns([2,2,3])
with fc1:
view = st.selectbox(“Filter”, [
“All positions”,“★ Heavenly Queens only”,
“🔴 Support hit”,“🟡 Near S1 (<5%)”,
“✅ Undervalued (below IV)”,“🔺 Overvalued (above IV)”,
“🔔 Earnings next 4 weeks”,
])
with fc2:
sort_by = st.selectbox(“Sort by”, [
“IV Discount ↓”,“Closest to S1 ↑”,“Earnings date ↑”,“Ticker A–Z”,
])
with fc3:
search = st.text_input(“Search”, placeholder=“Ticker or company…”)

filtered = list(rows)
if search:
q = search.lower()
filtered = [r for r in filtered if q in r[“ticker”].lower() or q in r[“name”].lower()]
if view == “★ Heavenly Queens only”:       filtered = [r for r in filtered if r[“queen”]]
elif view == “🔴 Support hit”:             filtered = [r for r in filtered if r[“hit_level”]]
elif view == “🟡 Near S1 (<5%)”:           filtered = [r for r in filtered if r[“near_s1”]]
elif view == “✅ Undervalued (below IV)”:  filtered = [r for r in filtered if r[“undervalued”]]
elif view == “🔺 Overvalued (above IV)”:  filtered = [r for r in filtered if not r[“undervalued”] and r[“iv_discount”] is not None]
elif view == “🔔 Earnings next 4 weeks”:  filtered = [r for r in filtered if r[“has_earnings”]]

if sort_by == “IV Discount ↓”:
filtered.sort(key=lambda r: -(r[“iv_discount”] or -9999))
elif sort_by == “Closest to S1 ↑”:
filtered.sort(key=lambda r: (r[“price”]-r[“s1”])/r[“price”] if (r[“price”] and r[“s1”]) else 9999)
elif sort_by == “Earnings date ↑”:
filtered.sort(key=lambda r: r[“earnings”][“days_away”] if r[“earnings”] else 9999)
else:
filtered.sort(key=lambda r: r[“ticker”])

st.markdown(f”**{len(filtered)} positions shown**”)
hcols = st.columns([1.4,2.2,1.2,1.1,4])
for col, lbl in zip(hcols, [“Ticker”,“Company”,“Live price”,“IV discount”,
“Buy point ladder  (IV → S1 → S2 → S3…)”]):
col.markdown(
f”<span style='font-size:11px;font-weight:700;color:#6b7280;"
f"text-transform:uppercase;letter-spacing:0.06em;'>{lbl}</span>”,
unsafe_allow_html=True
)
st.markdown(”<hr style='margin:4px 0 6px;border-color:#e5e7eb;'>”, unsafe_allow_html=True)

for r in filtered:
c1,c2,c3,c4,c5 = st.columns([1.4,2.2,1.2,1.1,4])
qc = “#D4537E” if r[“queen”] else “#1e293b”
qm = “★ “ if r[“queen”] else “”

```
with c1:
    st.markdown(
        f"<div style='padding-top:4px;'>"
        f"<span style='font-weight:700;font-size:14px;color:{qc};'>{qm}{r['ticker']}</span>"
        f"{earnings_badge(r['ticker'], earnings_map)}</div>",
        unsafe_allow_html=True
    )
with c2:
    st.markdown(f"<div style='padding-top:4px;font-size:13px;color:#374151;'>{r['name']}</div>",
                unsafe_allow_html=True)
with c3:
    ps = f"${r['price']:,.2f}" if r["price"] else "—"
    st.markdown(f"<div style='padding-top:4px;font-weight:700;font-size:14px;'>{ps}</div>",
                unsafe_allow_html=True)
with c4:
    if r["iv_discount"] is not None:
        cl = "#2d7a2d" if r["iv_discount"] > 0 else "#c0392b"
        sg = "+" if r["iv_discount"] > 0 else ""
        st.markdown(
            f"<div style='padding-top:4px;font-weight:700;font-size:14px;color:{cl};'>"
            f"{sg}{r['iv_discount']:.1f}%</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div style='padding-top:4px;color:#aaa;font-size:13px;'>No IV</div>",
                    unsafe_allow_html=True)
with c5:
    st.markdown(r["_ladder"], unsafe_allow_html=True)

st.markdown("<hr style='margin:4px 0;border-color:#f3f4f6;'>", unsafe_allow_html=True)
```

st.caption(
f”Prices: Yahoo Finance (15 min delay). “
f”Support & IV: Google Sheet (updated {sheet_label_date}). “
f”Earnings: Yahoo Finance. Not financial advice.”
)
