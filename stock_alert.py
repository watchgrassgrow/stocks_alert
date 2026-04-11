"""
Capital Gains Portfolio — Daily 6pm SGT Email Alert
- Reads support levels + IV live from Google Sheet
- Fetches upcoming earnings (next 28 days) from yfinance
- Ranked email: Queens undervalued → Others undervalued → Queens overvalued → Others overvalued
- Earnings callout section at bottom

Run:
    python stock_alert.py          # scheduled loop at 6pm SGT
    python stock_alert.py --once   # send once and exit (GitHub Actions)
"""

import os, sys, smtplib, schedule, time, requests, io
import yfinance as yf
import pandas as pd
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import pytz

SGT = pytz.timezone("Asia/Singapore")

SMTP_HOST     = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER", "your_email@gmail.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "your_app_password")
TO_EMAIL      = os.getenv("TO_EMAIL", "your_email@gmail.com")
SEND_TIME_SGT = "18:00"

SHEET_ID  = "1HzoXu5c5dyq4qYn6halQixRz1CkY_JrSuk-_6izKUsQ"
SHEET_GID = "333931792"
CSV_URL   = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={SHEET_GID}"


def load_sheet():
    resp = requests.get(CSV_URL, timeout=15)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text), header=None)
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
        if str(row.iloc[5]).strip() != "USD":
            continue
        ticker = ticker_raw.replace("-US", "").replace("-HK", "")

        def parse_num(val):
            s = str(val).strip().replace("$","").replace(",","").replace(" ","")
            try: return float(s)
            except: return None

        queen_raw = str(row.iloc[1]).strip()
        portfolio.append({
            "queen": "Q" in queen_raw or "❤" in queen_raw,
            "ticker": ticker,
            "name": str(row.iloc[3]).strip(),
            "s1": parse_num(row.iloc[6]),  "s2": parse_num(row.iloc[7]),
            "s3": parse_num(row.iloc[8]),  "s4": parse_num(row.iloc[9]),
            "s5": parse_num(row.iloc[10]), "iv": parse_num(row.iloc[13]),
        })
    return portfolio, sheet_label_date


def fetch_prices(portfolio):
    tickers = [p["ticker"] for p in portfolio]
    prices = {}
    try:
        data = yf.download(tickers, period="1d", interval="1m", progress=False, auto_adjust=True)
        close = data["Close"]
        if hasattr(close, "columns"):
            for t in tickers:
                if t in close.columns:
                    val = close[t].dropna()
                    if not val.empty:
                        prices[t] = round(float(val.iloc[-1]), 2)
    except Exception as e:
        print(f"  Price fetch error: {e}")
    return prices


def fetch_earnings(portfolio):
    today   = datetime.now(SGT).date()
    cutoff  = today + timedelta(days=28)
    results = {}
    for p in portfolio:
        try:
            cal = yf.Ticker(p["ticker"]).calendar
            if cal is None or cal.empty:
                continue
            if "Earnings Date" in cal.index:
                raw = cal.loc["Earnings Date"]
                dates = raw.values if hasattr(raw, "values") else [raw]
                for d in dates:
                    try:
                        ed = pd.Timestamp(d).date()
                        if today <= ed <= cutoff:
                            results[p["ticker"]] = {
                                "name": p["name"],
                                "queen": p["queen"],
                                "date": ed,
                                "days_away": (ed - today).days,
                                "label": ed.strftime("%d %b %Y"),
                            }
                            break
                    except Exception:
                        continue
        except Exception:
            continue
    return results


def get_hit_level(price, s1, s2, s3, s4, s5):
    for label, val in [("S1",s1),("S2",s2),("S3",s3),("S4",s4),("S5",s5)]:
        if val and price <= val:
            return label
    return None


def get_next_level(price, s1, s2, s3, s4, s5):
    hit = False
    for label, val in [("S1",s1),("S2",s2),("S3",s3),("S4",s4),("S5",s5)]:
        if val is None: continue
        if price <= val: hit = True
        elif hit: return f"{label} ${val:,.0f}"
    return "—"


