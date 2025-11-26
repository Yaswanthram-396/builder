# import requests
# from django.conf import settings

# def send_whatsapp_message(phone, message):
#     url = f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"

#     headers = {
#         "Content-Type": "application/json",
#         "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
#     }

#     payload = {
#         "messaging_product": "whatsapp",
#         "to": phone,
#         "type": "text",
#         "text": {"body": message}
#     }

#     response = requests.post(url, headers=headers, json=payload)
#     print("📤 Sent Message Response:", response.json())
#     return response.json()
import os, requests, json

WHATSAPP_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

def send_whatsapp_message(phone, message):
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": message}
    }

    response = requests.post(url, headers=headers, data=json.dumps(data))
    print("📤 WA Response:", response.text)

def send_whatsapp_buttons(to, text, buttons):
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": text},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": btn, "title": btn}}
                    for btn in buttons
                ]
            }
        }
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        print(f"📤 Buttons sent to {to}: Status={response.status_code}")
        if response.status_code != 200:
            print(f"❌ Button send error: {response.text}")
        else:
            print(f"✅ Buttons sent successfully: {response.json()}")
    except Exception as e:
        print(f"❌ Error sending buttons: {e}")
        import traceback
        traceback.print_exc()