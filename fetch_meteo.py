import urllib.request
import json
import csv
import os
import smtplib
import math
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path

LATITUDE = float(os.environ.get("LAT", "38.1157"))
LONGITUDE = float(os.environ.get("LON", "13.3615"))
EMAIL_FROM = os.environ.get("EMAIL_FROM", "")
EMAIL_PASS = os.environ.get("EMAIL_PASS", "")
EMAIL_TO = "amarsi@outlook.com"
CSV_FILE = "data/meteo.csv"
HOUR = datetime.now(timezone.utc).hour

URL = (f"https://api.open-meteo.com/v1/forecast"
       f"?latitude={LATITUDE}&longitude={LONGITUDE}"
       f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
       f"precipitation,wind_speed_10m,wind_direction_10m,weather_code,pressure_msl"
       f"&timezone=auto")

def dew_point(t, rh):
    a, b = 17.27, 237.7
    alpha = ((a * t) / (b + t)) + math.log(rh / 100.0)
    return round((b * alpha) / (a - alpha), 1)

def fetch():
    with urllib.request.urlopen(URL, timeout=15) as r:
        data = json.loads(r.read())
    c = data["current"]
    t = float(c.get("temperature_2m", 0))
    rh = float(c.get("relative_humidity_2m", 0))
    now = datetime.now(timezone.utc).astimezone()
    return {
        "timestamp": now.strftime("%Y-%m-%d %H:%M"),
        "lat": round(LATITUDE,4), "lon": round(LONGITUDE,4),
        "temp_c": t,
        "umidita_pct": rh,
        "dew_point_c": dew_point(t, rh),
        "percepita_c": round(float(c.get("apparent_temperature", 0)), 1),
        "pioggia_mm": c.get("precipitation", 0),
        "vento_kmh": round(float(c.get("wind_speed_10m", 0)), 1),
        "pressione_hpa": round(float(c.get("pressure_msl", 0)), 1),
    }

def save_csv(row):
    path = Path(CSV_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=row.keys())
        if new:
            w.writeheader()
        w.writerow(row)

def send_daily_email():
    if not EMAIL_FROM or not EMAIL_PASS:
        return
    path = Path(CSV_FILE)
    if not path.exists():
        return

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            if r["timestamp"].startswith(today):
                rows.append(r)

    if not rows:
        return

    table = ""
    for r in rows:
        table += f"""<tr>
        <td style="padding:8px;border-bottom:1px solid #eee;">{r['timestamp']}</td>
        <td style="padding:8px;border-bottom:1px solid #eee;">{r['temp_c']}°C</td>
        <td style="padding:8px;border-bottom:1px solid #eee;">{r['umidita_pct']}%</td>
        <td style="padding:8px;border-bottom:1px solid #eee;">{r['dew_point_c']}°C</td>
        <td style="padding:8px;border-bottom:1px solid #eee;">{r['pioggia_mm']}mm</td>
        <td style="padding:8px;border-bottom:1px solid #eee;">{r['vento_kmh']}km/h</td>
        </tr>"""

    html = f"""<html><body style="font-family:Arial;max-width:700px;margin:auto;">
<h2 style="background:#0a1628;color:#64ffda;padding:16px;border-radius:8px;">
  Meteo Giornaliero — {today}
</h2>
<p style="color:#666;">Posizione GPS: {rows[-1]['lat']}, {rows[-1]['lon']}</p>
<table width="100%" style="border-collapse:collapse;font-size:0.9em;">
<tr style="background:#0a1628;color:#64ffda;">
  <th style="padding:8px;">Ora</th>
  <th style="padding:8px;">Temp</th>
  <th style="padding:8px;">Umidità</th>
  <th style="padding:8px;">Dew Point</th>
  <th style="padding:8px;">Pioggia</th>
  <th style="padding:8px;">Vento</th>
</tr>
{table}
</table>
</body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Meteo {today} — Riepilogo giornaliero"
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    msg.attach(MIMEText(html, "html"))

    with open(path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", "attachment; filename=meteo.csv")
    msg.attach(part)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(EMAIL_FROM, EMAIL_PASS)
        s.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
    print("Email giornaliera inviata!")

row = fetch()
save_csv(row)
print("Salvato:", row)

if HOUR == 23:
    send_daily_email()
