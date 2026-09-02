import asyncio
import json
import os
import requests
import websockets

# ============================================================
# AYARLAR
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID = os.getenv("CHAT_ID", "-1004325133382")

PROXY_URL = "https://dichvu321.com/proxy.php?stream=all&live=4000"

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

TAG_COINS_MIN = 100
TAG_RECIPIENTS_MAX = 5
TAG_USERNAME = "@jiminienn"

# ============================================================
# UPSTASH CLOUD CACHE
# ============================================================

UPSTASH_URL = os.getenv(
    "UPSTASH_URL",
    "https://exotic-javelin-180919.upstash.io"
)

UPSTASH_TOKEN = os.getenv("UPSTASH_TOKEN", "")

CACHE_TIMEOUT = 1800


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

        response = requests.post(
            UPSTASH_URL,
            headers=headers,
            json=payload,
            timeout=3
        )

        response.raise_for_status()

        result = response.json().get("result")

        return result != "OK"

    except Exception as e:
        print(f"⚠️ Upstash cache hatası: {e}")
        return False


# ============================================================
# YARDIMCI FONKSİYONLAR
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


def recursive_find_key(obj, wanted_keys):

    wanted = {
        str(x).lower()
        for x in wanted_keys
    }

    if isinstance(obj, dict):

        for key, value in obj.items():

            if str(key).lower() in wanted:

                number = to_int(value, None)

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


def get_chest_recipients(payload):

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


def debug_relevant_keys(payload):

    if not isinstance(payload, dict):
        return

    interesting = {
        "canopen",
        "peoplecount",
        "participantcount",
        "winnercount",
        "claimcount",
        "recipientcount",
        "grabcount",
        "membercount",
        "people",
        "participants",
        "winners",
        "recipients"
    }

    found = []

    def scan(obj, path=""):

        if isinstance(obj, dict):

            for key, value in obj.items():

                key_lower = str(key).lower()

                if key_lower in interesting:

                    found.append(
                        f"{path}/{key}={value}"
                    )

                scan(
                    value,
                    f"{path}/{key}"
                )

        elif isinstance(obj, list):

            for index, item in enumerate(obj):

                scan(
                    item,
                    f"{path}[{index}]"
                )

    scan(payload)

    if found:

        print("🔎 KİŞİ SAYISI ALANLARI:")

        for item in found[:30]:
            print("   ", item)

    else:
        print("❌ Kişi sayısı alanı bulunamadı.")


# ============================================================
# TELEGRAM
# ============================================================

async def send_telegram(mesaj):

    if not TELEGRAM_BOT_TOKEN:

        print(
            "❌ BOT_TOKEN bulunamadı. "
            "Termux'ta BOT_TOKEN tanımla."
        )

        return

    url = (
        f"https://api.telegram.org/"
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
            f"⚠️ Telegram gönderim hatası: {e}"
        )


# ============================================================
# CANLI AKIŞ
# ============================================================

