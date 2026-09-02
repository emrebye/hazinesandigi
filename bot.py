import asyncio
import json
import os
import threading
import requests
import websockets

from http.server import BaseHTTPRequestHandler, HTTPServer


# ============================================================
# RENDER HEALTH SERVER
# ============================================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass


def start_health_server():

    try:
        port = int(
            os.environ.get("PORT", "10000")
        )

        server = HTTPServer(
            ("0.0.0.0", port),
            HealthHandler
        )

        print(
            f"🌐 Render HTTP server aktif: "
            f"0.0.0.0:{port}"
        )

        server.serve_forever()

    except Exception as e:

        print(
            f"❌ HTTP server hatası: {e}"
        )


# ============================================================
# TELEGRAM
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv(
    "BOT_TOKEN",
    ""
)

CHAT_ID = os.getenv(
    "CHAT_ID",
    "-1004325133382"
)


# ============================================================
# PROXY
# ============================================================

PROXY_URL = (
    "https://dichvu321.com/"
    "proxy.php?stream=all&live=4000"
)


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 10; Mobile) "
        "AppleWebKit/537.36"
    ),
    "Origin": "https://dichvu321.com",
    "Referer": "https://dichvu321.com/"
}


# ============================================================
# ETİKET AYARLARI
# ============================================================

TAG_USERNAME = "@jiminienn"

TAG_COINS_MIN = 100

TAG_RECIPIENTS_MAX = 5


# ============================================================
# UPSTASH
# ============================================================

UPSTASH_URL = os.getenv(
    "UPSTASH_URL",
    "https://exotic-javelin-180919.upstash.io"
)

UPSTASH_TOKEN = os.getenv(
    "UPSTASH_TOKEN",
    ""
)

CACHE_TIMEOUT = 1800


