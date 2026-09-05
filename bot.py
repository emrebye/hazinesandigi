async def init_session_and_get_ticket():
    main_url = "https://dichvu321.com/en/tiktok-treasure-box-bot/"
    proxy_url = "https://dichvu321.com/proxy.php?transport=ws&mode=bootstrap&stream=box&live=1000"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Referer": main_url,
        "Origin": "https://dichvu321.com",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
    }
    
    post_payload = {
        "demo": "true",
        "mode": "bootstrap",
        "stream": "box"
    }

    try:
        logging.info("1️⃣ Ana sayfaya gidiliyor...")
        await asyncio.to_thread(scraper.get, main_url, headers=headers, timeout=15)
        
        logging.info("2️⃣ proxy.php'den bilet isteniyor (POST + demo payload)...")
        r2 = await asyncio.to_thread(scraper.post, proxy_url, data=post_payload, headers=headers, timeout=15)
        logging.info(f"2️⃣ Bilet yanıt kodu: {r2.status_code}")
        logging.info(f"2️⃣ Bilet ham yanıtı: {r2.text[:150]}")
        
        data = r2.json()
        if data.get("success") and data.get("path"):
            return f"wss://dichvu321.com{data.get('path')}"
        else:
            logging.warning(f"⚠️ Bilet reddedildi: {data}")
    except Exception as e:
        logging.error(f"❌ Oturum hatası: {e}")
    return None
