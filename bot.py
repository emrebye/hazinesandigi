import os
import re
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
SENIN_TELEGRAM_ID = os.environ.get("TELEGRAM_ID", "")

# Kullanıcı adının başında @ yoksa otomatik ekle
if SENIN_TELEGRAM_ID and not SENIN_TELEGRAM_ID.startswith("@"):
    SENIN_TELEGRAM_ID = f"@{SENIN_TELEGRAM_ID}"

async def ai_mesaj_analiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Kanal gönderileri veya normal grup mesajlarını yakala
    mesaj_obj = update.effective_message
    if not mesaj_obj or not mesaj_obj.text:
        return

    mesaj = mesaj_obj.text

    # Hazine sandığı kontrolü
    if "HAZİNE SANDIĞI" in mesaj.upper():
        elmas_match = re.search(r'ELMAS:\s*(\d+)', mesaj, re.IGNORECASE)
        kisi_match = re.search(r'DAĞITILAN:\s*(\d+)\s*KİŞİ', mesaj, re.IGNORECASE)

        if elmas_match and kisi_match:
            elmas = int(elmas_match.group(1))
            kisi = int(kisi_match.group(1))

            if kisi > 0:
                kisi_basi_deger = elmas / kisi

                # Fırsat kriteri
                is_rare_opportunity = (kisi_basi_deger >= 1.5) or (kisi <= 8 and elmas >= 10)

                if is_rare_opportunity:
                    uyari_metni = (
                        f"🤖 **AI FIRSAT ALGILADI!** {SENIN_TELEGRAM_ID}\n"
                        f"💎 **Elmas:** {elmas} | 📦 **Dağıtılan:** {kisi} Kişi\n"
                        f"📊 **Kişi Başı:** {kisi_basi_deger:.1f} Elmas\n"
                        f"⚡ **Çabuk Katıl!**"
                    )
                    await mesaj_obj.reply_text(uyari_metni, parse_mode="Markdown")

if __name__ == '__main__':
    Thread(target=run_dummy_server, daemon=True).start()
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Hem normal grup mesajlarını hem de kanaldan gelen iletileri dinle
    app.add_handler(MessageHandler(filters.ALL, ai_mesaj_analiz))
    
    print("AI Akıllı Filtre Botu Aktif...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
