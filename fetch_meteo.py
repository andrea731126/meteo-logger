import urllib.request
import json
import csv
import os
import smtplib
import math
from datetime import datetime, timezone, date
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
        "lat": LATITUDE, "lon": LONGITUDE,
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

def send_email(row):
    if not EMAIL_FROM or not EMAIL_PASS:
        print("Email non configurata")
        return
    subject = f"Meteo {row['timestamp']} | T:{row['temp_c']}C UR:{row['umidita_pct']}% DP:{row['dew_point_c']}C"
    html = f"""<html><body style="font-family:Arial;max-width:500px;margin:auto;">
<h2 style="background:#0a1628;color:#64ffda;padding:16px;border-radius:8px;">Meteo Report</h2>
<p style="color:#666;">{row['timestamp']}</p>
<table width="100%" style="border-collapse:collapse;">
<tr style="background:#f0f4f8;"><td style="padding:10px;"><b>Temperatura</b></td><td style="padding:10px;">{row['temp_c']} °C</td></tr>
<tr><td style="padding:10px;"><b>Umidità Relativa</b></td><td style="padding:10px;">{row['umidita_pct']} %</td></tr>
<tr style="background:#f0f4f8;"><td style="padding:10px;"><b>Dew Point</b></td><td style="padding:10px;">{row['dew_point_c']} °C</td></tr>
<tr><td style="padding:10px;"><b>Percepita</b></td><td style="padding:10px;">{row['percepita_c']} °C</td></tr>
<tr style="background:#f0f4f8;"><td style="padding:10px;"><b>Pioggia</b></td><td style="padding:10px;">{row['pioggia_mm']} mm</td></tr>
<tr><td style="padding:10px;"><b>Vento</b></td><td style="padding:10px;">{row['vento_kmh']} km/h</td></tr>
<tr style="background:#f0f4f8;"><td style="padding:10px;"><b>Pressione</b></td><td style="padding:10px;">{row['pressione_hpa']} hPa</td></tr>
<tr><td style="padding:10px;"><b>Posizione GPS</b></td><td style="padding:10px;">{row['lat']}, {row['lon']}</td></tr>
</table>
</body></html>"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    msg.attach(MIMEText(html, "html"))
    p = Path(CSV_FILE)
    if p.exists():
        with open(p, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment; filename=meteo.csv")
        msg.attach(part)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(EMAIL_FROM, EMAIL_PASS)
        s.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
    print("Email inviata!")

row = fetch()
save_csv(row)
send_email(row)
print("Done:", row)
