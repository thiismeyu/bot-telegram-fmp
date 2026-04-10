from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime
import re
from app.services.google_services import client, drive
from app.keyboards import *
from app.utils import safe_upper, safe_label
from app.config import (
    USER_MANAGEMENT_ID,
    STO_MAPPING,
    KET_DEFAULT,
    BULAN_ID,
    BULAN_FOLDER,
    DRIVE_ROOT_DATA,
    DRIVE_ROOT_FOTO
)

from telegram import ReplyKeyboardMarkup

import time

dashboard_cache = {
    "data": None,
    "last_update": 0
}

SPREADSHEET_CACHE = {}

TICKET_CACHE = set()
TICKET_INDEX = {}
FOLDER_CACHE = {}
user_sheet = client.open_by_key(USER_MANAGEMENT_ID).worksheet("USERS")

def delete_drive_file_from_cell(cell_value):
    try:
        match = re.search(r'd/([a-zA-Z0-9_-]+)', cell_value)
        if not match:
            print("Tidak ada file ID")
            return False

        file_id = match.group(1)
        print("Coba hapus file:", file_id)

        drive.files().delete(fileId=file_id).execute()

        print("BERHASIL DIHAPUS")
        return True

    except Exception as e:
        print("ERROR DELETE:", e)
        return False
    


def get_formula_cell(ws, row, col):
    values = ws.get_values(
        f"A{row}:ZZ{row}",
        value_render_option="FORMULA"
    )

    if not values:
        return ""

    row_data = values[0]

    if col-1 >= len(row_data):
        return ""

    return row_data[col-1]

def get_existing_spreadsheet(year, month):
    
    folder_id = get_year_folder_data(year)
    month_name = BULAN_FOLDER[month]

    title = f"GAMAS_{month_name}_{year}"

    files = drive.files().list(
        q=f"name='{title}' and '{folder_id}' in parents and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false",
        fields="files(id)"
    ).execute()

    if files["files"]:
        return files["files"][0]["id"]

    return None
    
def get_gamas_dashboard():
    
    current_year = datetime.now().year
    years = [current_year-1, current_year, current_year+1]

    total_all = 0
    total_per_year = {}
    total_per_sto = {"BBU":0,"WNC":0,"UNH":0}
    per_sheet_data = {}

    for year in years:

        total_year = 0

        # 🔥 LOOP SEMUA BULAN
        for month in range(1, 13):

            try:
                sheet_id = get_existing_spreadsheet(year, month)

                if not sheet_id:
                    continue

                master = client.open_by_key(sheet_id)
            except:
                continue

            for ws in master.worksheets():

                sto_col = ws.col_values(2)
                date_col = ws.col_values(5)
                bulan_col = ws.col_values(10)

                if len(sto_col) <= 1:
                    continue

                sheet_name = ws.title
                count = len(sto_col) - 1

                total_year += count
                total_all += count

                if sheet_name not in per_sheet_data:
                    per_sheet_data[sheet_name] = {
                        "total": 0,
                        "bulan": {},
                        "min_date": None,
                        "max_date": None
                    }

                per_sheet_data[sheet_name]["total"] += count

                for i in range(1, len(sto_col)):

                    sto = safe_upper(sto_col[i])
                    bulan = bulan_col[i] if i < len(bulan_col) else ""
                    tanggal = date_col[i] if i < len(date_col) else ""

                    # hitung STO
                    if sto in total_per_sto:
                        total_per_sto[sto] += 1

                    # hitung bulan
                    if bulan:
                        per_sheet_data[sheet_name]["bulan"][bulan] = \
                            per_sheet_data[sheet_name]["bulan"].get(bulan, 0) + 1

                    # hitung rentang tanggal
                    try:
                        d = datetime.strptime(tanggal, "%d/%m/%Y")

                        if not per_sheet_data[sheet_name]["min_date"] or d < per_sheet_data[sheet_name]["min_date"]:
                            per_sheet_data[sheet_name]["min_date"] = d

                        if not per_sheet_data[sheet_name]["max_date"] or d > per_sheet_data[sheet_name]["max_date"]:
                            per_sheet_data[sheet_name]["max_date"] = d

                    except:
                        pass

        if total_year > 0:
            total_per_year[year] = total_year

    return total_all, total_per_year, total_per_sto, per_sheet_data
def get_gamas_dashboard_cached():
    now = time.time()

    # Cache berlaku 1 jam (3600 detik)
    if dashboard_cache["data"] and (now - dashboard_cache["last_update"] < 3600):
        print("DASHBOARD CACHE USED")
        return dashboard_cache["data"]

    print("DASHBOARD REGENERATE")

    result = get_gamas_dashboard()

    dashboard_cache["data"] = result
    dashboard_cache["last_update"] = now

    return result
