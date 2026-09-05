import asyncio
import os
import requests
from playwright.async_api import async_playwright

# ==================== KULLANICI AYARLARI ====================
# Takip etmek istediğin sitenin tam adresi (https:// ile başlasın)
SİTE_URL = "https://example.com/live" 

# Telegram Bot Token ve Chat ID bilgilerin (Render Environment Variable olarak da alabilir)
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "BOT_TOKENINIZI_BURAYA_YAZIN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "CHAT_IDNIZI_BURAYA_YAZIN")
# ============================================================

def telegram_bildirim_gonder(mesaj):
    """Telegram grubuna/kanalına bildirim gönderir."""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": mesaj,
            "parse_mode": "HTML"
        }
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram mesajı gönderilirken hata oluştu: {e}")

async def run():
    async with async_playwright() as p:
        print("Playwright Bot Başlatıldı! Canlı ve sayfa verileri izleniyor...")
        telegram_bildirim_gonder("🤖 <b>Playwright Bot Başlatıldı!</b>\nCanlı ve sayfa verileri izleniyor...")

        # Bot engeline takılmamak için standart Chrome User-Agent ekliyoruz
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 720}
        )
        
        page = await context.new_page()

        try:
            # Geçerli URL adresine gidiyoruz
            await page.goto(SİTE_URL, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"Siteye bağlanırken hata oluştu: {e}")
            telegram_bildirim_gonder(f"⚠️ Siteye bağlanılamadı: {e}")
            await browser.close()
            return

        son_bildirim_durumu = False

        while True:
            try:
                # Sitedeki tüm yazıyı dinamik olarak çeker (HTML sınıf adı değişse bile metni yakalar)
                body_text = await page.inner_text("body")
                body_text_upper = body_text.upper()

                # Sandık veya Hazine kelimesi sayfada geçiyor mu kontrol et
                sandik_var_mi = "HAZİNE SANDIĞI" in body_text_upper or "TREASURE BOX" in body_text_upper

                if sandik_var_mi and not son_bildirim_durumu:
                    mesaj = "🎁 <b>HAZİNE SANDIĞI YAKALANDI!</b>\n\nSayfada yeni bir sandık/etkinlik tespit edildi."
                    print("Sandık tespit edildi, Telegram'a gönderiliyor...")
                    telegram_bildirim_gonder(mesaj)
                    son_bildirim_durumu = True

                elif not sandik_var_mi and son_bildirim_durumu:
                    # Sandık ekrandan kaybolduysa durumu sıfırla
                    son_bildirim_durumu = False

                # Sayfadaki dynamic içeriğin güncellenmesi için 5 saniye bekle
                await asyncio.sleep(5)

            except Exception as e:
                print(f"Döngü içerisinde hata: {e}")
                await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(run())
