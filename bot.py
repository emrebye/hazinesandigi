        async def on_response(res):
            try:
                if "json" in res.headers.get("content-type", "").lower():
                    text = await res.text()
                    parse_and_process(text)
            except Exception:
                pass

        page.on("response", lambda res: asyncio.create_task(on_response(res)))

        def on_websocket(ws):
            def on_frame(frame_data):
                payload_str = frame_data.decode('utf-8', errors='ignore') if isinstance(frame_data, bytes) else str(frame_data)
                parse_and_process(payload_str)
            ws.on("framereceived", on_frame)

        page.on("websocket", on_websocket)
