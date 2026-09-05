import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        # Bot tespitini önlemek için standart kullanıcı kimliği (User-Agent) ekliyoruz
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # Siteye git
        await page.goto("SİTE_URL_ADRESİ", wait_until="networkidle")

        print("Playwright Bot Başlatıldı! Canlı ve sayfa verileri izleniyor...")

        while True:
            try:
                # Sayfadaki tüm yazıları dinamik olarak çek (KOD DEĞİŞSE BİLE YAZIYI BULUR)
                body_text = await page.inner_text("body")

                # Eğer ekranda 'HAZİNE SANDIĞI' veya 'TREASURE BOX' geçiyorsa
                if "HAZİNE SANDIĞI" in body_text or "TREASURE BOX" in body_text:
                    # Burada metinden elmas/izleyici verisini yakalayıp Telegram'a atacak fonksiyonunu çalıştır
                    print("Sandık algılandı! Telegram'a bildirim gönderiliyor...")
                
                await asyncio.sleep(5) # 5 saniyede bir kontrol et

            except Exception as e:
                print(f"Hata oluştu: {e}")
                await asyncio.sleep(5)

asyncio.run(run())
