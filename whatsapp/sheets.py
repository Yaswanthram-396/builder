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
                "Drive Link",
                "Timestamp",
                "Selected Property Type",
                "Selected Property Location",
                "Selected Property Price",
                "Selected Property Drive Link",
                "Selection Timestamp"
            ]
            # Insert headers at the top (this will shift existing rows down)
            sheet.insert_row(headers, 1)
            # Format header row (make it bold)
            try:
                sheet.format("A1:R1", {"textFormat": {"bold": True}})
            except:
                pass  # Formatting is optional, continue if it fails
    except Exception as e:
        print(f"⚠️ Warning: Could not setup headers: {e}")


# ======== PUSH DATA ========
def add_lead_to_sheet(lead, update_existing=False):
    """
    Add or update lead in sheet.
    If update_existing=True, will try to find and update existing row by phone number.
    Otherwise, appends a new row.
    """
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
            data.get("drive_link", ""),  # Drive Link column
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            data.get("selected_property_type", ""),  # Selected Property Type
            data.get("selected_property_location", ""),  # Selected Property Location
            data.get("selected_property_price", ""),  # Selected Property Price
            data.get("selected_property_drive_link", ""),  # Selected Property Drive Link
            data.get("selection_timestamp", "")  # Selection Timestamp
        ]

        # Try to update existing row if requested
        if update_existing:
            all_values = sheet.get_all_values()
            for idx, existing_row in enumerate(all_values, start=1):
                # Skip header row
                if idx == 1:
                    continue
                # Check if phone matches (column C, index 2)
                if len(existing_row) > 2 and existing_row[2] == lead.phone:
                    # Update the existing row
                    sheet.delete_rows(idx)
                    sheet.insert_row(row, idx)
                    print(f"✅ Updated existing row {idx} for phone {lead.phone}")
                    return True

        # Append new row if not updating or row not found
        sheet.append_row(row)
        print(f"✅ Added new row for phone {lead.phone}")
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


# ======== UPDATE BUYER PROPERTY SELECTION ========
def update_buyer_property_selection(lead, selected_property, seller_lead):
    """Update buyer's row in sheets with selected property details"""
    try:
        sheet = connect_sheet().sheet1
        
        # Find the buyer's row by phone number
        all_values = sheet.get_all_values()
        row_index = None
        
        for idx, row in enumerate(all_values, start=1):
            # Skip header row
            if idx == 1:
                continue
            # Check if phone matches (column C, index 2)
            if len(row) > 2 and row[2] == lead.phone:
                row_index = idx
                break
        
        if not row_index:
            print(f"⚠️ Buyer row not found for phone {lead.phone}")
            return False
        
        # Get seller's drive link
        seller_data = seller_lead.data or {}
        drive_link = seller_data.get("drive_link", "")
        
        # Update the row with selected property details
        # Column indices: N=13, O=14, P=15, Q=16, R=17 (0-indexed: 13, 14, 15, 16, 17)
        updates = {
            13: selected_property.property_type or "",  # Selected Property Type
            14: selected_property.location or "",  # Selected Property Location
            15: selected_property.price_range or "",  # Selected Property Price
            16: drive_link,  # Selected Property Drive Link
            17: datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Selection Timestamp
        }
        
        # Update each cell
        for col_idx, value in updates.items():
            sheet.update_cell(row_index, col_idx + 1, value)  # +1 because gspread is 1-indexed
        
        print(f"✅ Updated buyer property selection in sheets (row {row_index})")
        return True
        
    except Exception as e:
        print(f"❌ Error updating buyer property selection: {e}")
        return False
