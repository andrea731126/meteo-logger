import urllib.request
import json
import csv
import os
import smtplib
import math
import time
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path

LATITUDE = float(os.environ.get("LAT", "25.8854"))
LONGITUDE = float(os.environ.get("LON", "-80.1769"))
EMAIL_FROM = os.environ.get("EMAIL_FROM", "")
EMAIL_PASS = os.environ.get("EMAIL_PASS", "")
EMAIL_TO = "amarsi@outlook.com"
CSV_FILE = "data/meteo.csv"

URL = (f"https://api.open-meteo.com/v1/forecast"
       f"?latitude={LATITUDE}&longitude={LONGITUDE}"
       f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
       f"precipitation,wind_speed_10m,wind_direction_10m,weather_code,pressure_msl"
       f"&timezone=auto")

def get_location_name():
    for attempt in range(3):
        try:
            geo = f"https://nominatim.openstreetmap.org/reverse?lat={LATITUDE}&lon={LONGITUDE}&format=json"
            req = urllib.request.Request(geo)
            req.add_header("User-Agent", "MeteoLogger/1.0")
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
            addr = data.get("address", {})
            city = (addr.get("city") or addr.get("town") or
                   addr.get("village") or addr.get("county") or
                   addr.get("state") or "")
            country = addr.get("country", "")
            name = f"{city}, {country}".strip(", ")
            if name:
                return name
        except Exception as e:
            print(f"Tentativo {attempt+1} fallito: {e}")
            time.sleep(2)
    return f"Lat {LATITUDE}, Lon {LONGITUDE}"

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
    now_utc = datetime.now(timezone.utc)
    localita = get_location_name()
    return {
        "timestamp": now_utc.strftime("%Y-%m-%d %H:%M UTC"),
        "localita": localita,
        "lat": round(LATITUDE, 4),
        "lon": round(LONGITUDE, 4),
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
        print("Email non configurata")
        return
    path = Path(CSV_FILE)
    if not path.exists():
        print("CSV non trovato")
        return

    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            if r["timestamp"].startswith(yesterday):
                rows.append(r)

    if not rows:
        print(f"Nessun dato per {yesterday}")
        return

    print(f"Invio email con {len(rows)} rilevazioni per {yesterday}")

    table = ""
    for r in rows:
        table += f"""<tr>
        <td style="padding:8px;border-bottom:1px solid #eee;">{r['timestamp']}</td>
        <td style="padding:8px;border-bottom:1px solid #eee;">{r['localita']}</td>
        <td style="padding:8px;border-bottom:1px solid #eee;">{r['temp_c']}°C</td>
        <td style="padding:8px;border-bottom:1px solid #eee;">{r['umidita_pct']}%</td>
        <td style="padding:8px;border-bottom:1px solid #eee;">{r['dew_point_c']}°C</td>
        <td style="padding:8px;border-bottom:1px solid #eee;">{r['pioggia_mm']}mm</td>
        <td style="padding:8px;border-bottom:1px solid #eee;">{r['vento_kmh']}km/h</td>
        </tr>"""

    html = f"""<html><body style="font-family:Arial;max-width:800px;margin:auto;">
<h2 style="background:#0a1628;color:#64ffda;padding:16px;border-radius:8px;">
  Meteo — {yesterday} — {rows[0]['localita']}
</h2>
<table width="100%" style="border-collapse:collapse;font-size:0.9em;">
<tr style="background:#0a1628;color:#64ffda;">
  <th style="padding:8px;">Ora</th>
  <th style="padding:8px;">Localita</th>
  <th style="padding:8px;">Temp</th>
  <th style="padding:8px;">Umidita</th>
  <th style="padding:8px;">Dew Point</th>
  <th style="padding:8px;">Pioggia</th>
  <th style="padding:8px;">Vento</th>
</tr>
{table}
</table>
</body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Meteo {yesterday} — {rows[0]['localita']} — {len(rows)} rilevazioni"
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    msg.attach(MIMEText(html, "html"))

    with open(path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", "attachment; filename=meteo.csv")
    msg.attach(part)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(EMAIL_FROM, EMAIL_PASS)
            s.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        print("Email inviata!")
    except Exception as e:
        print(f"ERRORE EMAIL: {e}")

row = fetch()
save_csv(row)
utc_hour = datetime.now(timezone.utc).hour
print(f"Salvato: {row['timestamp']} — {row['localita']}")
print(f"UTC hour: {utc_hour}")

if utc_hour == 8:
    send_daily_email()
