import asyncio
import json
import os
import requests
import websockets
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

============================================================

DUMMY SERVER

============================================================

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

============================================================

AYARLAR

============================================================

Öncelik: Environment değişkenleri

Yoksa mevcut değerleri kullanır.

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

============================================================

TELEGRAM

============================================================

async def send_telegram(message):

url = (  
    f"https://api.telegram.org/"  
    f"bot{TELEGRAM_BOT_TOKEN}/sendMessage"  
)  

payload = {  
    "chat_id": CHAT_ID,  
    "text": message,  
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

    print(f"⚠️ Telegram hatası: {e}")

============================================================

SAYIYA ÇEVİR

============================================================

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

============================================================

İÇ İÇE KEY ARAMA

============================================================

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
            f"{path}.{key}"  
            if path  
            else str(key)  
        )  

        if key_normalized in wanted_keys:  

            number = to_int(value)  

            if number is not None:  
                return number, current_path  

        result = recursive_find_key(  
            value,  
            wanted_keys,  
            current_path  
        )  

        if result[0] is not None:  
            return result  

elif isinstance(obj, list):  

    for index, item in enumerate(obj):  

        result = recursive_find_key(  
            item,  
            wanted_keys,  
            f"{path}[{index}]"  
        )  

        if result[0] is not None:  
            return result  

return None, None

============================================================

HAZİNE KİŞİ SAYISI

============================================================

def get_chest_recipients(payload):

"""  
ÖNCELİK SIRASI:  

1. canOpen  
2. peopleCount  
3. people_count  
4. participantCount  
5. winnerCount  
6. claimCount  
7. recipientCount  
8. grabCount  

Eski botta canOpen kullanılıyordu.  
Bu nedenle canOpen en yüksek öncelikte.  
"""  

key_groups = [  

    # Eski yedekte kullanılan gerçek alan  
    ["canopen"],  

    # TikTok protobuf / JSON varyasyonları  
    ["peoplecount"],  
    ["participantcount"],  
    ["winnercount"],  
    ["claimcount"],  
    ["recipientcount"],  
    ["grabcount"],  
    ["membercount"],  

    # Diğer varyasyonlar  
    ["people"],  
    ["participants"],  
    ["winners"],  
    ["recipients"]  
]  

for wanted_keys in key_groups:  

    value, path = recursive_find_key(  
        payload,  
        wanted_keys  
    )  

    if value is not None:  

        print(  
            f"🎯 KİŞİ SAYISI BULUNDU: "  
            f"{value} | KEY: {path}"  
        )  

        return value, path  

return None, None

============================================================

PAYLOAD İÇİNDEKİ İLGİLİ KEY'LERİ GÖSTER

============================================================

def debug_relevant_keys(obj, path=""):

if isinstance(obj, dict):  

    for key, value in obj.items():  

        current_path = (  
            f"{path}.{key}"  
            if path  
            else str(key)  
        )  

        key_lower = str(key).lower()  

        if any(word in key_lower for word in [  
            "open",  
            "people",  
            "participant",  
            "winner",  
            "claim",  
            "recipient",  
            "grab",  
            "envelope",  
            "business",  
            "diamond",  
            "coin"  
        ]):  

            print(  
                f"🔎 {current_path} = {value}"  
            )  

        debug_relevant_keys(  
            value,  
            current_path  
        )  

elif isinstance(obj, list):  

    for index, item in enumerate(obj):  

        debug_relevant_keys(  
            item,  
            f"{path}[{index}]"  
        )

============================================================

CANLI AKIŞ

============================================================

async def listen_live_feed():

print("=" * 60)  
print("🚀 TREASURE ALERT BAŞLADI")  
print("🎁 HAZİNE SANDIĞI TAKİBİ AKTİF")  
print("🎯 canOpen + peopleCount araması aktif")  
print("=" * 60)  