def build_row(p, price, hit, next_lvl, iv_discount, earnings_map):
    queen_color = "#D4537E" if p["queen"] else "#1a1a1a"
    queen_mark  = "★ " if p["queen"] else ""
    iv_str   = f"${p['iv']:,.2f}" if p["iv"] else "—"
    s1_str   = f"${p['s1']:,.2f}" if p["s1"] else "—"
    disc_str = (f"+{iv_discount:.1f}%" if iv_discount > 0 else f"{iv_discount:.1f}%") if iv_discount is not None else "—"
    disc_col = "#2d7a2d" if iv_discount and iv_discount > 0 else "#c0392b"

    level_colors = {"S1":"#c0392b","S2":"#e05c00","S3":"#b7770d","S4":"#7a3e9e","S5":"#374151"}
    if hit:
        c = level_colors.get(hit, "#555")
        hit_html = f'<span style="background:{c};color:#fff;font-size:11px;font-weight:700;padding:2px 8px;border-radius:4px;">{hit} HIT</span>'
    elif p["s1"] and price and price > p["s1"] and (price-p["s1"])/price < 0.05:
        hit_html = '<span style="background:#b7770d;color:#fff;font-size:11px;font-weight:700;padding:2px 8px;border-radius:4px;">Near S1</span>'
    else:
        hit_html = '<span style="background:#e8e8e4;color:#555;font-size:11px;padding:2px 8px;border-radius:4px;">Above supports</span>'

    # Earnings badge
    earn_html = ""
    if p["ticker"] in earnings_map:
        e = earnings_map[p["ticker"]]
        days = e["days_away"]
        bg   = "#fef2f2" if days <= 7 else "#fffbeb" if days <= 14 else "#f0fdf4"
        fc   = "#dc2626" if days <= 7 else "#b45309" if days <= 14 else "#166534"
        earn_html = (f'<br><span style="background:{bg};color:{fc};border:1px solid {fc}44;'
                     f'font-size:10px;font-weight:700;padding:1px 6px;border-radius:4px;">'
                     f'🔔 Earnings {e["label"]} (in {days}d)</span>')

    return f"""
    <tr style="border-top:1px solid #f0f0ee;">
      <td style="padding:8px 10px;font-weight:700;color:{queen_color};">{queen_mark}{p['ticker']}{earn_html}</td>
      <td style="padding:8px 10px;color:#444;font-size:13px;">{p['name']}</td>
      <td style="padding:8px 10px;font-weight:700;text-align:right;">${price:,.2f}</td>
      <td style="padding:8px 10px;text-align:right;color:#555;">{s1_str}</td>
      <td style="padding:8px 10px;text-align:center;">{hit_html}
        <div style="font-size:11px;color:#888;margin-top:2px;">next: {next_lvl}</div></td>
      <td style="padding:8px 10px;text-align:right;color:#555;">{iv_str}</td>
      <td style="padding:8px 10px;text-align:right;font-weight:700;color:{disc_col};">{disc_str}</td>
    </tr>"""


def make_section(title, accent, rows_html, empty_msg):
    body = rows_html or f'<tr><td colspan="7" style="padding:16px;color:#888;text-align:center;">{empty_msg}</td></tr>'
    headers = ["Ticker","Company","Price","Support 1","Support status","Base IV","IV Disc/Prem"]
    th = "".join(f'<th style="padding:8px 10px;font-weight:700;color:{accent};font-size:11px;text-transform:uppercase;letter-spacing:0.05em;text-align:left;">{h}</th>' for h in headers)
    return f"""
    <h2 style="margin:28px 0 8px;font-size:14px;font-weight:700;color:{accent};
               border-left:3px solid {accent};padding-left:10px;text-transform:uppercase;">{title}</h2>
    <table width="100%" cellpadding="0" cellspacing="0"
           style="border-collapse:collapse;border:1px solid #e8e8e8;border-radius:8px;
                  overflow:hidden;font-family:system-ui,sans-serif;font-size:13px;">
      <thead><tr style="background:#f7f7f5;">{th}</tr></thead>
      <tbody>{body}</tbody>
    </table>"""


