import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Path to google JSON - use environment variable or default
GOOGLE_CREDENTIALS_FILE = os.getenv('GOOGLE_CREDENTIALS_FILE', 'google_credentials.json')
GOOGLE_AUTH_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), GOOGLE_CREDENTIALS_FILE)

# ======== CONNECTION ========
def connect_sheet(sheet_name=None):
    if sheet_name is None:
        sheet_name = os.getenv('GOOGLE_SHEETS_NAME', 'Dheeraj Leads Database')
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_AUTH_FILE, scope)
    client = gspread.authorize(creds)
    return client.open(sheet_name)


# ======== PUSH DATA ========
def add_lead_to_sheet(lead):
    try:
        sheet = connect_sheet().sheet1  # first tab

        data = lead.data or {}
        row = [
            lead.lead_type,
            data.get("name", ""),
            lead.phone,
            lead.score or "",
            lead.segment or "",
            data.get("budget") or data.get("price_range") or "",
            data.get("location") or data.get("location_preference") or "",
            data.get("property_type") or data.get("property_type_preference") or "",
            data.get("bhk") or "",
            lead.status,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ]

        sheet.append_row(row)
        return True

    except Exception as e:
        print("❌ Google Sheets Error:", e)
        return False
