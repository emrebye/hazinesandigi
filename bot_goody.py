                        # 1. Goody Bag için gerçek toplam elmas miktarını tespit etme
                        coins = int(
                            envelope_info.get("totalDiamondCount")
                            or envelope_info.get("diamondCount")
                            or envelope_info.get("coinCount")
                            or payload.get("totalCoins")
                            or payload.get("coins")
                            or payload.get("diamondCount")
                            or 0
                        )

                        # 2. 50 elmastan küçük olan Goody Bag kutularını pas geç
                        if coins < 50:
                            continue

                        viewers = (
                            payload.get("viewerCount")
                            or payload.get("userCount")
                            or envelope_info.get("viewerCount")
                            or 0
                        )
