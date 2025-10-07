#!/usr/bin/env python3
import os
import json
import asyncio
from aiohttp import web

# Konstanten (unverändert)
SCAN_TRIGGER_FILE = "/tmp/scan_now"
CONFIGURE_TRIGGER_FILE = "/tmp/configure_now"
TASK_FILE = "/data/task.json"
PROGRESS_LOG_FILE = "/data/progress.log"

# Handler für den Scan-Endpunkt (unverändert)
async def handle_scan(request):
    """Erstellt die Trigger-Datei für einen neuen Scan."""
    print("API: Scan-Anfrage erhalten.")
    with open(SCAN_TRIGGER_FILE, "w") as f:
        pass
    return web.Response(status=204)

# Handler für den Konfigurations-Endpunkt (unverändert)
async def handle_configure(request):
    """Empfängt die Konfigurationsdaten und startet den Prozess."""
    print("API: Konfigurations-Anfrage erhalten.")
    if not request.can_read_body:
        return web.Response(status=400, text="Bad Request: No body.")
    try:
        data = await request.json()
        with open(TASK_FILE, "w") as f:
            json.dump(data, f)
        with open(CONFIGURE_TRIGGER_FILE, "w") as f:
            pass
        print("API: task.json und Trigger erfolgreich erstellt.")
        # Status 202 ist hier semantisch korrekter
        return web.Response(status=202)
    except json.JSONDecodeError:
        return web.Response(status=400, text="Bad Request: Invalid JSON.")
    except Exception as e:
        print(f"API: Unerwarteter Fehler in handle_configure: {e}")
        return web.Response(status=500, text="Internal Server Error.")

# Handler für den Fortschritts-Endpunkt (unverändert)
async def handle_progress(request):
    """Liest die Fortschritts-Logdatei und gibt sie zurück."""
    try:
        with open(PROGRESS_LOG_FILE, "r") as f:
            content = f.read()
        return web.Response(text=content, content_type="text/plain")
    except FileNotFoundError:
        return web.Response(text="Log-Datei noch nicht vorhanden.", status=200, content_type="text/plain")
    except Exception as e:
        print(f"API: Fehler in handle_progress: {e}")
        return web.Response(status=500, text="Internal Server Error.")

# --- ALTER TEIL (wird ersetzt) ---
# app = web.Application()
# app.router.add_get("/api/scan", handle_scan)
# app.router.add_post("/api/configure", handle_configure)
# app.router.add_get("/api/progress", handle_progress)
# print("Starte aiohttp API-Server auf 127.0.0.1:8888...")
# web.run_app(app, host="127.0.0.1", port=8888)
# ------------------------------------

# --- NEUER, ROBUSTERER START ---
async def main():
    app = web.Application()
    app.router.add_get("/api/scan", handle_scan)
    app.router.add_post("/api/configure", handle_configure)
    app.router.add_get("/api/progress", handle_progress)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 8888)
    
    print("Starte aiohttp API-Server auf 127.0.0.1:8888...")
    await site.start()
    
    # Hält den Server am Laufen, bis das Skript gestoppt wird
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
# -----------------------------