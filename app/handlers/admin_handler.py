from telegram import Update
from telegram.ext import ContextTypes
from app.handlers.text_handler import (
    check_access,
    get_user,
    update_status,
    dashboard_cache,
    get_gamas_dashboard
)
from app.services.google_services import client
from app.config import USER_MANAGEMENT_ID


user_sheet = client.open_by_key(USER_MANAGEMENT_ID).worksheet("USERS")


# ================= LIST USER =================
async def listuser(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if check_access(update) != "ADMIN":
        await update.message.reply_text("❌ Akses ditolak")
        return

    users = user_sheet.get_all_values()
    text = "📋 DAFTAR USER:\n\n"

    for i in range(1, len(users)):
        text += f"{users[i][1]} - {users[i][2]} - {users[i][5]}\n"

    await update.message.reply_text(text)


# ================= APPROVE USER =================
async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if check_access(update) != "ADMIN":
        await update.message.reply_text("❌ Akses ditolak")
        return

    if not context.args:
        await update.message.reply_text("Gunakan: /approve TELEGRAM_ID")
        return

    if update_status(context.args[0], "AKTIF"):
        await update.message.reply_text("✅ User diaktifkan")
    else:
        await update.message.reply_text("❌ User tidak ditemukan")


