#!/usr/bin/env python3
# coding: utf-8
import os
import sys
import json
import asyncio
import subprocess
import time
from urllib.parse import quote
import aiohttp
from aiohttp import web
import fcntl

# --- Alle Konstanten an einem Ort ---
LOG_FILE = "/data/progress.log"
TASK_FILE = "/data/task.json"
CONFIG_PATH = "/data/options.json"
WIFI_LIST_FILE = "/var/www/wifi_list.json"
SCAN_TRIGGER_FILE = "/tmp/scan_now"
CONFIGURE_TRIGGER_FILE = "/tmp/configure_now"

# --- Token-Management (wird nur einmal beim Start gelesen) ---
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN")
HEADERS = {"Authorization": f"Bearer {SUPERVISOR_TOKEN}"}

# --- Kombinierte Logging-Funktion ---
def log(message):
    log_message = f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {message}"
    print(log_message, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_message + "\n")
    except Exception as e:
        print(f"Error writing to log file: {e}", flush=True)

# --- Supervisor API-Funktion (aus configure_shellies.py) ---
async def supervisor_api_request(session, method, url, data=None):
    if not SUPERVISOR_TOKEN:
        log("FATAL: SUPERVISOR_TOKEN is missing. Cannot make API calls.")
        return None
    try:
        async with session.request(method, url, json=data, headers=HEADERS, timeout=40) as response:
            if response.status >= 400:
                raw_text = await response.text()
                log(f"FEHLER bei API-Aufruf ({url}): Status {response.status}, Antwort: {raw_text}")
                return None
            return await response.json()
    except Exception as e:
        log(f"Schwerer Fehler beim API-Aufruf: {e}")
        return None

# --- Konfigurations-Logik (aus configure_shellies.py) ---
async def run_configuration_logic():
    lock_file_path = '/tmp/configure.lock'
    try:
        with open(lock_file_path, 'w') as lf:
            fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with open(LOG_FILE, 'w') as f: f.write('')
            log("Konfigurationsprozess gestartet...")

            with open(TASK_FILE, 'r') as f: task = json.load(f)
            with open(CONFIG_PATH, 'r') as f: config = json.load(f)
            
            selected_shellies = task.get("selectedShellies", [])
            user_ssid = task.get("userSsid", "")
            interface = config.get("interface", "wlan0")

            if not user_ssid or not selected_shellies:
                log("FEHLER: Ungültige Aufgabendaten.")
                return

            async with aiohttp.ClientSession() as session:
                for shelly_ssid in selected_shellies:
                    log(f"--- Bearbeite: {shelly_ssid} ---")
                    options = {"wifi": {"ssid": shelly_ssid, "auth": "open"}}
                    api_url = f"http://supervisor/network/interface/{interface}/accesspoints"
                    if not await supervisor_api_request(session, 'post', api_url, options):
                         log(f"FEHLER beim Senden des Verbindungs-Befehls für {shelly_ssid}.")
                         continue
                    log(f"Verbindung zu {shelly_ssid} erfolgreich beauftragt.")
            
    except IOError:
        log("Konfigurationsprozess läuft bereits.")
    except Exception as e:
        log(f"Ein unerwarteter Fehler im Konfigurationsprozess ist aufgetreten: {e}")
    finally:
        log("--- Konfiguration abgeschlossen. ---")
        if os.path.exists(TASK_FILE): os.remove(TASK_FILE)

# --- WLAN-Scan-Schleife (aus run.sh) ---
async def wifi_scan_loop():
    log("WLAN Scan-Schleife gestartet.")
    config = json.load(open(CONFIG_PATH))
    interface = config.get("interface", "wlan0")
    interval = config.get("scan_interval", 60)

    while True:
        try:
            if os.path.exists(CONFIGURE_TRIGGER_FILE):
                os.remove(CONFIGURE_TRIGGER_FILE)
                asyncio.create_task(run_configuration_logic())

            log("Suche nach WLAN-Netzwerken...")
            cmd = ["iw", "dev", interface, "scan"]
            proc = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                log("Scan erfolgreich.")
                output = stdout.decode('utf-8')
                ssids = [line.split("SSID: ")[1] for line in output.split('\n') if "SSID: " in line]
                with open(WIFI_LIST_FILE, 'w') as f:
                    json.dump(ssids, f)
            else:
                log(f"FEHLER: 'iw scan' fehlgeschlagen. Fehler: {stderr.decode('utf-8')}")

            log(f"Warte bis zu {interval} Sekunden...")
            for _ in range(interval):
                if os.path.exists(SCAN_TRIGGER_FILE) or os.path.exists(CONFIGURE_TRIGGER_FILE):
                    if os.path.exists(SCAN_TRIGGER_FILE): os.remove(SCAN_TRIGGER_FILE)
                    break
                await asyncio.sleep(1)

        except Exception as e:
            log(f"Fehler in der Scan-Schleife: {e}")
            await asyncio.sleep(30) # Bei Fehler länger warten

# --- API-Server-Handler (aus api_server.py) ---
async def handle_scan(request):
    with open(SCAN_TRIGGER_FILE, "w") as f: pass
    return web.Response(status=204)

async def handle_configure(request):
    try:
        data = await request.json()
        with open(TASK_FILE, "w") as f: json.dump(data, f)
        with open(CONFIGURE_TRIGGER_FILE, "w") as f: pass
        return web.Response(status=202)
    except Exception as e:
        log(f"API Fehler /api/configure: {e}")
        return web.Response(status=500)

async def handle_progress(request):
    try:
        with open(LOG_FILE, "r") as f: content = f.read()
        return web.Response(text=content, content_type="text/plain")
    except FileNotFoundError:
        return web.Response(text="Log-Datei noch nicht vorhanden.", status=200)

# --- Haupt-Startfunktion ---
async def start_background_tasks(app):
    app['wifi_scanner'] = asyncio.create_task(wifi_scan_loop())

async def main_startup():
    log(".....................................................................................................Add-on wird gestartet...")
    log(f"DEBUG: Supervisor Token vorhanden: {'Ja' if SUPERVISOR_TOKEN else 'Nein'}")
    if SUPERVISOR_TOKEN:
        log(f"DEBUG: Token beginnt mit: {SUPERVISOR_TOKEN[:5]}, endet mit: {SUPERVISOR_TOKEN[-5:]}")

    # Nginx starten
    log("Starte Nginx...")
    subprocess.Popen(["nginx", "-g", "daemon off;"])
    
    # API Server und Scan-Schleife starten
    app = web.Application()
    app.on_startup.append(start_background_tasks)
    app.router.add_get("/api/scan", handle_scan)
    app.router.add_post("/api/configure", handle_configure)
    app.router.add_get("/api/progress", handle_progress)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 8888)
    await site.start()
    log("API-Server läuft auf 127.0.0.1:8888")
    
    # Endlos warten
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main_startup())
    except KeyboardInterrupt:
        log("Add-on wird gestoppt.")