async def listen_live_feed():

    print("🚀 HAZİNE BOTU BAŞLADI")

    if UPSTASH_TOKEN:
        print("☁️ Upstash cloud cache: AKTİF")
    else:
        print("⚠️ Upstash token yok: CACHE KAPALI")

    print(
        f"🏷️ Etiket şartı: "
        f"{TAG_COINS_MIN}+ elmas / "
        f"{TAG_RECIPIENTS_MAX} veya daha az kişi"
    )

    print("🎁 canOpen öncelikli kişi sayısı sistemi AKTİF")

    print("🚫 20 elmas / 16 kişi filtresi AKTİF")

    while True:

        try:

            # ------------------------------------------------
            # PROXY'DEN WEBSOCKET ADRESİ AL
            # ------------------------------------------------

            res = await asyncio.to_thread(
                requests.get,
                PROXY_URL,
                headers=HEADERS,
                timeout=5
            )

            data = res.json()

            if not data.get("success"):

                await asyncio.sleep(1)

                continue

            path = data.get("path")

            if not path:

                await asyncio.sleep(1)

                continue

            ws_url = (
                f"wss://dichvu321.com{path}"
            )

            # ------------------------------------------------
            # WEBSOCKET
            # ------------------------------------------------

            async with websockets.connect(
                ws_url,
                additional_headers=HEADERS,
                ping_interval=20,
                ping_timeout=10
            ) as websocket:

                print("✅ WebSocket bağlandı")

                async for message in websocket:

                    # ========================================
                    # JSON
                    # ========================================

                    try:

                        event_data = json.loads(message)

                    except Exception:

                        continue

                    # ========================================
                    # PAYLOAD
                    # ========================================

                    payload = (
                        event_data.get("data")
                        if isinstance(
                            event_data.get("data"),
                            dict
                        )
                        else event_data
                    )

                    if not isinstance(payload, dict):

                        continue

                    if payload.get("status") == "connected":

                        continue

                    # ========================================
                    # HAZİNE / GOODY BAG AYRIMI
                    # ========================================

                    box_type_raw = str(
                        payload.get("type") or ""
                    ).lower()

                    source_raw = str(
                        payload.get("source") or ""
                    ).lower()

                    envelope_info = (
                        payload.get("envelopeInfo")
                        or {}
                    )

                    if not isinstance(
                        envelope_info,
                        dict
                    ):

                        envelope_info = {}

                    business_type = envelope_info.get(
                        "businessType",
                        1
                    )

                    is_goody = (
                        business_type == 2
                        or "goody" in box_type_raw
                        or "goody" in source_raw
                    )

                    if is_goody:

                        continue

                    # ========================================
                    # ELMAS
                    # ========================================

                    coins_number = to_int(
                        payload.get("coins"),
                        0
                    )

                    if coins_number <= 0:

                        continue

                    # ========================================
                    # YAYINCI
                    # ========================================

                    username = (
                        payload.get("uniqueId")
                        or payload.get("nickname")
                        or payload.get("username")
                        or ""
                    )

                    clean_username = (
                        str(username)
                        .replace("@", "")
                        .strip()
                    )

                    if not clean_username:

                        continue

                    # ========================================
                    # DAĞITILAN KİŞİ SAYISI
                    # ========================================

                    recipients_number = (
                        get_chest_recipients(
                            payload
                        )
                    )

                    # ========================================
                    # SADECE 20 / 16'YI KALDIR
                    # ========================================

                    if (
                        coins_number == 20
                        and recipients_number == 16
                    ):

                        print(
                            f"⏭️ KALDIRILDI: "
                            f"@{clean_username} "
                            f"| 20 elmas / 16 kişi"
                        )

                        continue

                    # ========================================
                    # DUPLICATE CACHE
                    # ========================================

                    cache_key = (
                        "treasurealert:"
                        + clean_username.lower()
                        + ":"
                        + str(coins_number)
                        + ":"
                        + str(recipients_number)
                    )

                    is_duplicate = await asyncio.to_thread(
                        check_and_save_cache,
                        cache_key
                    )

                    if is_duplicate:

                        print(
                            f"⏭️ DUPLICATE/CACHE: "
                            f"@{clean_username} "
                            f"| Elmas: {coins_number} "
                            f"| Kişi: {recipients_number}"
                        )

                        continue

                    # ========================================
                    # LEVEL
                    # ========================================

                    level = to_int(
                        payload.get("level"),
                        0
                    )

                    if level > 0:

                        box_title = (
                            f"🎁 HAZİNE SANDIĞI "
                            f"(Level {level})"
                        )

                    else:

                        box_title = (
                            "🎁 HAZİNE SANDIĞI"
                        )

                    # ========================================
                    # İZLEYİCİ
                    # ========================================

                    viewers = (
                        payload.get("viewerCount")
                        or payload.get("userCount")
                        or envelope_info.get(
                            "viewerCount"
                        )
                        or 0
                    )

                    viewers = to_int(
                        viewers,
                        0
                    )

                    # ========================================
                    # CANLI YAYIN LİNKİ
                    # ========================================

                    live_link = (
                        "https://www.tiktok.com/"
                        f"@{clean_username}/live"
                    )

                    # ========================================
                    # ETİKET KARARI
                    # ========================================

                    should_tag = (
                        coins_number >= TAG_COINS_MIN
                        and recipients_number <= TAG_RECIPIENTS_MAX
                    )

                    # ========================================
                    # TELEGRAM MESAJI
                    # ========================================

                    mesaj = (
                        f"{box_title}\n"
                        f"👤 YAYINCI: "
                        f"@{clean_username}\n"
                        f"👁️ İZLEYİCİ: "
                        f"{viewers}\n"
                        f"💎 ELMAS: "
                        f"{coins_number}\n"
                        f"📦 DAĞITILAN: "
                        f"{recipients_number} KİŞİ\n"
                        f"🔗 {live_link}"
                    )

                    # ========================================
                    # SADECE ŞART UYUYORSA ETİKET
                    # ========================================

                    if should_tag:

                        mesaj = (
                            f"🚨 {TAG_USERNAME}\n\n"
                            + mesaj
                        )

                        print(
                            f"🚨 ETİKETLİ HAZİNE: "
                            f"@{clean_username} "
                            f"| {coins_number} elmas "
                            f"| {recipients_number} kişi"
                        )

                    else:

                        print(
                            f"📩 NORMAL HAZİNE: "
                            f"@{clean_username} "
                            f"| {coins_number} elmas "
                            f"| {recipients_number} kişi"
                        )

                    # ========================================
                    # TELEGRAM'A GÖNDER
                    # ========================================

                    asyncio.create_task(
                        send_telegram(mesaj)
                    )

        # ================================================
        # BAĞLANTI HATASI
        # ================================================

        except Exception as e:

            print(
                f"⚠️ BAĞLANTI HATASI: {e}"
            )

            await asyncio.sleep(0.5)


# ============================================================
# BAŞLAT
# ============================================================

if __name__ == "__main__":

    asyncio.run(
        listen_live_feed()
    )
