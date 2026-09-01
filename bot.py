import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Aktif!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

BOT_TOKEN = os.environ.get("BOT_TOKEN")

async def her_mesaja_cevap_ver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mesaj = update.effective_message
    if mesaj:
        print(f"--> YAKALANAN MESAJ: {mesaj.text}")
        await mesaj.reply_text("🤖 Grubu duyuyorum, sistem aktif!")

if __name__ == '__main__':
    Thread(target=run_dummy_server, daemon=True).start()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Filtresiz: Gruptaki İstisnasız HER ŞEYİ yakalar
    app.add_handler(MessageHandler(filters.ALL, her_mesaja_cevap_ver))
    
    print("Test Botu Başlatıldı...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
