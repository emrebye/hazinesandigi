def parse_and_process(raw_str):
    try:
        # Metin içindeki JSON listesini veya objesini Regex ile ayıkla
        json_match = re.search(r'(\{.*\}|\[.*\])', raw_str)
        if not json_match:
            return
        
        cleaned_json = json_match.group(0)
        data = json.loads(cleaned_json)
        
        # Socket.IO dizisi halinde gelebilir (örn: ["stream", {data}])
        if isinstance(data, list):
            items = []
            for sub in data:
                if isinstance(sub, dict):
                    items.append(sub)
                elif isinstance(sub, list):
                    items.extend([x for x in sub if isinstance(x, dict)])
        else:
            items = [data.get("data", data)]

        for item in items:
            if not isinstance(item, dict) or item.get("status") == "connected":
                continue
                
            username = item.get("uniqueId") or item.get("username") or item.get("nickname") or item.get("author") or ""
            coins = 0
            for k in ["coins", "diamonds", "totalCoins", "val", "amount"]:
                if item.get(k) is not None:
                    try:
                        coins = int(item[k])
                        break
                    except (ValueError, TypeError):
                        pass
                        
            box_type = str(item.get("type") or "HAZİNE SANDIĞI")
            viewers = item.get("viewers", item.get("viewerCount", 0))
            
            if username and coins > 0:
                process_item(username, coins, box_type, viewers)
    except Exception as e:
        # Hataları takip edebilmek için loglayın
        pass