def check_and_save_cache(cache_key):

    if not UPSTASH_TOKEN:
        return False

    headers = {
        "Authorization":
            f"Bearer {UPSTASH_TOKEN}",

        "Content-Type":
            "application/json"
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

        response = requests.post(
            UPSTASH_URL,
            headers=headers,
            json=payload,
            timeout=3
        )

        response.raise_for_status()

        result = response.json().get(
            "result"
        )

        return result != "OK"

    except Exception as e:

        print(
            f"⚠️ Upstash cache hatası: {e}"
        )

        return False


# ============================================================
# YARDIMCI
# ============================================================

def to_int(value, default=0):

    if value is None:
        return default

    try:

        if isinstance(value, bool):
            return int(value)

        if isinstance(value, int):
            return value

        if isinstance(value, float):
            return int(value)

        text = str(value).strip()

        if not text:
            return default

        return int(float(text))

    except Exception:

        return default


# ============================================================
# RECURSIVE KEY ARAMA
# ============================================================

def recursive_find_key(
    obj,
    wanted_keys
):

    wanted = {
        str(x).lower()
        for x in wanted_keys
    }

    if isinstance(obj, dict):

        for key, value in obj.items():

            if str(key).lower() in wanted:

                number = to_int(
                    value,
                    None
                )

                if number is not None:
                    return number

        for value in obj.values():

            found = recursive_find_key(
                value,
                wanted_keys
            )

            if found is not None:
                return found

    elif isinstance(obj, list):

        for item in obj:

            found = recursive_find_key(
                item,
                wanted_keys
            )

            if found is not None:
                return found

    return None


# ============================================================
# KİŞİ SAYISI
# ============================================================

def get_chest_recipients(
    payload
):

    priority_keys = [

        "canOpen",

        "peopleCount",

        "participantCount",

        "winnerCount",

        "claimCount",

        "recipientCount",

        "grabCount",

        "memberCount"
    ]

    found = recursive_find_key(
        payload,
        priority_keys
    )

    if found is not None:
        return found

    alternative_keys = [

        "people",

        "participants",

        "winners",

        "recipients"
    ]

    found = recursive_find_key(
        payload,
        alternative_keys
    )

    if found is not None:
        return found

    return 0


# ============================================================
# TELEGRAM
# ============================================================

async def send_telegram(
    mesaj
):

    if not TELEGRAM_BOT_TOKEN:

        print(
            "❌ BOT_TOKEN bulunamadı."
        )

        return

    url = (
        "https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    payload = {

        "chat_id": CHAT_ID,

        "text": mesaj,

        "disable_web_page_preview": True
    }

    try:

        await asyncio.to_thread(

            requests.post,

            url,

            json=payload,

            timeout=5
        )

    except Exception as e:

        print(
            f"⚠️ Telegram hatası: {e}"
        )


# ============================================================
# TIKTOK AKIŞI
# ============================================================

async def listen_live_feed():

    print(
        "🚀 HAZİNE BOTU BAŞLADI"
    )

    print(
        "🌐 Render health server hazır"
    )

    print(
        "🎁 Hazine sistemi aktif"
    )

    print(
        "🚫 20 elmas / 16 kişi filtresi AKTİF"
    )

    print(
        f"🏷️ Etiket şartı: "
        f"{TAG_COINS_MIN}+ elmas / "
        f"{TAG_RECIPIENTS_MAX} veya az kişi"
    )

    if UPSTASH_TOKEN:

        print(
            "☁️ Upstash cloud cache AKTİF"
        )

    else:

        print(
            "⚠️ Upstash token yok - "
            "cache kapalı"
        )


    while True:

        try:

            # =================================================
            # PROXY
            # =================================================

            res = await asyncio.to_thread(

                requests.get,

                PROXY_URL,

                headers=HEADERS,

                timeout=5
            )

            data = res.json()

            if not data.get(
                "success"
            ):

                print(
                    "⚠️ Proxy success=false"
                )

                await asyncio.sleep(1)

                continue


            path = data.get(
                "path"
            )

            if not path:

                print(
                    "⚠️ Proxy path bulunamadı"
                )

                await asyncio.sleep(1)

                continue


            ws_url = (
                f"wss://dichvu321.com{path}"
            )


            # =================================================
            # WEBSOCKET
            # =================================================

            async with websockets.connect(

                ws_url,

                additional_headers=HEADERS,

                ping_interval=20,

                ping_timeout=10

            ) as websocket:

                print(
                    "✅ WebSocket bağlandı"
                )


                async for message in websocket:

                    # =========================================
                    # JSON
                    # =========================================

                    try:

                        event_data = json.loads(
                            message
                        )

                    except Exception:

                        continue


                    # =========================================
                    # PAYLOAD
                    # =========================================

                    if isinstance(
                        event_data.get("data"),
                        dict
                    ):

                        payload = (
                            event_data["data"]
                        )

                    else:

                        payload = event_data


                    if not isinstance(
                        payload,
                        dict
                    ):

                        continue


                    if payload.get(
                        "status"
                    ) == "connected":

                        continue


                    # =========================================
                    # HAZİNE / GOODY BAG
                    # =========================================

                    box_type_raw = str(

                        payload.get(
                            "type"
                        )
                        or ""

                    ).lower()


                    source_raw = str(

                        payload.get(
                            "source"
                        )
                        or ""

                    ).lower()


                    envelope_info = (

                        payload.get(
                            "envelopeInfo"
                        )
                        or {}

                    )


                    if not isinstance(
                        envelope_info,
                        dict
                    ):

                        envelope_info = {}


                    business_type = (

                        envelope_info.get(
                            "businessType",
                            1
                        )

                    )


                    is_goody = (

                        business_type == 2

                        or
                        "goody" in box_type_raw

                        or
                        "goody" in source_raw
                    )


                    if is_goody:

                        continue


                    # =========================================
                    # ELMAS
                    # =========================================

                    coins = to_int(

                        payload.get(
                            "coins"
                        ),

                        0
                    )


                    if coins <= 0:

                        continue


                    # =========================================
                    # YAYINCI
                    # =========================================

                    username = (

                        payload.get(
                            "uniqueId"
                        )

                        or

                        payload.get(
                            "nickname"
                        )

                        or

                        payload.get(
                            "username"
                        )

                        or ""

                    )


                    clean_username = (

                        str(username)

                        .replace(
                            "@",
                            ""
                        )

                        .strip()

                    )


                    if not clean_username:

                        continue


                    # =========================================
                    # DAĞITILAN KİŞİ
                    # =========================================

                    recipients = (
                        get_chest_recipients(
                            payload
                        )
                    )


                    # =========================================
                    # 20 / 16 FİLTRESİ
                    # =========================================

                    if (

                        coins == 20

                        and

                        recipients == 16

                    ):

                        print(

                            "⏭️ KALDIRILDI → "

                            f"@{clean_username} "

                            "| 20 elmas / 16 kişi"

                        )

                        continue


                    # =========================================
                    # CACHE
                    # =========================================

                    cache_key = (

                        "treasurealert:"

                        + clean_username.lower()

                        + ":"

                        + str(coins)

                        + ":"

                        + str(recipients)

                    )


                    is_duplicate = (

                        await asyncio.to_thread(

                            check_and_save_cache,

                            cache_key

                        )

                    )


                    if is_duplicate:

                        print(

                            "⏭️ DUPLICATE/CACHE → "

                            f"@{clean_username} "

                            f"| {coins} elmas "

                            f"| {recipients} kişi"

                        )

                        continue


                    # =========================================
                    # LEVEL
                    # =========================================

                    level = to_int(

                        payload.get(
                            "level"
                        ),

                        0
                    )


                    if level > 0:

                        box_title = (

                            "🎁 HAZİNE SANDIĞI "

                            f"(Level {level})"

                        )

                    else:

                        box_title = (
                            "🎁 HAZİNE SANDIĞI"
                        )


                    # =========================================
                    # İZLEYİCİ
                    # =========================================

                    viewers = (

                        payload.get(
                            "viewerCount"
                        )

                        or

                        payload.get(
                            "userCount"
                        )

                        or

                        envelope_info.get(
                            "viewerCount"
                        )

                        or 0

                    )


                    viewers = to_int(
                        viewers,
                        0
                    )


                    # =========================================
                    # CANLI LİNK
                    # =========================================

                    live_link = (

                        "https://www.tiktok.com/"

                        f"@{clean_username}/live"

                    )


                    # =========================================
                    # ETİKET KARARI
                    # =========================================

                    should_tag = (

                        coins >= TAG_COINS_MIN

                        and

                        recipients <= TAG_RECIPIENTS_MAX

                    )


                    # =========================================
                    # MESAJ
                    # =========================================

                    mesaj = (

                        f"{box_title}\n"

                        f"👤 YAYINCI: "
                        f"@{clean_username}\n"

                        f"👁️ İZLEYİCİ: "
                        f"{viewers}\n"

                        f"💎 ELMAS: "
                        f"{coins}\n"

                        f"📦 DAĞITILAN: "
                        f"{recipients} KİŞİ\n"

                        f"🔗 {live_link}"

                    )


                    # =========================================
                    # SADECE UYGUN HAZİNEDE ETİKET
                    # =========================================

                    if should_tag:

                        mesaj = (

                            f"🚨 {TAG_USERNAME}\n\n"

                            + mesaj

                        )

                        print(

                            "🚨 ETİKETLİ → "

                            f"@{clean_username} "

                            f"| {coins} elmas "

                            f"| {recipients} kişi"

                        )

                    else:

                        print(

                            "📩 NORMAL → "

                            f"@{clean_username} "

                            f"| {coins} elmas "

                            f"| {recipients} kişi"

                        )


                    # =========================================
                    # TELEGRAM
                    # =========================================

                    asyncio.create_task(

                        send_telegram(
                            mesaj
                        )

                    )


        # =====================================================
        # BAĞLANTI HATASI
        # =====================================================

        except Exception as e:

            print(
                f"⚠️ BAĞLANTI HATASI: {e}"
            )

            await asyncio.sleep(
                0.5
            )


# ============================================================
# BAŞLAT
# ============================================================

if __name__ == "__main__":

    # Render'ın istediği HTTP portunu
    # ayrı thread'de aç.

    threading.Thread(

        target=start_health_server,

        daemon=True

    ).start()


    # Asıl hazine botu.

    asyncio.run(
        listen_live_feed()
    )
