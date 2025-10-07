#!/usr/bin/env python3
import os
import json
from aiohttp import web

# Konstanten für die Trigger-Dateien
SCAN_TRIGGER_FILE = "/tmp/scan_now"
CONFIGURE_TRIGGER_FILE = "/tmp/configure_now"
TASK_FILE = "/data/task.json"
PROGRESS_LOG_FILE = "/data/progress.log"

# Handler für den Scan-Endpunkt
async def handle_scan(request):
    """Erstellt die Trigger-Datei für einen neuen Scan."""
    print("API: Scan-Anfrage erhalten.")
    with open(SCAN_TRIGGER_FILE, "w") as f:
        pass  # entspricht 'touch'
    return web.Response(status=204)  # 204 No Content

# Handler für den Konfigurations-Endpunkt
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
            pass # Trigger erstellen
            
        print("API: task.json und Trigger erfolgreich erstellt.")
        return web.Response(status=202)  # 202 Accepted
    except json.JSONDecodeError:
        return web.Response(status=400, text="Bad Request: Invalid JSON.")
    except Exception as e:
        print(f"API: Unerwarteter Fehler in handle_configure: {e}")
        return web.Response(status=500, text="Internal Server Error.")

# Handler für den Fortschritts-Endpunkt
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

# App aufsetzen und Routen definieren
app = web.Application()
app.router.add_get("/api/scan", handle_scan)
app.router.add_post("/api/configure", handle_configure)
app.router.add_get("/api/progress", handle_progress)

# Server starten
print("Starte aiohttp API-Server auf 127.0.0.1:8888...")
web.run_app(app, host="127.0.0.1", port=8888)