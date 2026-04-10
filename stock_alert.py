"""
Capital Gains Portfolio — Daily 6pm SGT Email Alert
Sends a ranked email: undervalued Queens first, then other US stocks undervalued,
then overvalued stocks at the bottom.

Requirements:
    pip install yfinance schedule pytz

Configuration:
    Set the environment variables below or edit the CONFIG section directly.
"""

import os
import smtplib
import schedule
import time
import yfinance as yf
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
import pytz

# ─── CONFIG ────────────────────────────────────────────────────────────────────
SMTP_HOST     = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER", "your_email@gmail.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "your_app_password")
TO_EMAIL      = os.getenv("TO_EMAIL", "your_email@gmail.com")
SEND_TIME_SGT = "18:00"   # 6pm Singapore Time
SGT           = pytz.timezone("Asia/Singapore")
# ───────────────────────────────────────────────────────────────────────────────

PORTFOLIO = [
    # queen, ticker (Yahoo Finance), company, currency, s1, s2, s3, s4, base_iv
    (True,  "AAPL",  "Apple Inc",                    "USD", 196,  180,  165,  None, 198),
    (True,  "AMZN",  "Amazon.com, Inc.",              "USD", 218,  188,  161,  146,  229),
    (True,  "GOOGL", "Alphabet Inc",                 "USD", 275,  256,  236,  224,  291.55),
    (True,  "MA",    "Mastercard Inc",               "USD", 527,  502,  464,  428,  529),
    (True,  "META",  "Meta Platforms Inc",           "USD", 734,  690,  649,  598,  815),
    (True,  "MSFT",  "Microsoft Corporation",        "USD", 493,  466,  431,  387,  537),
    (True,  "NVDA",  "NVIDIA Corporation",           "USD", 181,  153,  130,  90,   210),
    (True,  "PANW",  "Palo Alto Networks",           "USD", 191,  177,  165,  145,  202),
    (True,  "SPGI",  "S&P Global Inc",               "USD", 511,  480,  458,  429,  528),
    (True,  "TMO",   "Thermo Fisher Scientific",     "USD", 528,  501,  476,  415,  619),
    (True,  "WM",    "Waste Management Inc.",        "USD", 223,  213,  200,  None, 231),
    (False, "ACN",   "Accenture Plc",                "USD", 278,  262,  243,  229,  318),
    (False, "ASML",  "ASML Holding NV",              "USD", 858,  826,  763,  682,  969),
    (False, "AVGO",  "Broadcom Inc",                 "USD", 339,  305,  250,  219,  405),
    (False, "AZO",   "Autozone Inc",                 "USD", 3231, 3004, 2897, 2730, 3272),
    (False, "BKNG",  "Booking Holdings Inc",         "USD", 4148, 3749, 3395, 3166, 4656),
    (False, "CELH",  "Celsius Holdings",             "USD", 51,   47,   41,   37,   84.77),
    (False, "CNSWF", "Constellation Software",       "USD", 2926, 2574, 2232, 1919, 3504.5),
    (False, "CPRT",  "Copart Inc",                   "USD", 51,   48,   46,   42,   53.5),
    (False, "CRM",   "Salesforce Inc",               "USD", 286,  266,  229,  212,  318),
    (False, "CRWD",  "Crowdstrike Holdings",         "USD", 335,  303,  280,  None, 345),
    (False, "EVVTY", "Evolution ADR",                "USD", 98,   86,   72,   66,   143),
    (False, "FDS",   "FactSet Research Systems",     "USD", 344,  293,  249,  None, 363),
    (False, "FTNT",  "Fortinet Inc",                 "USD", 87,   81,   77,   70,   92.02),
    (False, "HCA",   "HCA Healthcare Inc",           "USD", 428,  402,  388,  371,  445),
    (False, "IDXX",  "IDEXX Laboratories",           "USD", 372,  318,  254,  None, 437),
    (False, "LVMUY", "LVMH Moet Hennessy ADR",       "USD", 137,  119,  106,  None, 159),
    (False, "LIN",   "Linde plc",                    "USD", 424,  410,  396,  389,  435.98),
    (False, "MELI",  "Mercadolibre Inc",             "USD", 2023, 1834, 1645, 1481, 2284),
    (False, "MSCI",  "MSCI Inc",                     "USD", 482,  457,  438,  385,  491),
    (False, "MSI",   "Motorola Solutions Inc",       "USD", 405,  388,  369,  None, 408),
    (False, "NKE",   "Nike Inc",                     "USD", 89,   82,   70,   57,   110),
    (False, "NOW",   "ServiceNow Inc",               "USD", 176,  159,  135,  127,  198),
    (False, "NVO",   "Novo Nordisk A/S",             "USD", 67,   58,   45,   None, 73.13),
    (False, "PEP",   "PepsiCo Inc",                  "USD", 155,  148,  141,  127,  158),
    (False, "PLTR",  "Palantir Technologies",        "USD", 142,  125,  105,  None, 143),
    (False, "POOL",  "Pool Corporation",             "USD", 308,  282,  253,  228,  314),
    (False, "UNH",   "UnitedHealth Group Inc",       "USD", 324,  293,  272,  247,  412),
    (False, "V",     "Visa Inc",                     "USD", 303,  292,  281,  268,  311),
    (False, "VEEV",  "Veeva Systems Inc",            "USD", 257,  235,  217,  202,  270),
]

