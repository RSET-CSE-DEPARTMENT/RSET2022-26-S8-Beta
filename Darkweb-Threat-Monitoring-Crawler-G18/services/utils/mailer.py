import smtplib
from email.mime.text import MIMEText

def send_report_email(receiver_email, report_text):

    sender_email = "darkwebthreatcrawler@gmail.com"
    app_password = "your_16_char_app_password"

    msg = MIMEText(report_text)
    msg["Subject"] = "Dark Web Threat Intelligence Report"
    msg["From"] = sender_email
    msg["To"] = receiver_email

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, app_password)
            server.send_message(msg)
        return True
    except Exception as e:
        print("Email error:", e)
        return False