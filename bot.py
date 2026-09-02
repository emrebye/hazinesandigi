import asyncio
import json
import os
import requests
import websockets
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

# ============================================================
# DUMMY SERVER
# ============================================================

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Jimin Bot Active!")

    def log_message(self, format, *args):
        pass

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()

# ============================================================
# AYARLAR & UPSTASH REDIS ENTEGRASYONU
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv(
    "BOT_TOKEN",
    "8910200072:AAHKi4G2GkhWupvBIfx2KoCruKrmMcTEbYw"
)

CHAT_ID = os.getenv(
    "CHAT_ID",
    "-1004325133382"
)

PROXY_URL = (
    "https://dichvu321.com/"
    "proxy.php?stream=all&live=4000"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 10; Mobile) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120.0.0.0 Mobile Safari/537.36"
    ),
    "Origin": "https://dichvu321.com",
    "Referer": "https://dichvu321.com/"
}

# Upstash REST Anahtarları
UPSTASH_URL = "https://exotic-javelin-180919.upstash.io"
UPSTASH_TOKEN = "gQAAAAAAAsK3AAIgcDFmZGQ3Njk5NjBhODQ0MmY3YTIyNThiZTMzYTU4N2M5Yg"
CACHE_TIMEOUT = 1800  # 30 dakika kilit süresi

http_session = requests.Session()
LOCAL_CACHE = set()

# ============================================================
# ORTAK KİLİT MEKANİZMASI (DİĞER BOTUN ATTIĞINI ENGELLEME)
# ============================================================

def is_already_taken_by_other_bot(clean_username):
    """
    Diğer bot bu yayıncıyı Upstash'e kilitlediyse True döner.
    Bu bot o yayıncıyı atmaz, es geçer.
    """
    if clean_username in LOCAL_CACHE:
        return True

    cache_key = f"hazine:{clean_username}"
    headers = {"Authorization": f"Bearer {UPSTASH_TOKEN}"}

    try:
        url = f"{UPSTASH_URL}/set/{cache_key}/1/NX/EX/{CACHE_TIMEOUT}"
        response = http_session.get(url, headers=headers, timeout=2)

        if response.ok:
            result = response.json().get("result")
            if result == "OK":
                # KİLİDİ BİZ ALDIK -> Mesajı bu bot atacak
                LOCAL_CACHE.add(clean_username)
                return False

        # Zaten diğer bot kilitledi ('null' döndü) -> MESAJI ATMA
        return True
    except Exception as e:
        print(f"⚠️ Upstash bağlantı hatası: {e}")
        return True

# ============================================================
# TELEGRAM
# ============================================================

async def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "disable_web_page_preview": True
    }
    try:
        await asyncio.to_thread(
            http_session.post, url, json=payload, timeout=5
        )
    except Exception as e:
        print(f"⚠️ Telegram hatası: {e}")

# ============================================================
# SAYIYA ÇEVİR
# ============================================================

def to_int(value):
    try:
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        number = int(value)
        if 0 <= number <= 10000:
            return number
    except Exception:
        pass
    return None

# ============================================================
# İÇ İÇE KEY ARAMA
# ============================================================

def recursive_find_key(obj, wanted_keys, path=""):
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_normalized = (
                str(key)
                .lower()
                .replace("_", "")
                .replace("-", "")
            )
            current_path = (
                f"{path}.{key}" if path else str(key)
            )
            if key_normalized in wanted_keys:
                number = to_int(value)
                if number is not None:
                    return number, current_path
            result = recursive_find_key(
                value, wanted_keys, current_path
            )
            if result[0] is not None:
                return result
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            result = recursive_find_key(
                item, wanted_keys, f"{path}[{index}]"
            )
            if result[0] is not None:
                return result
    return None, None

# ============================================================
# HAZİNE KİŞİ SAYISI
# ============================================================

def get_chest_recipients(payload):
    key_groups = [
        ["canopen"],
        ["peoplecount"],
        ["participantcount"],
        ["winnercount"],
        ["claimcount"],
        ["recipientcount"],
        ["grabcount"],
        ["membercount"],
        ["people"],
        ["participants"],
        ["winners"],
        ["recipients"]
    ]
    for wanted_keys in key_groups:
        value, path = recursive_find_key(
            payload, wanted_keys
        )
        if value is not None:
            print(
                f"🎯 KİŞİ SAYISI BULUNDU: "
                f"{value} | KEY: {path}"
            )
            return value, path
    return None, None

# ============================================================
# PAYLOAD İÇİNDEKİ İLGİLİ KEY'LERİ GÖSTER
# ============================================================

def debug_relevant_keys(obj, path=""):
    if isinstance(obj, dict):
        for key, value in obj.items():
            current_path = (
                f"{path}.{key}" if path else str(key)
            )
            key_lower = str(key).lower()
            if any(word in key_lower for word in [
                "open", "people", "participant", "winner", "claim", "recipient", "grab", "envelope", "business", "diamond", "coin"
            ]):
                print(f"🔎 {current_path} = {value}")
            debug_relevant_keys(value, current_path)
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            debug_relevant_keys(item, f"{path}[{index}]")

