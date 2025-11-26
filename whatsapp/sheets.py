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


# ======== SETUP HEADERS ========
def setup_headers(sheet):
    """Set up column headers if they don't exist"""
    try:
        # Check if first row is empty or doesn't have headers
        existing_headers = sheet.row_values(1)
        if not existing_headers or existing_headers[0].upper() not in ["LEAD TYPE", "LEADTYPE"]:
            headers = [
                "Lead Type",
                "Name",
                "Phone",
                "Score",
                "Segment",
                "Budget/Price",
                "Location",
                "Property Type",
                "Area (sq.ft)",
                "BHK",
                "Status",
                "Timestamp"
            ]
            # Insert headers at the top (this will shift existing rows down)
            sheet.insert_row(headers, 1)
            # Format header row (make it bold)
            try:
                sheet.format("A1:L1", {"textFormat": {"bold": True}})
            except:
                pass  # Formatting is optional, continue if it fails
    except Exception as e:
        print(f"⚠️ Warning: Could not setup headers: {e}")


# ======== PUSH DATA ========
def add_lead_to_sheet(lead):
    try:
        sheet = connect_sheet().sheet1  # first tab

        # Setup headers if needed
        setup_headers(sheet)

        data = lead.data or {}
        row = [
            lead.lead_type,
            data.get("name", ""),
            lead.phone,
            lead.score or "",  # Score column
            lead.segment or "",  # Segment column
            data.get("budget") or data.get("price_range") or "",
            data.get("location") or data.get("location_preference") or "",
            data.get("property_type") or data.get("property_type_preference") or "",
            data.get("area_sqft") or data.get("area_preference") or "",  # Area field - FIXED
            data.get("bhk") or "",
            lead.status,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ]

        sheet.append_row(row)
        return True

    except Exception as e:
        error_msg = str(e)
        if "accessNotConfigured" in error_msg or "403" in error_msg or "Drive API" in error_msg:
            print("❌ Google Sheets Error: Google Drive API is not enabled in your Google Cloud project.")
            print("   Please enable it at: https://console.cloud.google.com/apis/library/drive.googleapis.com")
            print("   Note: Google Sheets requires Drive API to be enabled for file access.")
        else:
            print(f"❌ Google Sheets Error: {e}")
        return False