# ================= USER MANAGEMENT =================
def renumber_users():
    data = user_sheet.get_all_values()
    for i in range(2, len(data)+1):
        user_sheet.update_cell(i, 1, i-1)


def get_user(user_id):
    users = user_sheet.get_all_values()
    for i in range(1, len(users)):
        if users[i][1] == str(user_id):
            return {
                "row": i+1,
                "nama": users[i][2],
                "role": users[i][4],
                "status": users[i][5]
            }
    return None


def add_user(user_id, nama, telp):
    today = datetime.now().strftime("%d/%m/%Y")
    user_sheet.append_row([
        "",
        str(user_id),
        safe_upper(nama),
        telp,
        "TEKNISI",
        "PENDING",
        today
    ])
    renumber_users()


def update_status(user_id, status):
    user = get_user(user_id)
    if user:
        user_sheet.update_cell(user["row"], 6, status)
        return True
    return False


def check_access(update):
    user = get_user(update.effective_user.id)

    if not user:
        return "NOT_REGISTERED"

    if user["status"] == "PENDING":
        return "PENDING"

    if user["status"] == "NONAKTIF":
        return "NONAKTIF"

    if user["status"] == "AKTIF":
        return user["role"]

    return "INVALID"
# ================= DRIVE ENGINE =================

def get_folder(name, parent):
    
    key = f"{parent}_{name}"

    if key in FOLDER_CACHE:
        return FOLDER_CACHE[key]

    query = f"name='{name}' and '{parent}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"

    result = drive.files().list(
        q=query,
        fields="files(id,name)",
        pageSize=1
    ).execute()

    files = result.get("files", [])

    if len(files) > 0:
        folder_id = files[0]["id"]
    else:
        time.sleep(0.3)
        folder = drive.files().create(
            body={
                "name": name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent]
            },
            fields="id"
        ).execute()

        folder_id = folder["id"]

    FOLDER_CACHE[key] = folder_id

    return folder_id


def get_year_folder_data(year):
    return get_folder(f"01_GAMAS_{year}", DRIVE_ROOT_DATA)


def get_year_folder_foto(year):
    return get_folder(f"01_GAMAS_{year}", DRIVE_ROOT_FOTO)


def get_ticket_date(ws, row):
    date_str = ws.cell(row, 5).value

    if not date_str:
        raise Exception("Tanggal tidak ditemukan di sheet")

    return datetime.strptime(date_str, "%d/%m/%Y")

def get_ticket_folder(ticket, date):
    
    year = date.year
    month = BULAN_FOLDER[date.month]

    year_folder = get_folder(f"01_GAMAS_{year}", DRIVE_ROOT_FOTO)

    month_folder = get_folder(month, year_folder)

    ticket_folder = get_folder(ticket, month_folder)

    return ticket_folder



def get_year_spreadsheet(year, date):
    cache_key = f"{year}_{date.month}"

    if cache_key in SPREADSHEET_CACHE:
        return SPREADSHEET_CACHE[cache_key]
    
    folder_year = get_year_folder_data(year)
    folder_id = folder_year
    month_name = BULAN_FOLDER[date.month]

    title = f"GAMAS_{month_name}_{year}"

    files = drive.files().list(
        q=f"name='{title}' and '{folder_id}' in parents and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false",
        fields="files(id)"
    ).execute()

    header = [
        "NO",
        "STO",
        "NOMOR TIKET",
        "CATUAN/ NAMA GAMAS (NAMA ODP / ODC / OLT)",
        "REPORTED DATE",
        "JASA",
        "KETERANGAN",
        "PIC (NAMA PENGAMBIL)",
        "NAMA MITRA",
        "BULAN"
    ]

    # ================= SPREADSHEET SUDAH ADA =================
    if files["files"]:

        sheet_id = files["files"][0]["id"]
        master = client.open_by_key(sheet_id)

        titles = [ws.title for ws in master.worksheets()]

        if "GAMAS BAU BAU" not in titles:
            ws1 = master.sheet1
            ws1.update_title("GAMAS BAU BAU")
            ws1.update("A1:J1", [header])
            

        if "GAMAS UNAAHA" not in titles:
            ws2 = master.add_worksheet(
                title="GAMAS UNAAHA",
                rows=1000,
                cols=20
            )
            ws2.update("A1:J1", [header])
            
        
        SPREADSHEET_CACHE[cache_key] = sheet_id

        return sheet_id

    # ================= SPREADSHEET BELUM ADA =================
    file = drive.files().create(
        body={
            "name": title,
            "mimeType": "application/vnd.google-apps.spreadsheet",
            "parents": [folder_id]
        },
        fields="id"
    ).execute()

    sheet_id = file["id"]

    master = client.open_by_key(sheet_id)

    ws1 = master.sheet1
    ws1.update_title("GAMAS BAU BAU")
    ws1.update("A1:J1", [header])
    

    ws2 = master.add_worksheet(
        title="GAMAS UNAAHA",
        rows=1000,
        cols=20
    )

    ws2.update("A1:J1", [header])
    
    SPREADSHEET_CACHE[cache_key] = sheet_id

    return sheet_id