# ============================================================
# CANLI AKIŞ
# ============================================================

async def listen_live_feed():
    print("=" * 60)
    print("🚀 TREASURE ALERT BAŞLADI")
    print("🎁 HAZİNE SANDIĞI TAKİBİ AKTİF")
    print("☁️ UPSTASH PAYLAŞIMLI KİLİT AKTİF")
    print("=" * 60)
    
    while True:
        try:
            print("🔄 Proxy bağlantısı alınıyor...")
            res = await asyncio.to_thread(
                http_session.get, PROXY_URL, headers=HEADERS, timeout=8
            )
            data = res.json()
            if not data.get("success"):
                print("⚠️ Proxy success=false")
                await asyncio.sleep(2)
                continue
            
            path = data.get("path")
            if not path:
                print("⚠️ Proxy path vermedi.")
                await asyncio.sleep(2)
                continue
                
            ws_url = f"wss://dichvu321.com{path}"
            print("🔌 WebSocket bağlanıyor...")
            
            async with websockets.connect(
                ws_url, additional_headers=HEADERS, ping_interval=20, ping_timeout=10
            ) as websocket:
                print("✅ WebSocket bağlandı.")
                async for message in websocket:
                    try:
                        event_data = json.loads(message)
                    except Exception:
                        continue
                        
                    if (isinstance(event_data, dict) and isinstance(event_data.get("data"), dict)):
                        payload = event_data["data"]
                    else:
                        payload = event_data
                        
                    if not isinstance(payload, dict):
                        continue
                        
                    if payload.get("status") == "connected":
                        continue
                        
                    envelope_info = payload.get("envelopeInfo") or {}
                    if not isinstance(envelope_info, dict):
                        envelope_info = {}
                    business_type = envelope_info.get("businessType")
                    
                    box_type_raw = str(payload.get("type") or "").lower()
                    source_raw = str(payload.get("source") or "").lower()
                    is_goody = (business_type == 2 or "goody" in box_type_raw or "goody" in source_raw)
                    if is_goody:
                        print("⏭️ Goody Bag atlandı.")
                        continue
                        
                    username = (
                        payload.get("uniqueId") or 
                        payload.get("nickname") or 
                        payload.get("username") or ""
                    )
                    clean_username = str(username).replace("@", "").strip().lower()
                    if not clean_username:
                        continue

                    # ------------------------------------------------------------
                    # BÖLÜŞME KONTROLÜ (Diğer bot attıysa pas geç)
                    # ------------------------------------------------------------
                    taken = await asyncio.to_thread(is_already_taken_by_other_bot, clean_username)
                    if taken:
                        continue
                        
                    coins = (
                        payload.get("coins") or 
                        payload.get("amount") or 
                        payload.get("diamond") or 
                        payload.get("elmas") or 0
                    )
                    try:
                        coins_number = int(coins)
                    except Exception:
                        coins_number = 0
                        
                    if coins_number < 10:
                        continue
                        
                    level = payload.get("level", 0)
                    try:
                        level = int(level)
                    except Exception:
                        level = 0
                        
                    if level > 0:
                        box_title = f"🎁 HAZİNE SANDIĞI (Level {level})"
                    else:
                        box_title = "🎁 HAZİNE SANDIĞI"
                        
                    viewers = (
                        payload.get("viewerCount") or 
                        payload.get("viewers") or 
                        payload.get("userCount") or 
                        envelope_info.get("viewerCount") or 0
                    )
                    
                    recipients, recipients_path = get_chest_recipients(payload)
                    
                    if recipients is None:
                        recipients_text = "BULUNAMADI"
                    else:
                        recipients_text = f"{recipients} KİŞİ"
                        
                    live_link = (
                        payload.get("link") or 
                        payload.get("url") or 
                        f"https://www.tiktok.com/@{clean_username}/live"
                    )
                    
                    mesaj = (
                        f"{box_title}\n"
                        f"👤 YAYINCI: @{clean_username}\n"
                        f"👁️ İZLEYİCİ: {viewers}\n"
                        f"💎 ELMAS: {coins_number}\n"
                        f"📦 DAĞITILAN: {recipients_text}\n"
                        f"🔗 {live_link}"
                    )
                    
                    asyncio.create_task(send_telegram(mesaj))
                    print(
                        f"✅ GÖNDERİLDİ: @{clean_username} | "
                        f"Elmas: {coins_number} | Kişi: {recipients_text}"
                    )
        except Exception as e:
            print(f"⚠️ BAĞLANTI HATASI: {e}")
            await asyncio.sleep(1)

# ============================================================
# BAŞLAT
# ============================================================

if __name__ == "__main__":
    Thread(target=run_dummy_server, daemon=True).start()
    asyncio.run(listen_live_feed())
