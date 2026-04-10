from telegram import Update
from telegram.ext import ContextTypes
import io
import uuid
from datetime import datetime
from googleapiclient.http import MediaIoBaseUpload

from app.keyboards import foto_menu
from app.utils import compress, safe_label
from app.services.google_services import drive
from app.handlers.text_handler import (
    find_ticket_global,
    get_year_folder_foto,   
    get_folder,
    find_empty_foto_col,
    find_label_column, 
    foto_list,
    get_formula_cell,
    delete_drive_file_from_cell
)

# ================= PHOTO HANDLER =================
async def photo(update:Update,context:ContextTypes.DEFAULT_TYPE):

    file=await update.message.photo[-1].get_file()
    bio=io.BytesIO()
    await file.download_to_memory(out=bio)

    # ===== EDIT FOTO =====
    if context.user_data.get("mode")=="WAIT_EDIT_FOTO":

        if "INC" not in context.user_data:
            await update.message.reply_text(
                "❌ Sesi tidak valid. Silakan mulai ulang Upload Foto."
            )
            return

        ws, row, year = find_ticket_global(context.user_data["INC"])

        if not ws:
            await update.message.reply_text("❌ Data tiket tidak ditemukan.")
            return

        year_id = get_year_folder_foto(year)
        inc_id = get_folder(context.user_data["INC"], year_id)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = f"{context.user_data['INC']}_{context.user_data['label']}_{timestamp}_{uuid.uuid4().hex[:6]}.jpg"

        media = MediaIoBaseUpload(
            io.BytesIO(compress(bio.getvalue())),
            mimetype="image/jpeg"
        )

        try:
            r = drive.files().create(
                body={"name": name, "parents": [inc_id]},
                media_body=media,
                fields="id"
            ).execute()
        except Exception:
            await update.message.reply_text("❌ Upload gagal. Coba lagi.")
            return

        link = f"https://drive.google.com/file/d/{r['id']}/view"

        col = context.user_data["edit_foto_col"]
        line = context.user_data["edit_foto_line"]

        cell = get_formula_cell(ws, row, col) or ""

        lines = cell.split("\n")

        # hapus file lama
        if line < len(lines):
            delete_drive_file_from_cell(lines[line])
        else:
            await update.message.reply_text("❌ Data foto tidak valid.")
            return

        # ganti dengan foto baru
        formula = f'=HYPERLINK("{link}";"{context.user_data["label"]}")'
        lines[line] = formula

        ws.update_cell(row, col, "\n".join(lines))

        context.user_data["mode"] = "WAIT_FOTO"

        await update.message.reply_text("✅ Foto berhasil diperbarui.")

        # reload daftar foto terbaru
        ws, row, year = find_ticket_global(context.user_data["INC"])
        fotos = foto_list(ws, row)

        text = "📸 FOTO SAAT INI:\n\n"

        if not fotos:
            text += "Belum ada foto.\n"
        else:
            for i, (col, label) in enumerate(fotos, 1):
                text += f"{i}. {label}   /edit{i} /hapus{i}\n"

        await update.message.reply_text(
            text,
            reply_markup=foto_menu()
        )

        return


    # ===== TAMBAH FOTO =====
    if context.user_data.get("mode")!="WAIT_FOTO":
        await update.message.reply_text("Masukkan nomor tiket terlebih dahulu.")
        return
    if "INC" not in context.user_data:
        await update.message.reply_text(
        "❌ Sesi upload tidak valid. Silakan mulai ulang."
        )
        return

    ws,row,year = find_ticket_global(context.user_data["INC"])

    if not ws:
        await update.message.reply_text("❌ Nomor tiket tidak ditemukan.")
        return

    year_id=get_year_folder_foto(year)
    inc_id=get_folder(context.user_data["INC"],year_id)

    timestamp=datetime.now().strftime("%Y%m%d_%H%M%S")
    name=f"{context.user_data['INC']}_{context.user_data['label']}_{timestamp}_{uuid.uuid4().hex[:6]}.jpg"

    media=MediaIoBaseUpload(io.BytesIO(compress(bio.getvalue())),mimetype="image/jpeg")

    try:
        r = drive.files().create(
            body={"name":name,"parents":[inc_id]},
            media_body=media,
            fields="id"
        ).execute()
    except Exception:
        await update.message.reply_text("❌ Upload gagal. Coba lagi.")
        return

    link = f"https://drive.google.com/file/d/{r['id']}/view"

    label = context.user_data["label"]

    # cek apakah label sudah ada di kolom
    col = find_label_column(ws, row, label)

    # jika belum ada, buat kolom baru
    if not col:
        col = find_empty_foto_col(ws, row)

    # ambil isi lama cell
    old = get_formula_cell(ws, row, col) or ""

    new_link = f'=HYPERLINK("{link}";"{label}")'

    # jika sudah ada foto dengan label sama → tambahkan di bawahnya
    if old.strip():
        formula = old + "\n" + new_link
    else:
        formula = new_link

    ws.update_cell(row, col, formula)

    context.user_data["mode"]="WAIT_FOTO"

    fotos=foto_list(ws,row)
    text="📸 Foto Saat Ini:\n"

    for i,(c,label) in enumerate(fotos,1):
        text+=f"{i}. {label}  /edit{i} /hapus{i}\n"

    await update.message.reply_text(text,reply_markup=foto_menu())