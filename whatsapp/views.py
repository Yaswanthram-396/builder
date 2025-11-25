from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import json
import os

from .utils import send_whatsapp_message
from .models import Lead, ConversationState, Property

# Sheets Sync
from whatsapp.sheets import add_lead_to_sheet

# Drive Upload Link
from whatsapp.drive import create_drive_folder

VERIFY_TOKEN = os.getenv('WHATSAPP_VERIFY_TOKEN', 'dheeraj-secret-token')


# ==================== PROPERTY MATCHING ====================

def send_matching_properties_to_buyer(buyer_lead, phone):
    from .models import Property

    buyer_data = buyer_lead.data
    b_type = (buyer_data.get("property_type_preference") or "").lower()
    b_loc = (buyer_data.get("location_preference") or "").lower()

    qs = Property.objects.all()

    if b_type:
        qs = qs.filter(property_type__icontains=b_type)

    if b_loc:
        qs = qs.filter(location__icontains=b_loc)

    props = list(qs[:5])  # max 5 matches

    if not props:
        send_whatsapp_message(phone, "🔍 No exact matches found! Our team will assist you shortly.")
        return

    lines = ["🎉 I found these matching properties:\n"]
    for idx, p in enumerate(props, start=1):
        lines.append(
            f"{idx}) {p.bhk or ''} {p.property_type or ''}\n"
            f"📐 {p.area_sqft or 'N/A'} sq.ft\n"
            f"📍 {p.location or 'N/A'}\n"
            f"💰 {p.price_range or 'N/A'}\n"
            f"🛠 Amenities: {p.amenities or 'N/A'}\n"
        )

    lines.append("👉 Reply with the property number (1, 2, 3...) if interested.")
    send_whatsapp_message(phone, "\n".join(lines))


# ==================== STATE MACHINE ====================

