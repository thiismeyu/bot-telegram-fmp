import gspread
import json
import os

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

from app.config import CREDS


# ================= GOOGLE SHEETS (Service Account) =================
client = gspread.authorize(CREDS)


# ================= GOOGLE DRIVE (OAuth Hybrid) =================
token_json = os.getenv("GOOGLE_OAUTH_TOKEN")

if token_json:
    # Railway (pakai ENV)
    token_data = json.loads(token_json)

    oauth_creds = Credentials.from_authorized_user_info(
        token_data,
        scopes=["https://www.googleapis.com/auth/drive"]
    )

else:
    # Lokal (pakai file)
    oauth_creds = Credentials.from_authorized_user_file(
        "credentials/token.json",
        scopes=["https://www.googleapis.com/auth/drive"]
    )


# refresh token hanya jika expired
if oauth_creds.expired and oauth_creds.refresh_token:
    oauth_creds.refresh(Request())


# Google Drive client
drive = build(
    "drive",
    "v3",
    credentials=oauth_creds,
    cache_discovery=False
)