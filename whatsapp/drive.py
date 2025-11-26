import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Path to same Google credentials used for Sheets - use environment variable or default
GOOGLE_CREDENTIALS_FILE = os.getenv('GOOGLE_CREDENTIALS_FILE', 'google_credentials.json')
GOOGLE_AUTH_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), GOOGLE_CREDENTIALS_FILE)

SCOPES = ["https://www.googleapis.com/auth/drive"]

def create_drive_folder(folder_name):
    try:
        # Check if credentials file exists
        if not os.path.exists(GOOGLE_AUTH_FILE):
            print(f"❌ Drive Error: Credentials file not found at {GOOGLE_AUTH_FILE}")
            return None

        creds = service_account.Credentials.from_service_account_file(GOOGLE_AUTH_FILE, scopes=SCOPES)
        service = build("drive", "v3", credentials=creds)

        # Create folder metadata
        file_metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder"
        }

        folder = service.files().create(body=file_metadata, fields="id").execute()
        folder_id = folder.get("id")

        # Make folder public (Anyone with link can upload)
        permission = {
            "role": "writer",
            "type": "anyone",
            "allowFileDiscovery": False
        }
        service.permissions().create(fileId=folder_id, body=permission).execute()

        # Generate upload link
        upload_link = f"https://drive.google.com/drive/folders/{folder_id}?usp=drive_link"
        return upload_link

    except Exception as e:
        error_msg = str(e)
        if "accessNotConfigured" in error_msg or "403" in error_msg:
            print("❌ Drive Error: Google Drive API is not enabled in your Google Cloud project.")
            print("   Please enable it at: https://console.cloud.google.com/apis/library/drive.googleapis.com")
            print("   Or visit the link provided in the error message above.")
        else:
            print(f"❌ Drive Error: {e}")
        return None
