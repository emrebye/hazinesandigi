async def scrape_dom_cards(page):
    try:
        body_text = await page.inner_text("body")
        
        # Ekrandaki yazıyı yayıncı adlarının başındaki '@' işaretine göre bölüyoruz
        parts = body_text.split('@')
        
        for i in range(1, len(parts)):
            # @ işaretinden önceki kısım (Sandık türü ve coin miktarı burada yazar)
            chunk_before = parts[i-1][-150:] 
            # @ işaretinden sonraki kısım (Yayıncı adı burada yazar)
            chunk_after = parts[i] 
            
            # Kullanıcı adını yakala (boşluğa, madde işaretine veya alt satıra kadar)
            user_match = re.search(r'^([a-zA-Z0-9_\.]+)', chunk_after)
            
            # Coin miktarını yakala (Örn: "20 coins" veya "20 diamond")
            coin_match = re.search(r'(\d+)\s*(?:coins?|elmas|diamonds?)', chunk_before, re.IGNORECASE)
            
            if user_match and coin_match:
                username = user_match.group(1)
                coins = int(coin_match.group(1))
                
                # Kutu türünü belirle
                box_type = "HAZİNE SANDIĞI"
                if "GOODY BAG" in chunk_before.upper():
                    box_type = "GOODY BAG"
                
                process_item(username, coins, box_type)
    except Exception as e:
        pass
