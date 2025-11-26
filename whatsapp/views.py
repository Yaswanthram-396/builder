from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import json
import os

from .utils import send_whatsapp_message
from .utils import send_whatsapp_buttons
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
    from whatsapp.ai.normalizer import normalize_answer
    from whatsapp.ai.scorer import ai_score_lead

    lead, _ = Lead.objects.get_or_create(phone=phone)
    state, _ = ConversationState.objects.get_or_create(phone=phone)

    # Process text input (button responses are already extracted in webhook)
    txt = text.strip().lower()
    print(f"📥 Processing message: '{text}' -> '{txt}' | Current step: {state.current_step} | Lead type: {lead.lead_type}")

    # ==================== GREETING + FRESH START ====================
    greetings = ["hi", "hii", "hello", "hey", "start", "yo", "hola"]
    if txt in greetings:
        lead.lead_type = ""
        lead.data = {}
        lead.status = "NEW"
        lead.save()

        send_whatsapp_buttons(
            phone,
            "👋 Welcome to *Dheeraj Properties!*\nHow can we help you today?",
            ["BUY", "SELL"]
        )
        state.current_step = "ASK_BUY_OR_SELL"
        state.save()
        return

    # ==================== ALREADY COMPLETED ====================
    if state.current_step == "COMPLETED":
        send_whatsapp_message(phone, "🙏 Thank you! Type *Hi* to start a new inquiry.")
        return

    # ==================== ASK BUY OR SELL ====================
    if state.current_step == "ASK_BUY_OR_SELL" or state.current_step == "INIT":
        # BUY SELECTED
        if "buy" in txt or txt == "buy":
            print(f"✅ BUY selected, setting lead type to BUYER")
            lead.lead_type = "BUYER"
            lead.data = {}
            lead.save()
            print(f"📤 Sending property type buttons to {phone}...")
            send_whatsapp_buttons(
                phone,
                "Great! 🏡 What type of property are you looking for?",
                ["Apartment", "House", "Plot"]
            )
            state.current_step = "BUY_Q1"
            state.save()
            print(f"✅ State updated to BUY_Q1, buttons should be sent")
            return

        # SELL SELECTED
        elif "sell" in txt or txt == "sell":
            print(f"✅ SELL selected, setting lead type to SELLER")
            lead.lead_type = "SELLER"
            lead.data = {}
            lead.save()
            send_whatsapp_buttons(
                phone,
                "Awesome! 🏠 What type of property are you selling?",
                ["Apartment", "House", "Plot"]
            )
            state.current_step = "SELL_Q1"
            state.save()
            print(f"✅ State updated to SELL_Q1")
            return

        # INVALID INPUT - resend buttons
        print(f"❌ Invalid input in ASK_BUY_OR_SELL: '{txt}' (state: {state.current_step})")
        send_whatsapp_buttons(
            phone,
            "❓ Please select one:",
            ["BUY", "SELL"]
        )
        # Ensure state is set correctly
        if state.current_step != "ASK_BUY_OR_SELL":
            state.current_step = "ASK_BUY_OR_SELL"
            state.save()
        return


    # ======================================================================
    #  SELLER FLOW
    # ======================================================================
    if lead.lead_type == "SELLER":

        if state.current_step == "SELL_Q1":
            lead.data["property_type"] = normalize_answer("Property Type", txt)
            lead.save()
            send_whatsapp_message(phone, "📐 Enter the area in sq.ft:")
            state.current_step = "SELL_Q2"
            state.save()
            return

        if state.current_step == "SELL_Q2":
            lead.data["area_sqft"] = normalize_answer("Area", txt)
            lead.save()
            send_whatsapp_buttons(phone, "🛏 Bedrooms?", ["1BHK", "2BHK", "3BHK"])
            state.current_step = "SELL_Q3"
            state.save()
            return

        if state.current_step == "SELL_Q3":
            lead.data["bhk"] = normalize_answer("Bedrooms", txt)
            lead.save()
            send_whatsapp_message(phone, "🧾 May I have your name?")
            state.current_step = "SELL_Q4"
            state.save()
            return

        if state.current_step == "SELL_Q4":
            lead.data["name"] = text.strip()
            lead.save()
            send_whatsapp_message(phone, "📍 Property location?")
            state.current_step = "SELL_Q5"
            state.save()
            return

        if state.current_step == "SELL_Q5":
            lead.data["location"] = normalize_answer("Location", txt)
            lead.save()
            send_whatsapp_message(phone, "💰 Expected price range?")
            state.current_step = "SELL_Q6"
            state.save()
            return

        if state.current_step == "SELL_Q6":
            lead.data["price_range"] = normalize_answer("Price", txt)
            lead.save()
            send_whatsapp_buttons(phone, "🏷 Amenities?", ["Pool", "Gym", "Other"])
            state.current_step = "SELL_Q7"
            state.save()
            return

        if state.current_step == "SELL_Q7":
            if txt == "other":
                send_whatsapp_message(phone, "Type amenities (e.g., Power Backup, Garden, Lift):")
                state.current_step = "SELL_Q7_OTHER"
                state.save()
                return

            lead.data["amenities"] = normalize_answer("Amenities", txt)
            lead.status = "NEW"
            lead.save()

            # Save Property
            Property.objects.create(
                SELLER=lead,
                property_type=lead.data.get("property_type"),
                area_sqft=lead.data.get("area_sqft"),
                bhk=lead.data.get("bhk"),
                location=lead.data.get("location"),
                price_range=lead.data.get("price_range"),
                amenities=lead.data.get("amenities"),
            )

            # Score Lead
            score, segment, reason = ai_score_lead(lead)
            lead.score = score
            lead.segment = segment
            lead.rejection_reason = reason if segment == "NONE" else ""
            lead.status = "QUALIFIED" if segment in ["HOT", "WARM"] else "UNQUALIFIED"
            lead.save()

            # Save to Sheets
            add_lead_to_sheet(lead)

            # Create Google Drive Upload Link
            folder_name = f"{lead.data.get('name', 'Seller')} - {lead.phone}"
            drive_link = create_drive_folder(folder_name)

            if drive_link:
                lead.data["drive_link"] = drive_link
                lead.save()
                send_whatsapp_message(phone, f"📁 Upload property media here:\n{drive_link}")

            send_whatsapp_message(phone, f"🎉 Property saved! Lead segment: *{segment}*.")
            state.current_step = "COMPLETED"
            state.save()
            return

        if state.current_step == "SELL_Q7_OTHER":
            lead.data["amenities"] = normalize_answer("Amenities", txt)
            state.current_step = "SELL_Q7"
            state.save()
            return handle_message(phone, txt)


    # ======================================================================
    #  BUYER FLOW
    # ======================================================================
    if lead.lead_type == "BUYER":

        if state.current_step == "BUY_Q1":
            lead.data["property_type_preference"] = normalize_answer("Property Type", txt)
            lead.save()
            send_whatsapp_message(phone, "📏 Preferred area? (e.g., 1000–1500 sq.ft)")
            state.current_step = "BUY_Q2"
            state.save()
            return

        if state.current_step == "BUY_Q2":
            lead.data["area_preference"] = normalize_answer("Area", txt)
            lead.save()
            send_whatsapp_buttons(phone, "🛏 Bedrooms needed?", ["1BHK", "2BHK", "3BHK"])
            state.current_step = "BUY_Q3"
            state.save()
            return

        if state.current_step == "BUY_Q3":
            lead.data["bhk"] = normalize_answer("Bedrooms", txt)
            lead.save()
            send_whatsapp_message(phone, "🧾 Your name?")
            state.current_step = "BUY_Q4"
            state.save()
            return

        if state.current_step == "BUY_Q4":
            lead.data["name"] = text.strip()
            lead.save()
            send_whatsapp_message(phone, "📍 Preferred location?")
            state.current_step = "BUY_Q5"
            state.save()
            return

        if state.current_step == "BUY_Q5":
            lead.data["location_preference"] = normalize_answer("Location", txt)
            lead.save()
            send_whatsapp_message(phone, "💰 Budget?")
            state.current_step = "BUY_Q6"
            state.save()
            return

        if state.current_step == "BUY_Q6":
            lead.data["budget"] = normalize_answer("Budget", txt)
            lead.save()
            send_whatsapp_buttons(phone, "🏷 Amenities needed?", ["Pool", "Gym", "Other"])
            state.current_step = "BUY_Q7"
            state.save()
            return

        if state.current_step == "BUY_Q7":
            if txt == "other":
                send_whatsapp_message(phone, "Type preferred amenities (e.g., Lift, Garden, Backup):")
                state.current_step = "BUY_Q7_OTHER"
                state.save()
                return

            lead.data["amenities"] = normalize_answer("Amenities", txt)
            lead.status = "NEW"
            lead.save()

            # Score Lead
            score, segment, reason = ai_score_lead(lead)
            lead.score = score
            lead.segment = segment
            lead.rejection_reason = reason if segment == "NONE" else ""
            lead.status = "QUALIFIED" if segment in ["HOT", "WARM"] else "UNQUALIFIED"
            lead.save()

            # Save To Sheets
            add_lead_to_sheet(lead)

            # Show matching properties
            send_matching_properties_to_buyer(lead, phone)
            send_whatsapp_message(phone, f"🎉 Saved! Lead segment: *{segment}*.")
            state.current_step = "COMPLETED"
            state.save()
            return

        if state.current_step == "BUY_Q7_OTHER":
            lead.data["amenities"] = normalize_answer("Amenities", txt)
            state.current_step = "BUY_Q7"
            state.save()
            return handle_message(phone, txt)

    # ======================================================================
    #  FALLBACK
    # ======================================================================
    send_whatsapp_message(phone, "❓ I didn't understand that. Type *Hi* to start over.")



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
            
            # Handle button responses (interactive messages)
            if message.get("type") == "interactive" and message.get("interactive", {}).get("type") == "button_reply":
                button_reply = message["interactive"]["button_reply"]
                # Use button ID (more reliable) or fallback to title
                text = button_reply.get("id") or button_reply.get("title", "")
                print(f"🔘 Button clicked: ID='{button_reply.get('id')}', Title='{button_reply.get('title')}' -> Using: '{text}'")
            # Handle regular text messages
            elif message.get("type") == "text":
                text = message.get("text", {}).get("body", "")
                print(f"💬 Text message: '{text}'")
            else:
                text = ""
                print(f"⚠️ Unknown message type: {message.get('type')}")
            
            if text:
                handle_message(from_phone, text)
            else:
                print("⚠️ No text extracted from message")
        except Exception as e:
            print(f"❌ Webhook Error: {e}")
            import traceback
            traceback.print_exc()

        return JsonResponse({"status": "received"}, status=200)

    return HttpResponse("Invalid request", status=400)
