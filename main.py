from flask import Flask, request, jsonify
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import os

app = Flask(__name__)

INFLUX_URL    = os.environ.get("INFLUX_URL", "")
INFLUX_TOKEN  = os.environ.get("INFLUX_TOKEN", "")
INFLUX_ORG    = os.environ.get("INFLUX_ORG", "afrikanet")
INFLUX_BUCKET = os.environ.get("INFLUX_BUCKET", "supervision")
EMAIL_FROM    = os.environ.get("EMAIL_FROM", "")
EMAIL_PASS    = os.environ.get("EMAIL_PASS", "")
EMAIL_TO      = os.environ.get("EMAIL_TO", "")
SEUIL_TEMP    = float(os.environ.get("SEUIL_TEMP", "40"))
SEUIL_DEBIT   = float(os.environ.get("SEUIL_DEBIT", "100"))

influx_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
write_api = influx_client.write_api(write_options=SYNCHRONOUS)

def envoyer_alerte(sujet, message):
    try:
        msg = MIMEText(message)
        msg["Subject"] = sujet
        msg["From"]    = EMAIL_FROM
        msg["To"]      = EMAIL_TO
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_FROM, EMAIL_PASS)
        server.send_message(msg)
        server.quit()
        print(f"Alerte envoyee : {sujet}")
    except Exception as e:
        print(f"Erreur email : {e}")

@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "ok", "service": "AFRIKANET IoT Server", "version": "1.0"})

@app.route("/data", methods=["POST"])
def recevoir_data():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data"}), 400

        print(f"Donnees recues : {data}")

        site_id     = data.get("site_id", "UNKNOWN")
        wan_status  = data.get("wan_status", "Unknown")
        wan_ip      = data.get("wan_ip", "0.0.0.0")
        wan_gateway = data.get("wan_gateway", "0.0.0.0")
        wan_type    = data.get("wan_type", "Unknown")
        nb_clients  = int(data.get("nb_clients", 0))
        signal_moy  = int(data.get("signal_moy", 0))
        debit_wifi  = float(data.get("debit_moy_mbps", 0))
        courant     = float(data.get("courant", 0))
        puissance   = float(data.get("puissance", 0))
        debit_kbps  = float(data.get("debit_kbps", 0))
        temperature = float(data.get("temperature", 0))
        humidite    = float(data.get("humidite", 0))

        point = Point("supervision") \
            .tag("site_id", site_id) \
            .tag("wan_status", wan_status) \
            .tag("wan_type", wan_type) \
            .field("wan_ip", wan_ip) \
            .field("wan_gateway", wan_gateway) \
            .field("nb_clients", nb_clients) \
            .field("signal_moy", signal_moy) \
            .field("debit_wifi_mbps", debit_wifi) \
            .field("courant_a", courant) \
            .field("puissance_w", puissance) \
            .field("debit_kbps", debit_kbps) \
            .field("temperature_c", temperature) \
            .field("humidite_pct", humidite)

        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if wan_status != "Connected":
            envoyer_alerte(
                f"ALERTE AFRIKANET - {site_id} HORS LIGNE",
                f"Site : {site_id}\nDate : {now}\nStatut : {wan_status}\nIP WAN : {wan_ip}"
            )

        if temperature > SEUIL_TEMP:
            envoyer_alerte(
                f"ALERTE TEMPERATURE - {site_id}",
                f"Site : {site_id}\nDate : {now}\nTemperature : {temperature}C\nSeuil : {SEUIL_TEMP}C"
            )

        if debit_kbps > 0 and debit_kbps < SEUIL_DEBIT:
            envoyer_alerte(
                f"ALERTE DEBIT FAIBLE - {site_id}",
                f"Site : {site_id}\nDate : {now}\nDebit : {debit_kbps} Kbps\nSeuil : {SEUIL_DEBIT} Kbps"
            )

        return jsonify({"status": "ok", "message": "Data saved"}), 200

    except Exception as e:
        print(f"Erreur : {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/status", methods=["GET"])
def status():
    return jsonify({"status": "running", "timestamp": datetime.now().isoformat()})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
