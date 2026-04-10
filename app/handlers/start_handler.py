from telegram import Update
from telegram.ext import ContextTypes
from app.keyboards import admin_menu, main_menu
from app.services.google_services import client
from app.config import USER_MANAGEMENT_ID
from app.handlers.text_handler import check_access, get_user


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = get_user(update.effective_user.id)

    if not user:
        context.user_data.clear()
        context.user_data["mode"] = "REG_NAMA"
        await update.message.reply_text(
            "👋 Anda belum terdaftar.\nMasukkan Nama Lengkap:"
        )
        return

    if user["status"] == "PENDING":
        await update.message.reply_text(
            "⏳ Akun Anda masih menunggu persetujuan admin."
        )
        return

    if user["status"] == "NONAKTIF":
        await update.message.reply_text(
            "🚫 Akun Anda tidak aktif."
        )
        return

    context.user_data.clear()

    if user["role"] == "ADMIN":
        await update.message.reply_text(
            f"👑 Halo Admin {user['nama']}",
            reply_markup=admin_menu()
        )
    else:
        await update.message.reply_text(
            f"👋 Halo {user['nama']}",
            reply_markup=main_menu()
        )