def load_ticket_cache():
    
    global TICKET_CACHE

    current_year = datetime.now().year
    years = [current_year-1, current_year, current_year+1]

    for year in years:

        try:

            sheet_id = get_year_spreadsheet(year, datetime(year,1,1))
            master = client.open_by_key(sheet_id)

            for ws in master.worksheets():

                headers = [h.strip().upper() for h in ws.row_values(1)]

                if "NOMOR TIKET" not in headers:
                    continue

                col = headers.index("NOMOR TIKET") + 1

                values = ws.col_values(col)

                for i, v in enumerate(values[1:], start=2):
    
                    if v:
                        ticket = safe_upper(v)

                        TICKET_CACHE.add(ticket)

                        TICKET_INDEX[ticket] = {
                            "sheet": ws,
                            "year": year
                        }

        except:
            continue

    print("TICKET CACHE LOADED:", len(TICKET_CACHE))
    
def ensure_sheet(master, sheet_name):
    
    header = [
        "NO",
        "STO",
        "NOMOR TIKET",
        "CATUAN/ NAMA GAMAS (NAMA ODP / ODC / OLT)",
        "REPORTED DATE",
        "JASA",
        "KETERANGAN",
        "PIC (NAMA PENGAMBIL)",
        "NAMA MITRA",
        "BULAN"
    ]

    try:
        ws = master.worksheet(sheet_name)
        return ws

    except:

        ws = master.add_worksheet(
            title=sheet_name,
            rows=1000,
            cols=50
        )

        ws.update("A1:J1", [header])
        ws.update("A2", "=ROW()-1")

        return ws


# ================= INSERT SORTED =================
def insert_sorted(ws, row_data, date_value):
    
    # ambil semua tanggal
    dates = ws.col_values(5)

    insert_position = len(dates) + 1

    for i in range(2, len(dates)+1):

        try:
            existing_date = datetime.strptime(dates[i-1], "%d/%m/%Y")

            if date_value < existing_date:
                insert_position = i
                break

        except:
            continue

    ws.insert_row(row_data, insert_position)

    # update nomor otomatis
    total = len(ws.col_values(1)) - 1

    numbers = [[i] for i in range(1, total+1)]

    ws.update(f"A2:A{total+1}", numbers)

    return insert_position


# ================= FIND TIKET LINTAS TAHUN =================
def find_ticket_global(ticket):
    
    ticket = safe_upper(ticket)

    if ticket in TICKET_INDEX:

        data = TICKET_INDEX[ticket]

        ws = data["sheet"]

        row = find_ticket_row(ws, ticket)

        return ws, row, data["year"]

    return None, None, None
def find_ticket_row(ws, ticket):
    
    headers = [h.strip().upper() for h in ws.row_values(1)]

    if "NOMOR TIKET" not in headers:
        return None

    col = headers.index("NOMOR TIKET") + 1

    values = ws.col_values(col)

    ticket = safe_upper(ticket)

    for i, v in enumerate(values[1:], start=2):

        if safe_upper(v) == ticket:
            return i

    return None

# ================= FOTO LIST DINAMIS =================
def foto_list(ws, row):
    values = ws.get_values(
        f"A{row}:ZZ{row}",
        value_render_option="FORMULA"
    )

    if not values:
        return []

    row_data = values[0]
    
 

    fotos = []
    col = 11

    while col <= len(row_data):

        cell = row_data[col-1]

        if cell and ("HYPERLINK" in cell or "TEXTJOIN" in cell):

            lines = cell.split("\n")

            for line in lines:
                try:
                    parts = line.split('"')
                    label = parts[3]
                    fotos.append((col, label))
                except:
                    pass

        col += 1

    return fotos
def foto_list_detail(ws, row):
    
    row_data = ws.get_values(
        f"A{row}:ZZ{row}",
        value_render_option="FORMULA"
    )[0]

    fotos = []

    col = 11

    while col <= len(row_data):

        cell = row_data[col-1]

        if cell and ("HYPERLINK" in cell or "TEXTJOIN" in cell):

            lines = cell.split("\n")

            for i,line in enumerate(lines):

                try:
                    parts = line.split('"')
                    link = parts[1]
                    label = parts[3]

                    fotos.append({
                        "col": col,
                        "line": i,
                        "link": link,
                        "label": label
                    })

                except:
                    pass

        col += 1

    return fotos

