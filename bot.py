            logging.info("Taramaya başlandı...")
            dongu_sayaci = 0
            
            while True:
                await scrape_dom_cards(page)
                await asyncio.sleep(2)
                
                # Her 2 saniyede bir sayar. 150'ye ulaşınca (yaklaşık 5 dakika) sayfayı tazeler.
                dongu_sayaci += 1
                if dongu_sayaci >= 150:
                    logging.info("♻️ Oturum süresi doldu, sayfa yenileniyor (Demo engeli aşıldı)...")
                    try:
                        await page.reload(wait_until="domcontentloaded", timeout=60000)
                    except Exception as e:
                        logging.warning(f"Sayfa yenilenirken gecikme oldu: {e}")
                    dongu_sayaci = 0 # Sayacı sıfırla ve yeniden taramaya başla
