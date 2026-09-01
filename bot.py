import asyncio
import json
import os
import time
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

from TikTokLive import TikTokLiveClient
from TikTokLive.events import EnvelopeEvent

# --- 1. RENDER İÇİN PORT SUNUCUSU ---
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"TikTok Treasure AI Bot Active!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

# --- 2. AYARLAR VE ÇEVRE DEĞİŞKENLERİ ---
DISCOVERY_URL = "https://api.tik.tools/api/live/top-channels"
MAX_CONNECTIONS = 10
SCAN_INTERVAL = 30
RETRY_COOLDOWN = 300
CONNECT_TIMEOUT = 25
WATCH_SECONDS = 30

TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("CHAT_ID")
SENIN_TELEGRAM_ID = os.getenv("TELEGRAM_ID", "@Jiminienn")

if SENIN_TELEGRAM_ID and not SENIN_TELEGRAM_ID.startswith("@"):
    SENIN_TELEGRAM_ID = f"@{SENIN_TELEGRAM_ID}"

active = set()
scheduled = set()
failed_until = {}
seen_envelopes = set()

queue = asyncio.Queue()
room_id_semaphore = asyncio.Semaphore(1)

# --- 3. TİKTOK DATA & ROOM ID ---
def get_live_channels():
    req = urllib.request.Request(DISCOVERY_URL, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        result = []
        for c in data.get("channels", []):
            username = c.get("uniqueId")
            if username:
                result.append({
                    "username": username,
                    "viewers": c.get("viewerCount", 0),
                    "region": c.get("region", ""),
                })
        return result
    except Exception:
        return []

async def get_fresh_room_id(username):
    async with room_id_semaphore:
        for attempt in range(3):
            client = TikTokLiveClient(unique_id=username)
            try:
                room_id = await client.web.fetch_room_id_from_api(username)
                if room_id:
                    return int(room_id)
                raise ValueError("Boş Room ID")
            except Exception:
                if attempt < 2:
                    await asyncio.sleep(1.0 + attempt)
            finally:
                try:
                    await client.web.client.aclose()
                except Exception:
                    pass
    return None

# --- 4. HASSAS AI FİLTRE VE TELEGRAM BİLDİRİMİ ---
async def send_telegram_alert(username, amount, people):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram BOT_TOKEN veya CHAT_ID eksik!")
        return

    if people <= 0:
        return

    kisi_basi = amount / people

    # AZ KİŞİ + YÜKSEK HAZİNE FİLTRESİ
    # 1. Kişi başı düşen elmas 1.5 ve üzeri olmalı OR
    # 2. Dağıtılan kişi sayısı 8 veya daha AZ, toplam elmas 10 ve üzeri olmalı.
    is_rare_opportunity = (kisi_basi >= 1.5) or (people <= 8 and amount >= 10)

    # Kriteri karşılamıyorsa (Örn: Elmas çok ama kişi sayısı aşırı kalabalıksa) ES GEÇ
    if not is_rare_opportunity:
        print(f"⏩ Düşük Değerli / Kalabalık Sandık Atlandı: @{username} (Elmas: {amount}, Kişi: {people})")
        return

    text = (
        f"🤖 **AZ KİŞİLİ BÜYÜK FIRSAT!** {SENIN_TELEGRAM_ID}\n\n"
        f"🎁 **HAZİNE SANDIĞI**\n"
        f"👤 **YAYINCI:** @{username}\n"
        f"💎 **ELMAS:** {amount}\n"
        f"👥 **DAĞITILAN:** {people} KİŞİ\n"
        f"📊 **KİŞİ BAŞI:** {kisi_basi:.1f} Elmas\n\n"
        f"⚡ **Çabuk Katıl:** https://www.tiktok.com/@{username}/live"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False,
    }).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "TreasureAlert/1.0"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            if r.status == 200:
                print(f"🎯 KAZANÇLI SANDIK YAKALANDI VE BİLDİRİLDİ: @{username}")
    except Exception as e:
        print(f"⚠️ Telegram gönderme hatası: {e}")

# --- 5. İZLEME VE DÖNGÜ ---
async def watch(channel, worker_id):
    username = channel["username"]

    try:
        active.add(username)
        room_id = await asyncio.wait_for(get_fresh_room_id(username), timeout=CONNECT_TIMEOUT)
        if not room_id:
            return

        client = TikTokLiveClient(unique_id=username)
        client.parse_error_ignorelist.append("'bytes' object has no attribute 'HashtagNamespace'")

        @client.on(EnvelopeEvent)
        async def on_envelope(event):
            info = event.envelope_info
            if not info or getattr(info, 'business_type', None) != 1:
                return

            amount = info.diamond_count or 0
            people = info.people_count or 0
            envelope_id = info.envelope_id

            if amount <= 0 or (envelope_id and envelope_id in seen_envelopes):
                return

            if envelope_id:
                seen_envelopes.add(envelope_id)

            # Filtreye gönder
            await send_telegram_alert(username, amount, people)

        connect_task = asyncio.create_task(
            client.connect(room_id=room_id, fetch_live_check=False, fetch_room_info=False, fetch_gift_info=False)
        )

        try:
            await asyncio.sleep(WATCH_SECONDS)
        finally:
            try:
                await client._ws.disconnect()
            except Exception:
                pass
            try:
                await connect_task
            except Exception:
                pass

    except Exception:
        failed_until[username] = time.monotonic() + RETRY_COOLDOWN
    finally:
        active.discard(username)
        scheduled.discard(username)

async def worker(worker_id):
    while True:
        channel = await queue.get()
        try:
            await watch(channel, worker_id)
        finally:
            queue.task_done()

async def discovery_loop():
    print("🚀 RENDER TIKTOK AZ KİŞİLİ HAZİNE BOTU BAŞLATILDI")
    for i in range(MAX_CONNECTIONS):
        asyncio.create_task(worker(i + 1))

    while True:
        try:
            channels = get_live_channels()
            now = time.monotonic()
            channels.sort(key=lambda x: x.get("viewers", 0), reverse=True)

            for channel in channels:
                username = channel["username"]
                if username in active or username in scheduled or now < failed_until.get(username, 0):
                    continue
                if (MAX_CONNECTIONS - len(active) - queue.qsize()) <= 0:
                    break

                scheduled.add(username)
                await queue.put(channel)

        except Exception as e:
            print(f"❌ Keşif hatası: {e}")

        await asyncio.sleep(SCAN_INTERVAL)

async def main():
    Thread(target=run_dummy_server, daemon=True).start()
    await discovery_loop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 BOT DURDURULDU")