def find_empty_foto_col(ws,row):

    row_data = ws.row_values(row)
    col = 11

    while True:
        if col > len(row_data) or not row_data[col-1]:
            return col
        col += 1

def add_foto_link(ws, row, col, url, label):
    
    existing = get_formula_cell(ws, row, col)

    new_link = f'HYPERLINK("{url}","{label}")'

    if existing and "TEXTJOIN" in existing:

        links = existing.replace('=TEXTJOIN(CHAR(10),TRUE,', '').rstrip(')')
        value = f'=TEXTJOIN(CHAR(10),TRUE,{links},{new_link})'

    elif existing:

        old = existing.replace("=", "")
        value = f'=TEXTJOIN(CHAR(10),TRUE,{old},{new_link})'

    else:

        value = f'=TEXTJOIN(CHAR(10),TRUE,{new_link})'

    ws.update_cell(row, col, value)

def find_label_column(ws, row, label):
    
    row_data = ws.get_values(
        f"A{row}:ZZ{row}",
        value_render_option="FORMULA"
    )[0]

    label = safe_label(label)

    col = 11

    while col <= len(row_data):

        cell = row_data[col-1]

        if cell:

            lines = cell.split("\n")

            for line in lines:
                try:
                    parts = line.split('"')
                    cell_label = parts[3]

                    if safe_label(cell_label) == label:
                        return col
                except:
                    pass

        col += 1

    return None

# ================= PREVIEW BUILDER =================
def build_preview(d):
    
    tanggal = d["DATE"].strftime("%d/%m/%Y")

    return f"""
📋 PREVIEW LAPORAN

INC : {d['INC']}   /edit_inc
PIC : {d['PIC']}   /edit_pic
Tanggal : {tanggal}   /edit_date
STO : {d['STO']}   /edit_sto
Catuan : {d['LOC']}   /edit_loc
Jasa : {d['JASA']}   /edit_jasa
Keterangan : {d['KET']}   /edit_ket

Klik 💾 SIMPAN jika sudah benar
"""

