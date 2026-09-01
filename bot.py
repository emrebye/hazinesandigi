import os
import re
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# Render'ın port hatası vermemesi için sahte web sunucusu
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Aktif!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

# Render ortam değişkenlerini al
BOT_TOKEN = os.environ.get("BOT_TOKEN")
SENIN_TELEGRAM_ID = os.environ.get("TELEGRAM_ID")

async def ai_mesaj_analiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    mesaj = update.message.text

    if "HAZİNE SANDIĞI" in mesaj:
        elmas_match = re.search(r'ELMAS:\s*(\d+)', mesaj, re.IGNORECASE)
        kisi_match = re.search(r'DAĞITILAN:\s*(\d+)\s*KİŞİ', mesaj, re.IGNORECASE)

        if elmas_match and kisi_match:
            elmas = int(elmas_match.group(1))
            kisi = int(kisi_match.group(1))

            if kisi > 0:
                kisi_basi_deger = elmas / kisi

                # Kişi başı değer yüksekse veya toplam kişi azsa alarm ver
                is_rare_opportunity = (kisi_basi_deger >= 1.5) or (kisi <= 8 and elmas >= 10)

                if is_rare_opportunity:
                    uyari_metni = (
                        f"🤖 **AI FIRSAT ALGILADI!** {SENIN_TELEGRAM_ID}\n"
                        f"💎 **Elmas:** {elmas} | 📦 **Dağıtılan:** {kisi} Kişi\n"
                        f"📊 **Yapay Zeka Skoru:** Yüksek Kazanma Şansı!\n"
                        f"⚡ **Çabuk Katıl!**"
                    )
                    await update.message.reply_text(uyari_metni, parse_mode="Markdown")

if __name__ == '__main__':
    # Sahte sunucuyu arka planda başlat
    Thread(target=run_dummy_server, daemon=True).start()
    
    # Telegram Botunu Başlat
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), ai_mesaj_analiz))
    print("AI Akıllı Filtre Botu Aktif...")
    app.run_polling()
