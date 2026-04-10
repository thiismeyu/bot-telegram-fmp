from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from app.config import TOKEN
from app.handlers.start_handler import start
from app.handlers.text_handler import text, load_ticket_cache
from app.handlers.photo_handler import photo
from app.handlers.admin_handler import listuser, approve
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import os


# ================= HEALTH SERVER UNTUK RAILWAY =================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")


def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()


def main():

    print("Loading ticket cache...")
    load_ticket_cache()

    # Health server Railway
    threading.Thread(target=run_health_server, daemon=True).start()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("listuser", listuser))
    app.add_handler(CommandHandler("approve", approve))
   

    app.add_handler(MessageHandler(filters.TEXT, text))
    app.add_handler(MessageHandler(filters.PHOTO, photo))

    print("BOT GAMAS PRO VERSION RUNNING...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()