# ================= TEXT HANDLER =================
async def text(update:Update,context:ContextTypes.DEFAULT_TYPE):

    msg = update.message.text.strip()

    # ===== GLOBAL BACK =====
    
    if msg == "🔙 KEMBALI":
        context.user_data.clear()

        role = check_access(update)

        if role == "ADMIN":
            await update.message.reply_text("Kembali ke menu admin.", reply_markup=admin_menu())
        else:
            await update.message.reply_text("Kembali ke menu utama.", reply_markup=main_menu())
        return
    # ===== GLOBAL BATAL =====
    if msg == "❌ BATAL":

        # jika sedang input/edit
        if context.user_data:

            # jika sedang preview kembali ke menu
            if context.user_data.get("mode") == "PREVIEW":
                context.user_data.clear()
                await update.message.reply_text("Input dibatalkan.", reply_markup=main_menu())
                return

            # jika sedang edit kembali ke preview
            if "mode" in context.user_data:
                context.user_data["mode"] = "PREVIEW"

                await update.message.reply_text(
                    build_preview(context.user_data),
                    reply_markup=preview_menu()
                )
                return

        await update.message.reply_text("Tidak ada proses yang dibatalkan.")
        return
    # ===== REGISTRASI =====
    if context.user_data.get("mode")=="REG_NAMA":
        context.user_data["reg_nama"]=safe_upper(msg)
        context.user_data["mode"]="REG_TELP"
        await update.message.reply_text("Masukkan Nomor Telepon:")
        return

    if context.user_data.get("mode")=="REG_TELP":
        add_user(update.effective_user.id,context.user_data["reg_nama"],msg)
        context.user_data.clear()
        await update.message.reply_text("✅ Registrasi berhasil. Status: PENDING.\nHubungi admin.")
        return

    # ===== ACCESS CONTROL =====
    access = check_access(update)

    if access == "NOT_REGISTERED":
        context.user_data.clear()
        context.user_data["mode"] = "REG_NAMA"
        await update.message.reply_text("👋 Anda belum terdaftar.\nMasukkan Nama Lengkap:")
        return

    if access == "PENDING":
        await update.message.reply_text("⏳ Akun Anda masih menunggu persetujuan admin.")
        return

    if access == "NONAKTIF":
        await update.message.reply_text("🚫 Akun Anda tidak aktif.")
        return


    # ===== INPUT LAPORAN =====
    if msg=="📝 Input Laporan":
        context.user_data.clear()
        context.user_data["mode"]="INPUT_PIC"
        await update.message.reply_text("Masukkan Nama PIC (Nama Pengambil):")
        return

    if context.user_data.get("mode")=="INPUT_PIC":
        if msg in ["🔙 KEMBALI", "❌ BATAL"]:
            return
        context.user_data["PIC"]=safe_upper(msg)
        context.user_data["mode"]="INPUT_DATE"
        await update.message.reply_text("Masukkan Tanggal (dd/mm/yyyy):")
        return

    if context.user_data.get("mode")=="INPUT_DATE":
        try:
            d=datetime.strptime(msg,"%d/%m/%Y")
            if d>datetime.now():
                await update.message.reply_text("❌ Tanggal tidak boleh melebihi hari ini")
                return
            context.user_data["DATE"]=d
            context.user_data["mode"]="INPUT_INC"
            await update.message.reply_text("Masukkan Nomor Tiket:")
        except:
            await update.message.reply_text("❌ Format salah. Gunakan dd/mm/yyyy")
        return

    if context.user_data.get("mode")=="INPUT_INC":

        ticket = safe_upper(msg)

        if ticket in TICKET_CACHE:
            await update.message.reply_text("❌ Nomor tiket sudah ada.")
            return

        context.user_data["INC"]=ticket
        context.user_data["mode"]="INPUT_STO"
        await update.message.reply_text("Pilih STO:",reply_markup=sto_menu())
        return

    if context.user_data.get("mode")=="INPUT_STO":
        if msg not in STO_MAPPING:
            await update.message.reply_text("❌ Pilih STO dari tombol.")
            return

        context.user_data["STO"]=msg
        context.user_data["mode"]="INPUT_LOC"
        await update.message.reply_text("Masukkan Catuan / Nama GAMAS:")
        return

    if context.user_data.get("mode")=="INPUT_LOC":
        if msg in ["🔙 KEMBALI", "❌ BATAL"]:
            return
        context.user_data["LOC"]=safe_upper(msg)
        context.user_data["mode"]="INPUT_JASA"
        await update.message.reply_text("Masukkan Jasa / Material:")
        return

    if context.user_data.get("mode")=="INPUT_JASA":
        if msg in ["🔙 KEMBALI", "❌ BATAL"]:
            return
        context.user_data["JASA"]=safe_upper(msg)
        context.user_data["mode"]="INPUT_KET"
        await update.message.reply_text("Pilih Keterangan:",reply_markup=ket_menu())
        return

    if context.user_data.get("mode")=="INPUT_KET":
        
        if msg == "LAINNYA":
            context.user_data["mode"]="INPUT_KET_MANUAL"
            await update.message.reply_text("Masukkan Keterangan lainnya:")
            return

        if msg not in KET_DEFAULT:
            await update.message.reply_text("❌ Pilih dari tombol.")
            return

        context.user_data["KET"]=safe_upper(msg)
        context.user_data["mode"]="PREVIEW"
        await update.message.reply_text(build_preview(context.user_data),reply_markup=preview_menu())
        return
    
    if context.user_data.get("mode")=="INPUT_KET_MANUAL":
        if msg in ["🔙 KEMBALI", "❌ BATAL"]:
            return
        context.user_data["KET"]=safe_upper(msg)
        context.user_data["mode"]="PREVIEW"
        await update.message.reply_text(build_preview(context.user_data),reply_markup=preview_menu())
        return

    # ===== EDIT SYSTEM FINAL =====

    # ===== TRIGGER EDIT =====
    if msg.startswith("/edit_") and context.user_data.get("mode") == "PREVIEW":

        field = msg.replace("/edit_", "").upper()

        if field not in ["INC", "PIC", "DATE", "STO", "LOC", "JASA", "KET"]:
            await update.message.reply_text("Field tidak dikenali.")
            return

        context.user_data["edit_field"] = field

        # STO (hybrid tombol)
        if field == "STO":
            context.user_data["mode"] = "EDIT_STO"
            await update.message.reply_text(
                "Pilih STO baru:",
                reply_markup=sto_menu()
            )
            return

        # KET (hybrid tombol + lainnya)
        if field == "KET":
            context.user_data["mode"] = "EDIT_KET"
            await update.message.reply_text(
                "Pilih Keterangan baru:",
                reply_markup=ket_menu()
            )
            return

        # DATE (format khusus)
        if field == "DATE":
            context.user_data["mode"] = "EDIT_DATE"
            await update.message.reply_text(
                "Masukkan tanggal baru (dd/mm/yyyy):"
            )
            return

        # Field biasa
        context.user_data["mode"] = "WAIT_EDIT"
        await update.message.reply_text(
            f"Masukkan nilai baru untuk {field}:"
        )
        return


    # ===== HANDLE EDIT STO =====
    if context.user_data.get("mode") == "EDIT_STO":

        if msg not in STO_MAPPING:
            await update.message.reply_text("❌ Pilih STO dari tombol.")
            return

        context.user_data["STO"] = msg
        context.user_data["mode"] = "PREVIEW"

        await update.message.reply_text(
            build_preview(context.user_data),
            reply_markup=preview_menu()
        )
        return


    # ===== HANDLE EDIT KET =====
    if context.user_data.get("mode") == "EDIT_KET":

        if msg == "LAINNYA":
            context.user_data["mode"] = "EDIT_KET_MANUAL"
            await update.message.reply_text(
                "Masukkan Keterangan baru:"
            )
            return

        if msg not in KET_DEFAULT:
            await update.message.reply_text("❌ Pilih dari tombol.")
            return

        context.user_data["KET"] = safe_upper(msg)
        context.user_data["mode"] = "PREVIEW"

        await update.message.reply_text(
            build_preview(context.user_data),
            reply_markup=preview_menu()
        )
        return


    # ===== HANDLE EDIT KET MANUAL =====
    if context.user_data.get("mode") == "EDIT_KET_MANUAL":
        if msg in ["🔙 KEMBALI", "❌ BATAL"]:
            return

        context.user_data["KET"] = safe_upper(msg)
        context.user_data["mode"] = "PREVIEW"

        await update.message.reply_text(
            build_preview(context.user_data),
            reply_markup=preview_menu()
        )
        return


    # ===== HANDLE EDIT DATE =====
    if context.user_data.get("mode") == "EDIT_DATE":

        try:
            d = datetime.strptime(msg, "%d/%m/%Y")
            context.user_data["DATE"] = d
            context.user_data["mode"] = "PREVIEW"

            await update.message.reply_text(
                build_preview(context.user_data),
                reply_markup=preview_menu()
            )
        except:
            await update.message.reply_text(
                "Format salah. Gunakan dd/mm/yyyy"
            )
        return


    # ===== HANDLE EDIT FIELD BIASA =====
    if context.user_data.get("mode") == "WAIT_EDIT":
        if msg in ["🔙 KEMBALI", "❌ BATAL"]:
            return
    
        field = context.user_data["edit_field"]
        context.user_data[field] = safe_upper(msg)
        context.user_data["mode"] = "PREVIEW"

        await update.message.reply_text(
            build_preview(context.user_data),
            reply_markup=preview_menu()
        )
        return

    # ===== SIMPAN =====
    # ===== SIMPAN =====
    if msg=="💾 SIMPAN" and context.user_data.get("mode")=="PREVIEW":

        try:

            d=context.user_data
            year=d["DATE"].year

            sheet_id=get_year_spreadsheet(year, d["DATE"])
            master_year=client.open_by_key(sheet_id)

            sheet_name=STO_MAPPING[d["STO"]]["sheet"]
            mitra=STO_MAPPING[d["STO"]]["mitra"]

            # pastikan sheet ada
            ws = ensure_sheet(master_year, sheet_name)

            row=[
                "",
                d["STO"],
                d["INC"],
                d["LOC"],
                d["DATE"].strftime("%d/%m/%Y"),
                d["JASA"],
                d["KET"],
                d["PIC"],
                mitra,
                BULAN_ID[d["DATE"].month]
            ]

            row_position = insert_sorted(ws,row,d["DATE"])

            TICKET_CACHE.add(d["INC"])

            TICKET_INDEX[d["INC"]] = {
                "sheet": ws,
                "year": year
            }

            dashboard_cache["data"] = None

            context.user_data.clear()

            await update.message.reply_text(
                "✅ Laporan berhasil disimpan.",
                reply_markup=main_menu()
            )

        except Exception as e:

            print("ERROR SIMPAN:", e)

            await update.message.reply_text(
                "❌ Gagal menyimpan laporan.\nSilakan coba lagi atau hubungi admin."
            )

        return

    
    
    # ===== MULAI UPLOAD FOTO =====
    if msg == "📸 Upload Foto":
        context.user_data.clear()
        context.user_data["mode"] = "UPLOAD_INC"
        await update.message.reply_text("Masukkan Nomor Tiket:")
        return

    if context.user_data.get("mode") == "UPLOAD_INC":
        
        ticket = safe_upper(msg)

        ws, row, year = find_ticket_global(ticket)

        if not ws:
            await update.message.reply_text("❌ Nomor tiket tidak ditemukan.")
            return

        context.user_data["INC"] = ticket

        

        fotos = foto_list_detail(ws, row)

        context.user_data["foto_map"] = fotos

        text = "📸 FOTO SAAT INI:\n\n"

        if not fotos:
            text += "Belum ada foto.\n"

        else:

            label_count = {}

            for f in fotos:
                label = safe_label(f["label"])
                label_count[label] = label_count.get(label,0) + 1

            # ===== ringkasan =====
            text += "📊 Ringkasan Foto:\n"

            for label,count in label_count.items():
                text += f"{label} ({count} foto)\n"

            text += "\n"

            # ===== detail =====
            text += "📋 Detail Foto:\n"

            for i,f in enumerate(fotos,1):
                text += f"{i}. {f['label']}   /edit{i} /hapus{i}\n"
            

        await update.message.reply_text(text)

        context.user_data["mode"] = "UPLOAD_LABEL"

        await update.message.reply_text("Masukkan Label Foto:")

        return

    if context.user_data.get("mode") == "UPLOAD_LABEL":
        if msg in ["🔙 KEMBALI", "❌ BATAL"]:
            return
        context.user_data["label"] = safe_label(msg).upper()
        context.user_data["mode"] = "WAIT_FOTO"
        await update.message.reply_text("Kirim foto sekarang.")
        return
    
    if msg=="➕ TAMBAH FOTO":
        context.user_data["mode"]="UPLOAD_LABEL"
        await update.message.reply_text("Masukkan Label Foto:")
        return

    if msg=="✅ SELESAI":
        context.user_data.clear()
        await update.message.reply_text("Upload selesai.",reply_markup=main_menu())
        return
    
   
    # ===== FOTO LIST EDIT / HAPUS =====

    if msg.startswith("/hapus") and msg[6:].isdigit():

        if "INC" not in context.user_data:
            await update.message.reply_text(
                "❌ Sesi upload tidak aktif. Silakan mulai ulang dari Upload Foto."
            )
            return

        idx = int(msg.replace("/hapus",""))

        ws, row, year = find_ticket_global(context.user_data["INC"])

        if not ws:
            await update.message.reply_text("❌ Data tiket tidak ditemukan.")
            return

        fotos = foto_list_detail(ws, row)

        if 1 <= idx <= len(fotos):

            f = fotos[idx-1]

            col = f["col"]
            line = f["line"]

            cell = get_formula_cell(ws, row, col) or ""

            lines = cell.split("\n")

            if line >= len(lines):
                await update.message.reply_text("❌ Data foto tidak valid.")
                return

            target = lines[line]

            delete_drive_file_from_cell(target)

            del lines[line]

            if len(lines) == 0:
                ws.update_cell(row, col, "")
            else:
                ws.update_cell(row, col, "\n".join(lines))

        else:
            await update.message.reply_text("❌ Nomor foto tidak valid.")
            return

        fotos = foto_list_detail(ws, row)

        context.user_data["foto_map"] = fotos

        text = "📸 FOTO SAAT INI:\n\n"

        if not fotos:
            text += "Belum ada foto.\n"
        else:
            for i,f in enumerate(fotos,1):
                text += f"{i}. {f['label']}   /edit{i} /hapus{i}\n"

        await update.message.reply_text(text, reply_markup=foto_menu())

        return


    # ===== EDIT FOTO =====

    if msg.startswith("/edit") and msg[5:].isdigit():

        if "INC" not in context.user_data:
            await update.message.reply_text(
                "❌ Sesi upload tidak aktif. Silakan mulai ulang dari Upload Foto."
            )
            return

        idx = int(msg.replace("/edit",""))

        ws, row, year = find_ticket_global(context.user_data["INC"])

        if not ws:
            await update.message.reply_text("❌ Data tiket tidak ditemukan.")
            return

        fotos = foto_list_detail(ws, row)

        if 1 <= idx <= len(fotos):

            f = fotos[idx-1]

            context.user_data["edit_foto_col"] = f["col"]
            context.user_data["edit_foto_line"] = f["line"]
            context.user_data["label"] = f["label"]

            context.user_data["mode"] = "WAIT_EDIT_FOTO"

            await update.message.reply_text(
                f"Upload foto baru untuk mengganti foto {f['label']}"
            )

        else:
            await update.message.reply_text("❌ Nomor foto tidak valid.")

        return


    if context.user_data.get("mode") == "EDIT_FOTO_LABEL":
        if msg in ["🔙 KEMBALI", "❌ BATAL"]:
            return
        context.user_data["label"] = safe_label(msg)
        context.user_data["mode"] = "WAIT_EDIT_FOTO"
        await update.message.reply_text("Kirim foto baru sekarang.")
        return
    # ===== DASHBOARD ADMIN =====
    if msg == "/dashboard refresh" and check_access(update) == "ADMIN":
    
        await update.message.reply_text("🔄 Rebuild dashboard...")

        dashboard_cache["data"] = None

        total_all, total_per_year, total_per_sto, per_sheet_data = get_gamas_dashboard_cached()

        text = "📊 DASHBOARD GAMAS (REFRESH)\n\n"
        text += f"Total Semua Laporan : {total_all}\n\n"

        for y, t in total_per_year.items():
            text += f"📅 Tahun {y} : {t}\n"

        text += "\n📍 Per STO:\n"
        for sto, t in total_per_sto.items():
            text += f"{sto} : {t}\n"

        text += "\n📂 Per Sheet:\n\n"

        for sheet_name, data in per_sheet_data.items():

            text += f"🔹 {sheet_name}\n"
            text += f"Total : {data['total']}\n"

            if data["min_date"] and data["max_date"]:
                start = data["min_date"].strftime("%d/%m/%Y")
                end = data["max_date"].strftime("%d/%m/%Y")
                text += f"Rentang : {start} s/d {end}\n"

            for bulan, jumlah in data["bulan"].items():
                text += f"{bulan} : {jumlah}\n"

            text += "\n"

        await update.message.reply_text(text, reply_markup=admin_menu())

        return
    if msg=="📊 Dashboard User" and check_access(update)=="ADMIN":

        users=user_sheet.get_all_values()
        total=len(users)-1

        aktif=0
        pending=0
        nonaktif=0

        for i in range(1,len(users)):
            status=users[i][5]
            if status=="AKTIF":
                aktif+=1
            elif status=="PENDING":
                pending+=1
            elif status=="NONAKTIF":
                nonaktif+=1

        text=f"""
    📊 DASHBOARD USER

    Total User : {total}
    AKTIF : {aktif}
    PENDING : {pending}
    NONAKTIF : {nonaktif}
    """
        await update.message.reply_text(text,reply_markup=admin_menu())
        return

    if msg == "📊 Dashboard GAMAS" and check_access(update) == "ADMIN":
    
        total_all, total_per_year, total_per_sto, per_sheet_data = get_gamas_dashboard_cached()

        text = "📊 DASHBOARD GAMAS PRO\n\n"
        text += f"Total Semua Laporan : {total_all}\n\n"

        for y, t in total_per_year.items():
            text += f"📅 Tahun {y} : {t}\n"

        text += "\n📍 Per STO:\n"
        for sto, t in total_per_sto.items():
            text += f"{sto} : {t}\n"

        text += "\n📂 Per Sheet:\n\n"

        for sheet_name, data in per_sheet_data.items():

            text += f"🔹 {sheet_name}\n"
            text += f"Total : {data['total']}\n"

            if data["min_date"] and data["max_date"]:
                start = data["min_date"].strftime("%d/%m/%Y")
                end = data["max_date"].strftime("%d/%m/%Y")
                text += f"Rentang : {start} s/d {end}\n"

            for bulan, jumlah in data["bulan"].items():
                text += f"{bulan} : {jumlah}\n"

            text += "\n"

        await update.message.reply_text(text, reply_markup=admin_menu())
        return

    if msg == "👥 Kelola User" and check_access(update) == "ADMIN":
    
        users = user_sheet.get_all_values()
        text = "👥 DAFTAR USER:\n\n"

        for i in range(1, len(users)):
            text += f"{users[i][1]} - {users[i][2]} ({users[i][5]})\n"

        text += "\nKetik TELEGRAM ID user untuk ubah status."

        context.user_data["mode"] = "ADMIN_SELECT_USER"

        await update.message.reply_text(text, reply_markup=admin_menu())
        return
    
    if msg=="📋 List Pending" and check_access(update)=="ADMIN":

        users=user_sheet.get_all_values()
        text="📋 USER PENDING:\n\n"

        found=False
        for i in range(1,len(users)):
            if users[i][5]=="PENDING":
                found=True
                text+=f"{users[i][1]} - {users[i][2]}\n"

        if not found:
            text+="Tidak ada."

        await update.message.reply_text(text,reply_markup=admin_menu())
        return
    
    
    if context.user_data.get("mode") == "ADMIN_SELECT_USER":
    
        user_id = msg.strip()
        user = get_user(user_id)

        if not user:
            await update.message.reply_text("❌ User tidak ditemukan.")
            return

        context.user_data["target_user"] = user_id
        context.user_data["mode"] = "ADMIN_SET_STATUS"

        keyboard = ReplyKeyboardMarkup(
            [["AKTIF","NONAKTIF","PENDING"],
            ["🔙 KEMBALI"]],
            resize_keyboard=True
        )

        await update.message.reply_text(
            f"Pilih status baru untuk {user['nama']}:",
            reply_markup=keyboard
        )
        return
    
    if context.user_data.get("mode") == "ADMIN_SET_STATUS":
    
        if msg not in ["AKTIF","NONAKTIF","PENDING"]:
            await update.message.reply_text("❌ Pilih dari tombol.")
            return

        target_id = context.user_data["target_user"]

        if update_status(target_id, msg):
            await update.message.reply_text(
                f"✅ Status berhasil diubah menjadi {msg}.",
                reply_markup=admin_menu()
            )
        else:
            await update.message.reply_text("❌ Gagal update.")

        context.user_data.clear()
        return
        