# US-only tickers (exclude HK stocks)
US_PORTFOLIO = [p for p in PORTFOLIO if p[3] == "USD"]


def fetch_prices(tickers):
    """Fetch latest prices using yfinance."""
    prices = {}
    try:
        data = yf.download(tickers, period="1d", interval="1m", progress=False, auto_adjust=True)
        if "Close" in data.columns:
            close = data["Close"]
            if hasattr(close, "columns"):
                for t in tickers:
                    if t in close.columns:
                        val = close[t].dropna()
                        if not val.empty:
                            prices[t] = round(float(val.iloc[-1]), 2)
            else:
                val = close.dropna()
                if not val.empty and len(tickers) == 1:
                    prices[tickers[0]] = round(float(val.iloc[-1]), 2)
    except Exception as e:
        print(f"Price fetch error: {e}")
    return prices


def classify(price, s1, s2, s3, s4, iv):
    """Return trigger level hit and IV status."""
    trigger = None
    if s1 and price <= s1:
        trigger = "S1"
    elif s2 and price <= s2:
        trigger = "S2"
    elif s3 and price <= s3:
        trigger = "S3"
    elif s4 and price <= s4:
        trigger = "S4"

    iv_discount = None
    if iv:
        iv_discount = round((iv - price) / iv * 100, 1)

    undervalued = iv_discount is not None and iv_discount > 0
    return trigger, iv_discount, undervalued


def pct_to_s1(price, s1):
    if s1 is None:
        return None
    return round((price - s1) / price * 100, 1)


def build_row(queen, ticker, name, price, s1, s2, s3, s4, iv, trigger, iv_discount, pct_s1):
    queen_mark = "★ " if queen else ""
    trigger_str = trigger if trigger else "—"
    iv_str = f"${iv:,.2f}" if iv else "—"
    disc_str = (f"+{iv_discount}%" if iv_discount and iv_discount > 0 else f"{iv_discount}%") if iv_discount is not None else "—"
    s1_gap = f"{pct_s1}% above S1" if pct_s1 is not None else "—"

    disc_color = "#2d6a2d" if iv_discount and iv_discount > 0 else "#a32d2d"
    trigger_color = "#a32d2d" if trigger else "#888"
    queen_color = "#D4537E" if queen else "transparent"

    return f"""
    <tr>
      <td style="padding:8px 10px; font-weight:600; color:#1a1a1a; white-space:nowrap;">
        <span style="color:{queen_color}; margin-right:2px;">{queen_mark}</span>{ticker}
      </td>
      <td style="padding:8px 10px; color:#444; font-size:13px;">{name}</td>
      <td style="padding:8px 10px; font-weight:600; color:#1a1a1a; text-align:right;">${price:,.2f}</td>
      <td style="padding:8px 10px; color:#555; text-align:right;">${s1:,.2f}</td>
      <td style="padding:8px 10px; text-align:right; color:#555; font-size:13px;">{s1_gap}</td>
      <td style="padding:8px 10px; text-align:right; color:#555; font-size:13px;">{iv_str}</td>
      <td style="padding:8px 10px; text-align:right; font-weight:600; color:{disc_color};">{disc_str}</td>
      <td style="padding:8px 10px; text-align:center; font-weight:600; color:{trigger_color}; font-size:13px;">{trigger_str}</td>
    </tr>"""


