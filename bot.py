import asyncio
import json
import os
import requests
import websockets
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
import re


# ============================================================
# DUMMY HTTP SERVER
# ============================================================

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Jimin Bot Active!")


def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()


# ============================================================
# AYARLAR
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("CHAT_ID")

UPSTASH_URL = os.getenv(
    "UPSTASH_URL",
    "https://exotic-javelin-180919.upstash.io"
)

UPSTASH_TOKEN = os.getenv("UPSTASH_TOKEN")

PROXY_URL = "https://dichvu321.com/proxy.php?stream=box&live=1000"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 10; Mobile) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Mobile Safari/537.36"
    ),
    "Origin": "https://dichvu321.com",
    "Referer": "https://dichvu321.com/"
}

CACHE_TIMEOUT = 1800


# ============================================================
# TELEGRAM
# ============================================================

async def send_telegram_async(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ BOT_TOKEN veya CHAT_ID eksik.")
        return

    url = (
        f"https://api.telegram.org/bot"
        f"{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    def _send():
        try:
            requests.post(
                url,
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": text,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": False
                },
                timeout=5
            )
        except Exception as e:
            print(f"❌ Telegram hatası: {e}")

    await asyncio.to_thread(_send)


# ============================================================
# UPSTASH CACHE
# ============================================================

def check_and_save_cache(cache_key):

    if not UPSTASH_TOKEN:
        return False

    headers = {
        "Authorization": f"Bearer {UPSTASH_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        payload = [
            "SET",
            cache_key,
            "1",
            "EX",
            str(CACHE_TIMEOUT),
            "NX"
        ]

        res = requests.post(
            UPSTASH_URL,
            headers=headers,
            json=payload,
            timeout=3
        )

        data = res.json()

        if data.get("result") == "OK":
            return False

        return True

    except Exception as e:
        print(f"⚠️ Cache hatası: {e}")
        return False


# ============================================================
# HAM JSON İÇİN TÜM KEY YOLLARINI GÖSTER
# ============================================================

def dump_all_keys(data, path=""):
    """
    Gelen JSON'un bütün key yollarını terminale çıkarır.
    Gerçek kişi sayısının hangi alanda olduğunu bulmak için kullanılır.
    """

    if isinstance(data, dict):

        for key, value in data.items():

            current = (
                f"{path}.{key}"
                if path
                else str(key)
            )

            if isinstance(value, (int, float, str, bool)) or value is None:
                print(f"🔎 {current} = {value}")
            else:
                print(f"📂 {current}")

            dump_all_keys(value, current)

    elif isinstance(data, list):

        for index, item in enumerate(data):
            dump_all_keys(
                item,
                f"{path}[{index}]"
            )


# ============================================================
# HAZİNEYE AİT OLASI KEY'LERİ BUL
# ============================================================

def find_possible_chest_people(data):

    candidates = []

    target_words = [
        "usercount",
        "user_count",
        "peoplecount",
        "people_count",
        "participant",
        "participant_count",
        "participantcount",
        "winner",
        "winner_count",
        "winnercount",
        "grab",
        "grab_count",
        "grabcount",
        "claim",
        "claim_count",
        "claimcount",
        "member",
        "member_count",
        "membercount",
        "recipient",
        "recipient_count",
        "recipientcount",
        "receive",
        "receiver",
        "person",
        "persons",
        "people",
        "kisi",
        "kişi",
        "num"
    ]

    skip_words = [
        "viewer",
        "viewers",
        "room",
        "online",
        "total",
        "coin",
        "amount",
        "diamond",
        "elmas",
        "username",
        "uniqueid",
        "nickname",
        "link",
        "url",
        "avatar"
    ]

    def recursive_search(obj, path=""):

        if isinstance(obj, dict):

            for key, value in obj.items():

                key_string = str(key)
                key_lower = key_string.lower()

                current_path = (
                    f"{path}.{key_string}"
                    if path
                    else key_string
                )

                # Önce kesinlikle istemediğimiz alanlar
                if any(
                    skip in key_lower
                    for skip in skip_words
                ):
                    recursive_search(value, current_path)
                    continue

                # Olası kişi sayısı alanları
                if any(
                    target in key_lower
                    for target in target_words
                ):

                    if isinstance(value, (int, float)):

                        value_int = int(value)

                        if 1 <= value_int <= 500:
                            candidates.append({
                                "path": current_path,
                                "key": key_string,
                                "value": value_int
                            })

                    elif isinstance(value, str):

                        try:
                            value_int = int(value)

                            if 1 <= value_int <= 500:
                                candidates.append({
                                    "path": current_path,
                                    "key": key_string,
                                    "value": value_int
                                })

                        except:
                            pass

                recursive_search(
                    value,
                    current_path
                )

        elif isinstance(obj, list):

            for index, item in enumerate(obj):

                recursive_search(
                    item,
                    f"{path}[{index}]"
                )

    recursive_search(data)

    return candidates


# ============================================================
# EN MANTIKLI ADAYI SEÇ
# ============================================================

def get_chest_people(data):

    candidates = find_possible_chest_people(data)

    if not candidates:
        return None, []

    # Öncelik sırası
    priority = [
        "people_count",
        "peoplecount",
        "user_count",
        "usercount",
        "participant_count",
        "participantcount",
        "winner_count",
        "winnercount",
        "claim_count",
        "claimcount",
        "grab_count",
        "grabcount",
        "member_count",
        "membercount",
        "recipient_count",
        "recipientcount",
        "people",
        "persons",
        "person",
        "kisi",
        "kişi"
    ]

    def score(item):

        key = item["key"].lower().replace("-", "_")

        try:
            index = priority.index(key)
            return index
        except ValueError:
            return 999

    candidates.sort(key=score)

    selected = candidates[0]

    return selected["value"], candidates


# ============================================================
# WEBSOCKET DİNLE
# ============================================================

async def listen_live_feed():

    print("🚀 RECURSIVE HAZİNE TARAMA AKTİF")
    print("🔍 Gerçek kişi sayısı alanı aranıyor...")

    while True:

        try:

            # ------------------------------------------------
            # PROXY'DEN WS PATH AL
            # ------------------------------------------------

            res = await asyncio.to_thread(
                requests.get,
                PROXY_URL,
                headers=HEADERS,
                timeout=5
            )

            data = res.json()

            if not data.get("success"):
                await asyncio.sleep(2)
                continue

            path = data.get("path")

            if not path:
                print("⚠️ Proxy path vermedi.")
                await asyncio.sleep(2)
                continue

            ws_url = f"wss://dichvu321.com{path}"

            print(f"🔌 WebSocket bağlanıyor: {ws_url}")

            # ------------------------------------------------
            # WEBSOCKET
            # ------------------------------------------------

            async with websockets.connect(
                ws_url,
                additional_headers=HEADERS,
                ping_interval=None
            ) as websocket:

                print("✅ WebSocket bağlandı.")

                async for message in websocket:

                    try:
                        event_data = json.loads(message)
                    except:
                        continue

                    # ------------------------------------------------
                    # PAYLOAD BİRLEŞTİR
                    # ------------------------------------------------

                    payload = event_data.copy()

                    if (
                        "data" in event_data
                        and isinstance(event_data["data"], dict)
                    ):
                        payload.update(
                            event_data["data"]
                        )

                    if (
                        "payload" in event_data
                        and isinstance(event_data["payload"], dict)
                    ):
                        payload.update(
                            event_data["payload"]
                        )

                    # ------------------------------------------------
                    # USERNAME
                    # ------------------------------------------------

                    username = (
                        payload.get("uniqueId")
                        or payload.get("nickname")
                        or payload.get("username")
                        or payload.get("streamer")
                    )

                    if not username:
                        continue

                    clean_username = (
                        str(username)
                        .replace("@", "")
                        .strip()
                    )

                    if not clean_username:
                        continue

                    # ------------------------------------------------
                    # ELİMAS
                    # ------------------------------------------------

                    coins_raw = (
                        payload.get("coins")
                        or payload.get("amount")
                        or payload.get("elmas")
                        or payload.get("diamond")
                        or 0
                    )

                    try:
                        amount = float(coins_raw)
                    except:
                        amount = 0

                    if amount < 10:
                        continue

                    # ------------------------------------------------
                    # CACHE
                    # ------------------------------------------------

                    cache_key = re.sub(
                        r"[^a-z0-9]",
                        "",
                        clean_username.lower()
                    )

                    if await asyncio.to_thread(
                        check_and_save_cache,
                        cache_key
                    ):
                        continue

                    # ------------------------------------------------
                    # İZLEYİCİ
                    # ------------------------------------------------

                    room_viewers = (
                        payload.get("viewerCount")
                        or payload.get("viewers")
                        or payload.get("totalUserCount")
                        or 0
                    )

                    # ------------------------------------------------
                    # GERÇEK HAZİNE KİŞİ SAYISINI ARA
                    # ------------------------------------------------

                    chest_people, candidates = (
                        get_chest_people(payload)
                    )

                    # ------------------------------------------------
                    # ADAYLARI TERMİNALE YAZ
                    # ------------------------------------------------

                    print("\n" + "=" * 70)
                    print("🎁 OLASI HAZİNE MESAJI")
                    print(f"👤 Yayıncı: @{clean_username}")
                    print(f"💎 Elmas: {amount}")

                    if candidates:

                        print("\n🔎 BULUNAN KİŞİ SAYISI ADAYLARI:")

                        for candidate in candidates:

                            print(
                                f"   ➜ {candidate['path']} "
                                f"= {candidate['value']}"
                            )

                    else:

                        print(
                            "⚠️ Kişi sayısı için uygun alan bulunamadı."
                        )

                    print("\n📦 HAM JSON:")

                    print(
                        json.dumps(
                            payload,
                            ensure_ascii=False,
                            indent=2
                        )
                    )

                    print("=" * 70 + "\n")

                    # ------------------------------------------------
                    # LİNK
                    # ------------------------------------------------

                    live_link = (
                        payload.get("link")
                        or payload.get("url")
                        or (
                            "https://www.tiktok.com/"
                            f"@{clean_username}/live"
                        )
                    )

                    # ------------------------------------------------
                    # KİŞİ SAYISI YOKSA YANLIŞ 15 GÖNDERME
                    # ------------------------------------------------

                    if chest_people is None:

                        people_text = "BULUNAMADI"

                    else:

                        people_text = (
                            f"{chest_people} KİŞİ"
                        )

                    # ------------------------------------------------
                    # TELEGRAM MESAJI
                    # ------------------------------------------------

                    mesaj = (
                        "🎁 **HAZİNE SANDIĞI**\n"
                        f"👤 **YAYINCI:** "
                        f"`@{clean_username}`\n"
                        f"👁️ **İZLEYİCİ:** "
                        f"{room_viewers}\n"
                        f"💎 **ELMAS:** "
                        f"{int(amount)}\n"
                        f"📦 **DAĞITILAN:** "
                        f"{people_text}\n"
                        f"🔗 {live_link}"
                    )

                    asyncio.create_task(
                        send_telegram_async(mesaj)
                    )

                    print(
                        f"✅ GÖNDERİLDİ: "
                        f"@{clean_username} | "
                        f"Kişi: {people_text}"
                    )

        except Exception as e:

            print(
                f"⚠️ WebSocket/Proxy hatası: {e}"
            )

            await asyncio.sleep(2)


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    Thread(
        target=run_dummy_server,
        daemon=True
    ).start()

    asyncio.run(
        listen_live_feed()
    )
