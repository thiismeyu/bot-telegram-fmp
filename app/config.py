import os
import json
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials

load_dotenv()

# ================= ENV =================
TOKEN = os.getenv("BOT_TOKEN")
DRIVE_ROOT_DATA = os.getenv("DRIVE_ROOT_DATA")
DRIVE_ROOT_FOTO = os.getenv("DRIVE_ROOT_FOTO")
USER_MANAGEMENT_ID = os.getenv("USER_MANAGEMENT_ID")
# ================= GOOGLE CREDENTIAL =================
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

GOOGLE_SERVICE_JSON = os.getenv("GOOGLE_SERVICE_JSON")

if GOOGLE_SERVICE_JSON:
    # Railway
    service_account_info = json.loads(GOOGLE_SERVICE_JSON)
    CREDS = ServiceAccountCredentials.from_json_keyfile_dict(
        service_account_info,
        scope
    )
else:
    # Lokal
    CREDS = ServiceAccountCredentials.from_json_keyfile_name(
        "credentials/service.json",
        scope
    )
BULAN_ID = {
    1:"JANUARI",2:"FEBRUARI",3:"MARET",4:"APRIL",
    5:"MEI",6:"JUNI",7:"JULI",8:"AGUSTUS",
    9:"SEPTEMBER",10:"OKTOBER",11:"NOVEMBER",12:"DESEMBER"
}
BULAN_FOLDER = {
    1:"01_JANUARI",
    2:"02_FEBRUARI",
    3:"03_MARET",
    4:"04_APRIL",
    5:"05_MEI",
    6:"06_JUNI",
    7:"07_JULI",
    8:"08_AGUSTUS",
    9:"09_SEPTEMBER",
    10:"10_OKTOBER",
    11:"11_NOVEMBER",
    12:"12_DESEMBER"
}
STO_MAPPING = {
    "BBU": {"sheet":"GAMAS BAU BAU","mitra":"FMP BAU BAU"},
    "WNC": {"sheet":"GAMAS BAU BAU","mitra":"FMP WANCI"},
    "UNH": {"sheet":"GAMAS UNAAHA","mitra":"FMP UNAAHA"}
}

KET_DEFAULT = [
    "GAMAS BESAR",
    "GAMAS KECIL",
    "INFRA CARE",
    "LAINNYA"
]