while True:  

    try:  

        # ------------------------------------------------  
        # PROXY  
        # ------------------------------------------------  

        print("🔄 Proxy bağlantısı alınıyor...")  

        res = await asyncio.to_thread(  
            requests.get,  
            PROXY_URL,  
            headers=HEADERS,  
            timeout=8  
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

        ws_url = (  
            f"wss://dichvu321.com{path}"  
        )  

        print(  
            f"🔌 WebSocket bağlanıyor..."  
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

            print("✅ WebSocket bağlandı.")  

            async for message in websocket:  

                try:  

                    event_data = json.loads(  
                        message  
                    )  

                except Exception:  
                    continue  

                # ------------------------------------------------  
                # DATA  
                # ------------------------------------------------  

                if (  
                    isinstance(event_data, dict)  
                    and isinstance(  
                        event_data.get("data"),  
                        dict  
                    )  
                ):  

                    payload = event_data["data"]  

                else:  

                    payload = event_data  

                if not isinstance(payload, dict):  
                    continue  

                # Bağlantı mesajını geç  
                if payload.get("status") == "connected":  
                    continue  

                # ------------------------------------------------  
                # ENVELOPE INFO  
                # ------------------------------------------------  

                envelope_info = (  
                    payload.get("envelopeInfo")  
                    or {}  
                )  

                if not isinstance(  
                    envelope_info,  
                    dict  
                ):  
                    envelope_info = {}  

                business_type = (  
                    envelope_info.get(  
                        "businessType"  
                    )  
                )  

                # ------------------------------------------------  
                # GOODY BAG FİLTRESİ  
                # ------------------------------------------------  

                box_type_raw = str(  
                    payload.get("type") or ""  
                ).lower()  

                source_raw = str(  
                    payload.get("source") or ""  
                ).lower()  

                is_goody = (  
                    business_type == 2  
                    or "goody" in box_type_raw  
                    or "goody" in source_raw  
                )  

                if is_goody:  

                    print(  
                        "⏭️ Goody Bag atlandı."  
                    )  

                    continue  

                # ------------------------------------------------  
                # USERNAME  
                # ------------------------------------------------  

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

                # ------------------------------------------------  
                # ELİMAS  
                # ------------------------------------------------  

                coins = (  
                    payload.get("coins")  
                    or payload.get("amount")  
                    or payload.get("diamond")  
                    or payload.get("elmas")  
                    or 0  
                )  

                try:  
                    coins_number = int(coins)  
                except Exception:  
                    coins_number = 0  

                # Hazine filtresi  
                if coins_number < 10:  
                    continue  

                # ------------------------------------------------  
                # LEVEL  
                # ------------------------------------------------  

                level = payload.get(  
                    "level",  
                    0  
                )  

                try:  
                    level = int(level)  
                except Exception:  
                    level = 0  

                if level > 0:  

                    box_title = (  
                        f"🎁 HAZİNE SANDIĞI "  
                        f"(Level {level})"  
                    )  

                else:  

                    box_title = (  
                        "🎁 HAZİNE SANDIĞI"  
                    )  

                # ------------------------------------------------  
                # İZLEYİCİ  
                # ------------------------------------------------  

                viewers = (  
                    payload.get("viewerCount")  
                    or payload.get("viewers")  
                    or payload.get("userCount")  
                    or envelope_info.get(  
                        "viewerCount"  
                    )  
                    or 0  
                )  

                # ------------------------------------------------  
                # KİŞİ SAYISI  
                # ------------------------------------------------  

                recipients, recipients_path = (  
                    get_chest_recipients(  
                        payload  
                    )  
                )  

                # ------------------------------------------------  
                # KİŞİ SAYISI BULUNAMADIYSA  
                # ------------------------------------------------  

                if recipients is None:  

                    print("\n" + "=" * 60)  
                    print(  
                        "⚠️ KİŞİ SAYISI BULUNAMADI"  
                    )  
                    print(  
                        f"👤 @{clean_username}"  
                    )  
                    print(  
                        f"💎 Elmas: {coins_number}"  
                    )  

                    print(  
                        "\n🔎 İLGİLİ KEY'LER:"  
                    )  

                    debug_relevant_keys(  
                        payload  
                    )  

                    print(  
                        "\n📦 HAM PAYLOAD:"  
                    )  

                    print(  
                        json.dumps(  
                            payload,  
                            ensure_ascii=False,  
                            indent=2  
                        )  
                    )  

                    print("=" * 60 + "\n")  

                    recipients_text = (  
                        "BULUNAMADI"  
                    )  

                else:  

                    recipients_text = (  
                        f"{recipients} KİŞİ"  
                    )  

                # ------------------------------------------------  
                # LINK  
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
                # TELEGRAM  
                # ------------------------------------------------  

                mesaj = (  
                    f"{box_title}\n"  
                    f"👤 YAYINCI: "  
                    f"@{clean_username}\n"  
                    f"👁️ İZLEYİCİ: "  
                    f"{viewers}\n"  
                    f"💎 ELMAS: "  
                    f"{coins_number}\n"  
                    f"📦 DAĞITILAN: "  
                    f"{recipients_text}\n"  
                    f"🔗 {live_link}"  
                )  

                asyncio.create_task(  
                    send_telegram(mesaj)  
                )  

                print(  
                    f"✅ GÖNDERİLDİ: "  
                    f"@{clean_username} | "  
                    f"Elmas: {coins_number} | "  
                    f"Kişi: {recipients_text}"  
                )  

    except Exception as e:  

        print(  
            f"⚠️ BAĞLANTI HATASI: {e}"  
        )  

        await asyncio.sleep(1)

============================================================

BAŞLAT

============================================================

if name == "main":

Thread(  
    target=run_dummy_server,  
    daemon=True  
).start()  

asyncio.run(  
    listen_live_feed()  
)

Bunun icine  koy duzenle