def build_email():
    tickers = [p[1] for p in US_PORTFOLIO]
    prices = fetch_prices(tickers)

    rows_undervalued_queens = []
    rows_undervalued_others = []
    rows_overvalued = []

    for queen, ticker, name, cur, s1, s2, s3, s4, iv in US_PORTFOLIO:
        price = prices.get(ticker)
        if price is None:
            continue
        trigger, iv_discount, undervalued = classify(price, s1, s2, s3, s4, iv)
        pct_s1 = pct_to_s1(price, s1)
        row = build_row(queen, ticker, name, price, s1, s2, s3, s4, iv,
                        trigger, iv_discount, pct_s1)

        if iv_discount is None:
            continue  # ETFs with no IV, skip
        if undervalued:
            if queen:
                rows_undervalued_queens.append((iv_discount, row))
            else:
                rows_undervalued_others.append((iv_discount, row))
        else:
            rows_overvalued.append((iv_discount, row))

    # Sort: undervalued = biggest discount first; overvalued = least overvalued first
    rows_undervalued_queens.sort(key=lambda x: -x[0])
    rows_undervalued_others.sort(key=lambda x: -x[0])
    rows_overvalued.sort(key=lambda x: -x[0])

    def section(title, accent, rows_sorted, empty_msg):
        rows_html = "".join(r for _, r in rows_sorted) if rows_sorted else \
            f'<tr><td colspan="8" style="padding:16px 10px; color:#888; text-align:center;">{empty_msg}</td></tr>'
        return f"""
        <h2 style="margin:32px 0 8px; font-size:15px; font-weight:600; color:{accent}; letter-spacing:0.03em; border-left:3px solid {accent}; padding-left:10px;">{title}</h2>
        <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse; border:1px solid #e8e8e8; border-radius:8px; overflow:hidden; font-family:system-ui,sans-serif; font-size:13px;">
          <thead>
            <tr style="background:#f7f7f5;">
              <th style="padding:8px 10px; text-align:left; font-weight:600; color:#555; font-size:11px; text-transform:uppercase; letter-spacing:0.05em;">Ticker</th>
              <th style="padding:8px 10px; text-align:left; font-weight:600; color:#555; font-size:11px; text-transform:uppercase; letter-spacing:0.05em;">Company</th>
              <th style="padding:8px 10px; text-align:right; font-weight:600; color:#555; font-size:11px; text-transform:uppercase; letter-spacing:0.05em;">Price</th>
              <th style="padding:8px 10px; text-align:right; font-weight:600; color:#555; font-size:11px; text-transform:uppercase; letter-spacing:0.05em;">Support 1</th>
              <th style="padding:8px 10px; text-align:right; font-weight:600; color:#555; font-size:11px; text-transform:uppercase; letter-spacing:0.05em;">S1 Gap</th>
              <th style="padding:8px 10px; text-align:right; font-weight:600; color:#555; font-size:11px; text-transform:uppercase; letter-spacing:0.05em;">Base IV</th>
              <th style="padding:8px 10px; text-align:right; font-weight:600; color:#555; font-size:11px; text-transform:uppercase; letter-spacing:0.05em;">IV Discount</th>
              <th style="padding:8px 10px; text-align:center; font-weight:600; color:#555; font-size:11px; text-transform:uppercase; letter-spacing:0.05em;">Trigger</th>
            </tr>
          </thead>
          <tbody>{''.join(r for _, r in rows_sorted) if rows_sorted else rows_html}</tbody>
        </table>"""

    now_sgt = datetime.now(SGT).strftime("%d %b %Y, %I:%M %p SGT")
    body = f"""
<!DOCTYPE html>
<html>
<body style="margin:0; padding:0; background:#f4f4f0; font-family:system-ui,-apple-system,sans-serif;">
<div style="max-width:760px; margin:24px auto; background:#fff; border-radius:12px; overflow:hidden; border:1px solid #e0e0da;">

  <!-- Header -->
  <div style="background:#1a1a1a; padding:24px 28px;">
    <p style="margin:0; font-size:11px; font-weight:600; letter-spacing:0.1em; color:#999; text-transform:uppercase;">Capital Gains Portfolio</p>
    <h1 style="margin:6px 0 4px; font-size:22px; font-weight:600; color:#fff;">Daily Price Alert</h1>
    <p style="margin:0; font-size:13px; color:#aaa;">{now_sgt} &nbsp;·&nbsp; US Stocks Only &nbsp;·&nbsp; ★ = Heavenly Queen</p>
  </div>

  <div style="padding:20px 28px 32px;">

    {section("★ Heavenly Queens — Undervalued", "#D4537E", rows_undervalued_queens, "No Queens are undervalued today.")}
    {section("Other US Stocks — Undervalued", "#2d6a2d", rows_undervalued_others, "No other stocks are undervalued today.")}
    {section("US Stocks — Overvalued / Above IV", "#a32d2d", rows_overvalued, "No stocks are overvalued today.")}

    <p style="margin-top:28px; font-size:11px; color:#aaa; border-top:1px solid #eee; padding-top:16px;">
      Prices sourced from Yahoo Finance (may be delayed 15 min). Support levels last updated 3 Feb 2026.
      This is for informational purposes only and not financial advice. &copy; 2026 Piranha Profits.
    </p>
  </div>
</div>
</body>
</html>"""

    return body, now_sgt


def send_email():
    print(f"[{datetime.now(SGT).strftime('%Y-%m-%d %H:%M:%S')} SGT] Building and sending alert email…")
    body, timestamp = build_email()

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📊 Portfolio Alert — {datetime.now(SGT).strftime('%d %b %Y')} 6pm SGT"
    msg["From"]    = SMTP_USER
    msg["To"]      = TO_EMAIL
    msg.attach(MIMEText(body, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, TO_EMAIL, msg.as_string())
        print(f"  ✓ Email sent to {TO_EMAIL}")
    except Exception as e:
        print(f"  ✗ Failed to send: {e}")


if __name__ == "__main__":
    print("Capital Gains Portfolio Alert — scheduler started")
    print(f"  Will send daily at {SEND_TIME_SGT} SGT to {TO_EMAIL}")
    print(f"  Current time: {datetime.now(SGT).strftime('%Y-%m-%d %H:%M:%S')} SGT")

    # Schedule at 6pm SGT every day
    schedule.every().day.at(SEND_TIME_SGT).do(send_email)

    # Uncomment to test immediately:
    # send_email()

    while True:
        schedule.run_pending()
        time.sleep(30)
