import os
from twilio.rest import Client
from concurrent.futures import ThreadPoolExecutor

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
print("SID:", os.getenv("TWILIO_ACCOUNT_SID"))
print("TOKEN:", os.getenv("TWILIO_AUTH_TOKEN"))
print("FROM:", os.getenv("TWILIO_PHONE_NUMBER"))

def build_sms(camera_id, location, fall_time):
    return f"""QUIET SOS ALERT ⚠️
Fall Detected
Camera: {camera_id}
Location: {location}
Time: {fall_time}
Please check immediately."""

def build_twiml(camera_id, location):
    return f"""
<Response>
  <Say voice="alice">
    Quiet S O S alert. A fall has been detected.
    Camera {camera_id}. Location {location}.
    Please check immediately.
  </Say>
</Response>
"""

def send_sms(to_number, message):
    msg = client.messages.create(
        body=message,
        from_=TWILIO_PHONE_NUMBER,
        to=to_number
    )
    return msg.sid

def make_call(to_number, twiml):
    call = client.calls.create(
    to=to_number,
    from_=TWILIO_PHONE_NUMBER,
    url="http://127.0.0.1:5000/trigger-alert"
)
   
    return call.sid

def notify_contact(to_number, camera_id, location, fall_time): 
    sms_body = build_sms(camera_id, location, fall_time) 
    twiml = build_twiml(camera_id, location) 
    
    # ✅ SMS + Call at the same time 
    with ThreadPoolExecutor(max_workers=2) as executor: 
        sms_future = executor.submit(send_sms, to_number, sms_body) 
        call_future = executor.submit(make_call, to_number, twiml) 
        
        sms_sid = sms_future.result() 
        call_sid = call_future.result() 
        
        return {"contact": to_number, "sms_sid": sms_sid, "call_sid": call_sid}