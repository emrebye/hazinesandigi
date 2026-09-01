import os
import re
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# Render'daki Environment Variables alanından verileri çeker
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
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), ai_mesaj_analiz))
    print("AI Akıllı Filtre Botu Aktif...")
    app.run_polling()