def build_and_send():
    print(f"[{datetime.now(SGT).strftime('%Y-%m-%d %H:%M')} SGT] Loading sheet…")
    portfolio, sheet_label_date = load_sheet()
    print(f"  Sheet K2 date: {sheet_label_date} · {len(portfolio)} US stocks loaded")

    prices      = fetch_prices(portfolio)
    earnings_map = fetch_earnings(portfolio)
    print(f"  Earnings found for {len(earnings_map)} stocks in next 28 days")

    queens_under, others_under, queens_over, others_over = [], [], [], []

    for p in portfolio:
        price = prices.get(p["ticker"])
        if price is None or p["iv"] is None:
            continue
        hit      = get_hit_level(price, p["s1"], p["s2"], p["s3"], p["s4"], p["s5"])
        next_lvl = get_next_level(price, p["s1"], p["s2"], p["s3"], p["s4"], p["s5"])
        iv_disc  = round((p["iv"] - price) / p["iv"] * 100, 1)
        row      = build_row(p, price, hit, next_lvl, iv_disc, earnings_map)

        if iv_disc > 0:
            (queens_under if p["queen"] else others_under).append((iv_disc, row))
        else:
            (queens_over  if p["queen"] else others_over ).append((iv_disc, row))

    for lst in [queens_under, others_under]:
        lst.sort(key=lambda x: -x[0])
    for lst in [queens_over, others_over]:
        lst.sort(key=lambda x: -x[0])

    # Earnings section HTML
    earn_rows = ""
    if earnings_map:
        sorted_earn = sorted(earnings_map.items(), key=lambda x: x[1]["days_away"])
        for ticker, e in sorted_earn:
            days = e["days_away"]
            bg   = "#fef2f2" if days <= 7 else "#fffbeb" if days <= 14 else "#f0fdf4"
            fc   = "#dc2626" if days <= 7 else "#b45309" if days <= 14 else "#166534"
            earn_rows += f"""
            <tr style="border-top:1px solid #f0f0ee;">
              <td style="padding:8px 10px;font-weight:700;">{'★ ' if e['queen'] else ''}{ticker}</td>
              <td style="padding:8px 10px;color:#444;">{e['name']}</td>
              <td style="padding:8px 10px;text-align:center;">
                <span style="background:{bg};color:{fc};font-size:12px;font-weight:700;
                             padding:3px 10px;border-radius:4px;">📅 {e['label']}</span>
              </td>
              <td style="padding:8px 10px;text-align:center;color:{fc};font-weight:600;">in {days} days</td>
            </tr>"""

    earnings_section = ""
    if earn_rows:
        earnings_section = f"""
        <h2 style="margin:28px 0 8px;font-size:14px;font-weight:700;color:#1e40af;
                   border-left:3px solid #3b82f6;padding-left:10px;text-transform:uppercase;">
          🔔 Upcoming Earnings — Next 4 Weeks</h2>
        <table width="100%" cellpadding="0" cellspacing="0"
               style="border-collapse:collapse;border:1px solid #bfdbfe;border-radius:8px;
                      overflow:hidden;font-family:system-ui,sans-serif;font-size:13px;">
          <thead><tr style="background:#eff6ff;">
            {"".join(f'<th style="padding:8px 10px;font-weight:700;color:#1e40af;font-size:11px;text-transform:uppercase;letter-spacing:0.05em;text-align:left;">{h}</th>'
                     for h in ["Ticker","Company","Earnings Date","Days Away"])}
          </tr></thead>
          <tbody>{earn_rows}</tbody>
        </table>"""

    now_str = datetime.now(SGT).strftime("%d %b %Y, %I:%M %p SGT")

    html = f"""<!DOCTYPE html><html><body style="margin:0;padding:0;background:#f4f4f0;
font-family:system-ui,-apple-system,sans-serif;">
<div style="max-width:780px;margin:24px auto;background:#fff;border-radius:12px;
            overflow:hidden;border:1px solid #e0e0da;">

  <div style="background:#fff;border-bottom:1px solid #e8e8e4;padding:24px 28px 18px;">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
      <div style="width:30px;height:30px;background:#D4537E;border-radius:7px;
                  display:flex;align-items:center;justify-content:center;">
        <span style="color:#fff;font-size:15px;">★</span></div>
      <span style="font-size:12px;font-weight:700;letter-spacing:0.08em;
                   color:#D4537E;text-transform:uppercase;">Piranha Profits</span>
    </div>
    <h1 style="margin:0;font-size:22px;font-weight:700;color:#1a1a1a;">
      Capital Gains Portfolio Alert</h1>
    <p style="margin:4px 0 0;font-size:13px;color:#888;">
      {now_str} &nbsp;·&nbsp; US Stocks &nbsp;·&nbsp; ★ = Heavenly Queen</p>
    <div style="margin-top:10px;padding:8px 12px;background:#f0f7ff;border-radius:6px;
                border-left:3px solid #3b82f6;font-size:12px;color:#1e40af;">
      📋 <b>Support & IV data (per sheet cell K2):</b> {sheet_label_date}
      &nbsp;—&nbsp; <i>update cell L2 in the sheet to reflect the latest data date</i>
    </div>
  </div>

  <div style="background:#fffbf2;border-bottom:1px solid #f0e8d0;padding:9px 28px;">
    <span style="font-size:11px;font-weight:700;color:#888;text-transform:uppercase;
                 letter-spacing:0.05em;margin-right:8px;">Support triggers:</span>
    {"".join(f'<span style="background:{c};color:#fff;font-size:11px;font-weight:700;padding:2px 7px;border-radius:4px;margin-right:6px;">{l}</span>'
             for l,c in [("S1","#c0392b"),("S2","#e05c00"),("S3","#b7770d"),("S4","#7a3e9e"),("S5","#374151")])}
  </div>

  <div style="padding:16px 28px 32px;">
    {make_section("★ Heavenly Queens — Undervalued","#D4537E","".join(r for _,r in queens_under),"No Queens undervalued today.")}
    {make_section("Other US Stocks — Undervalued","#2d7a2d","".join(r for _,r in others_under),"No other stocks undervalued today.")}
    {make_section("★ Heavenly Queens — Overvalued","#a32d2d","".join(r for _,r in queens_over),"No Queens overvalued.")}
    {make_section("Other US Stocks — Overvalued","#c0392b","".join(r for _,r in others_over),"No other stocks overvalued.")}
    {earnings_section}
    <p style="margin-top:24px;font-size:11px;color:#bbb;border-top:1px solid #eee;
              padding-top:14px;line-height:1.8;">
      Prices from Yahoo Finance (up to 15 min delay). Support & IV from Google Sheet
      (K2 date: {sheet_label_date}). Earnings dates from Yahoo Finance.
      For informational purposes only — not financial advice. &copy; 2026 Piranha Profits.
    </p>
  </div>
</div></body></html>"""

    subject = (f"📊 Portfolio Alert — {datetime.now(SGT).strftime('%d %b %Y')} · "
               f"Data: {sheet_label_date}"
               + (f" · 🔔 {len(earnings_map)} earnings" if earnings_map else ""))

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SMTP_USER
    msg["To"]      = TO_EMAIL
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo(); server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, TO_EMAIL, msg.as_string())

    print(f"  ✓ Email sent · Subject: {subject}")


if __name__ == "__main__":
    if "--once" in sys.argv:
        build_and_send()
    else:
        print(f"Scheduler started — sending daily at {SEND_TIME_SGT} SGT")
        schedule.every().day.at(SEND_TIME_SGT).do(build_and_send)
        while True:
            schedule.run_pending()
            time.sleep(30)
