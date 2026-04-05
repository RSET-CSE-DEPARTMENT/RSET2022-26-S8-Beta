import os
import json
from datetime import datetime
from flask import Flask, request, jsonify
from flask import Response
from dotenv import load_dotenv
from alert_service import notify_contact
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv()
app = Flask(__name__)

def load_contacts():
    contacts_path = os.path.join(BASE_DIR, "contacts.json")
    with open(contacts_path, "r") as f:
        return json.load(f)

@app.get("/")
def home():
    return jsonify({"status": "QuietSOS Flask Alert Server Running ✅"})

@app.post("/trigger-alert")
def trigger_alert():
    data = request.get_json()

    if not data or "cameraId" not in data:
        return jsonify({"error": "cameraId is required"}), 400

    camera_id = data["cameraId"]
    fall_time = data.get("time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    contacts_db = load_contacts()

    if camera_id not in contacts_db:
        return jsonify({"error": f"No mapping found for {camera_id}"}), 404

    location = contacts_db[camera_id]["location"]
    contacts = contacts_db[camera_id]["contacts"]

    report = []
    for contact in contacts:
        try:
            result = notify_contact(contact, camera_id, location, fall_time)
            report.append({"status": "SUCCESS", **result})
        except Exception as e:
            print("❌ TWILIO ERROR:", e)
            report.append({"status": "FAILED", "contact": contact, "error": str(e)})


    return jsonify({
        "status": "ALERT_TRIGGERED",
        "cameraId": camera_id,
        "location": location,
        "time": fall_time,
        "report": report
    })

@app.get("/voice")
def voice():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice">Alert! Fall detected.</Say>
</Response>"""

    return Response(xml, mimetype="text/xml")

if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)