def handle_message(phone, text):
    from whatsapp.ai.normalizer import normalize_answer  # AI Normalizer
    from whatsapp.ai.scorer import ai_score_lead          # AI Scorer

    lead, _ = Lead.objects.get_or_create(phone=phone)
    state, _ = ConversationState.objects.get_or_create(phone=phone)

    txt = text.strip()

    # ================= INIT =================
    if state.current_step == "INIT":
        send_whatsapp_message(phone, "Welcome to Dheeraj Properties! Do you want to BUY or SELL a property?")
        state.current_step = "ASK_BUY_OR_SELL"
        state.save()
        return

    # ================= ASK BUY/SELL =================
    if state.current_step == "ASK_BUY_OR_SELL":
        low = txt.lower()
        if low in ["buy", "buyer", "purchase"]:
            lead.lead_type = "BUYER"
            lead.save()
            send_whatsapp_message(phone, "Great! 🏡 What type of property are you looking for? (Apartment/House/Plot)")
            state.current_step = "BUY_Q1"
            state.save()
            return

        elif low in ["sell", "seller", "selling"]:
            lead.lead_type = "SELLER"
            lead.save()
            send_whatsapp_message(phone, "Awesome! 🏠 What type of property are you selling? (Apartment/House/Plot/Commercial)")
            state.current_step = "SELL_Q1"
            state.save()
            return

        else:
            send_whatsapp_message(phone, "❓ Please reply with BUY or SELL.")
            return

    # ================= SELL FLOW =================
    if lead.lead_type == "SELLER":

        if state.current_step == "SELL_Q1":
            lead.data["property_type"] = normalize_answer("Property Type", txt)
            lead.save()
            send_whatsapp_message(phone, "Nice! 📐 What is the area in sq.ft?")
            state.current_step = "SELL_Q2"
            state.save()
            return

        if state.current_step == "SELL_Q2":
            lead.data["area_sqft"] = normalize_answer("Area", txt)
            lead.save()
            send_whatsapp_message(phone, "How many bedrooms? (1BHK/2BHK/etc)")
            state.current_step = "SELL_Q3"
            state.save()
            return

        if state.current_step == "SELL_Q3":
            lead.data["bhk"] = normalize_answer("Bedroom Count", txt)
            lead.save()
            send_whatsapp_message(phone, "May I have your name?")
            state.current_step = "SELL_Q4"
            state.save()
            return

        if state.current_step == "SELL_Q4":
            lead.data["name"] = txt
            lead.save()
            send_whatsapp_message(phone, "📍 Where is your property located?")
            state.current_step = "SELL_Q5"
            state.save()
            return

        if state.current_step == "SELL_Q5":
            lead.data["location"] = normalize_answer("Location", txt)
            lead.save()
            send_whatsapp_message(phone, "💰 What's your expected price range?")
            state.current_step = "SELL_Q6"
            state.save()
            return

        if state.current_step == "SELL_Q6":
            lead.data["price_range"] = normalize_answer("Price Range", txt)
            lead.save()
            send_whatsapp_message(phone, "🏷️ Any amenities? (Pool, Gym, Security etc.)")
            state.current_step = "SELL_Q7"
            state.save()
            return

        if state.current_step == "SELL_Q7":
            lead.data["amenities"] = normalize_answer("Amenities", txt)
            lead.status = "NEW"
            lead.save()

            # Save to Property Table
            Property.objects.create(
                SELLER=lead,
                property_type=lead.data.get("property_type"),
                area_sqft=lead.data.get("area_sqft"),
                bhk=lead.data.get("bhk"),
                location=lead.data.get("location"),
                price_range=lead.data.get("price_range"),
                amenities=lead.data.get("amenities"),
            )

            # ===== SCORING =====
            score, segment, reason = ai_score_lead(lead)
            lead.score = score
            lead.segment = segment
            lead.rejection_reason = "" if segment != "NONE" else reason
            lead.status = "QUALIFIED" if segment in ["HOT", "WARM"] else "UNQUALIFIED"
            lead.save()

            # ===== SHEETS SYNC =====
            add_lead_to_sheet(lead)

            # ===== GOOGLE DRIVE FOLDER =====
            folder_name = f"{lead.data.get('name', 'Seller')} - {lead.phone}"
            drive_link = create_drive_folder(folder_name)

            if drive_link:
                lead.data["drive_link"] = drive_link
                lead.save()
                send_whatsapp_message(
                    phone,
                    f"📁 Please upload property images/videos here:\n{drive_link}"
                )
            else:
                send_whatsapp_message(phone, "⚠️ Upload link couldn't be generated. Our team will help manually.")

            send_whatsapp_message(phone, f"🎉 Property saved! (Lead segment: {segment}). Our team will contact you soon.")
            state.current_step = "COMPLETED"
            state.save()
            return

    # ================= BUY FLOW =================
    if lead.lead_type == "BUYER":
        from .utils import send_whatsapp_message

        if state.current_step == "BUY_Q1":
            lead.data["property_type_preference"] = normalize_answer("Property Type", txt)
            lead.save()
            send_whatsapp_message(phone, "📏 What area size do you prefer? (Example: 1000–1500 sq.ft)")
            state.current_step = "BUY_Q2"
            state.save()
            return

        if state.current_step == "BUY_Q2":
            lead.data["area_preference"] = normalize_answer("Area Preference", txt)
            lead.save()
            send_whatsapp_message(phone, "🛏️ How many bedrooms do you need? (1BHK/2BHK/etc)")
            state.current_step = "BUY_Q3"
            state.save()
            return

        if state.current_step == "BUY_Q3":
            lead.data["bhk"] = normalize_answer("Bedroom Count", txt)
            lead.save()
            send_whatsapp_message(phone, "🧾 May I have your name?")
            state.current_step = "BUY_Q4"
            state.save()
            return

        if state.current_step == "BUY_Q4":
            lead.data["name"] = txt
            lead.save()
            send_whatsapp_message(phone, "📍 Which location are you interested in?")
            state.current_step = "BUY_Q5"
            state.save()
            return

        if state.current_step == "BUY_Q5":
            lead.data["location_preference"] = normalize_answer("Location Preference", txt)
            lead.save()
            send_whatsapp_message(phone, "💰 What's your budget?")
            state.current_step = "BUY_Q6"
            state.save()
            return

        if state.current_step == "BUY_Q6":
            lead.data["budget"] = normalize_answer("Budget", txt)
            lead.save()
            send_whatsapp_message(phone, "🏷️ Any amenities you prefer? (Pool, Gym etc.)")
            state.current_step = "BUY_Q7"
            state.save()
            return

        if state.current_step == "BUY_Q7":
            lead.data["amenities"] = normalize_answer("Amenities", txt)
            lead.status = "NEW"
            lead.save()

            # ===== SCORING =====
            score, segment, reason = ai_score_lead(lead)
            lead.score = score
            lead.segment = segment
            lead.rejection_reason = "" if segment != "NONE" else reason
            lead.status = "QUALIFIED" if segment in ["HOT", "WARM"] else "UNQUALIFIED"
            lead.save()

            # ===== SHEETS SYNC =====
            add_lead_to_sheet(lead)

            # Match SELLER properties
            send_matching_properties_to_buyer(lead, phone)

            send_whatsapp_message(phone, f"✅ Your requirements are saved. (Lead segment: {segment}). Our team will follow up.")
            state.current_step = "COMPLETED"
            state.save()
            return

    # ================= DEFAULT =================
    send_whatsapp_message(phone, "🙏 Thank you! Our team will get back to you soon.")


# ==================== WEBHOOK ENDPOINT ====================

@csrf_exempt
def whatsapp_webhook(request):
    if request.method == "GET":
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            return HttpResponse(challenge, status=200)
        return HttpResponse("Invalid verification token", status=403)

    if request.method == "POST":
        data = json.loads(request.body.decode("utf-8"))
        print("📩 Incoming:", json.dumps(data, indent=2))

        try:
            message = data["entry"][0]["changes"][0]["value"]["messages"][0]
            from_phone = message["from"]
            text = message.get("text", {}).get("body", "")
            handle_message(from_phone, text)
        except Exception as e:
            print("❌ Error:", e)

        return JsonResponse({"status": "received"}, status=200)

    return HttpResponse("Invalid request", status=400)
