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
import random

print("==== ENVIRONMENT ====")
for key, val in os.environ.items():
    if "SUPERVISOR" in key or "HASS" in key:
        print(f"{key}={val}")
print("======================")


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
# main.py

# Hilfsfunktion, um externe Befehle auszuführen und zu loggen
async def run_command(cmd):
    log(f"Führe aus: {' '.join(cmd)}")
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = await proc.communicate()
    
    stdout_str = stdout.decode('utf-8').strip()
    stderr_str = stderr.decode('utf-8').strip()
    
    if stdout_str:
        log(f"Ausgabe: {stdout_str}")
    if stderr_str:
        log(f"Fehler-Ausgabe: {stderr_str}")
        
    return proc.returncode == 0

async def run_configuration_logic(caller_id="unknown"): # <--- NEUER PARAMETER
    lock_file_path = '/tmp/configure.lock'
    log(f"[{caller_id}] Betrete run_configuration_logic...") # <--- NEUES LOG
    try:
        with open(lock_file_path, 'w') as lf:
            fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with open(LOG_FILE, 'w') as f: f.write('') # Log leeren
            log(f"[{caller_id}] Konfigurationsprozess gestartet...") # <--- MODIFIZIERTES LOG

            with open(TASK_FILE, 'r') as f: task = json.load(f)
            with open(CONFIG_PATH, 'r') as f: config = json.load(f)
            
            selected_shellies = task.get("selectedShellies", [])
            user_ssid = task.get("userSsid", "")
            user_password = task.get("userPassword", "")
            interface = config.get("interface", "wlan0")

            if not user_ssid or not selected_shellies:
                log(f"[{caller_id}] FEHLER: Ungültige Aufgabendaten.")
                return

            await run_command(["nmcli", "radio", "wifi", "on"])

            for shelly_ssid in selected_shellies:
                log(f"[{caller_id}] --- Bearbeite: {shelly_ssid} ---")
                
                # ... (Rest der for-Schleife bleibt logisch gleich, wir könnten hier auch noch IDs hinzufügen) ...
                # ... aus Gründen der Übersichtlichkeit lassen wir das erstmal weg ...
                log(f"[{caller_id}] Versuche Verbindung zu {shelly_ssid}...")
                await run_command(["nmcli", "connection", "delete", shelly_ssid])
                connect_success = await run_command([
                    "nmcli", "device", "wifi", "connect", shelly_ssid, 
                    "name", shelly_ssid,
                    "ifname", interface
                ])

                if not connect_success:
                    log(f"[{caller_id}] FEHLER: Konnte keine Verbindung zu {shelly_ssid} herstellen.")
                    continue
                
                await asyncio.sleep(10)

                shelly_ip = "192.168.33.1"
                encoded_ssid = quote(user_ssid)
                encoded_pass = quote(user_password)
                configure_url = f"http://{shelly_ip}/settings/sta?ssid={encoded_ssid}&key={encoded_pass}&enabled=1"

                log(f"[{caller_id}] Sende Konfigurationsbefehl...")
                try:
                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
                        async with session.get(configure_url) as response:
                            if response.status == 200:
                                log(f"[{caller_id}] Befehl erfolgreich gesendet.")
                            else:
                                log(f"[{caller_id}] FEHLER: Shelly-Antwort: {response.status}")
                except Exception as e:
                    log(f"[{caller_id}] FEHLER beim Senden des HTTP-Befehls: {e}")
                finally:
                    log(f"[{caller_id}] Trenne Verbindung zu {shelly_ssid}...")
                    await run_command(["nmcli", "connection", "down", shelly_ssid])
                    await run_command(["nmcli", "connection", "delete", shelly_ssid])
                    log(f"[{caller_id}] Verbindung getrennt.")

    except IOError:
        log(f"[{caller_id}] Konfigurationsprozess läuft bereits (Lock-Datei vorhanden).") # <--- MODIFIZIERTES LOG
    except Exception as e:
        log(f"[{caller_id}] Ein unerwarteter Fehler ist aufgetreten: {e}")
    finally:
        log(f"[{caller_id}] --- Konfiguration abgeschlossen. ---") # <--- MODIFIZIERTES LOG
        if os.path.exists(TASK_FILE): os.remove(TASK_FILE)

# --- WLAN-Scan-Schleife (aus run.sh) ---
# main.py

async def wifi_scan_loop():
    log("WLAN Scan-Dienst gestartet. Warte auf Trigger...")
    config = json.load(open(CONFIG_PATH))
    interface = config.get("interface", "wlan0")

    while True:
        while not os.path.exists(SCAN_TRIGGER_FILE) and not os.path.exists(CONFIGURE_TRIGGER_FILE):
            await asyncio.sleep(1)

        if os.path.exists(CONFIGURE_TRIGGER_FILE):
            os.remove(CONFIGURE_TRIGGER_FILE)
            
            # Erzeuge eine eindeutige ID für diesen spezifischen Auftrag
            task_id = f"task_{random.randint(1000, 9999)}" # <--- NEU
            
            # Übergebe die ID an die Logik-Funktion
            await run_configuration_logic(caller_id=task_id) # <--- MODIFIZIERT
            continue

        if os.path.exists(SCAN_TRIGGER_FILE):
            os.remove(SCAN_TRIGGER_FILE)
            # ... (Rest der Scan-Logik bleibt gleich) ...
            log("Manueller Scan getriggert...")
            try:
                cmd = ["iw", "dev", interface, "scan"]
                proc = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = await proc.communicate()
                if proc.returncode == 0:
                    log("Scan erfolgreich.")
                    output = stdout.decode('utf-8')
                    ssids = [line.split("SSID: ")[1] for line in output.split('\n') if "SSID: " in line and line.split("SSID: ")[1]]
                    with open(WIFI_LIST_FILE, 'w') as f:
                        json.dump(ssids, f)
                else:
                    log(f"FEHLER: 'iw scan' fehlgeschlagen. Fehler: {stderr.decode('utf-8')}")
            except Exception as e:
                log(f"Fehler während des Scans: {e}")

# --- API-Server-Handler (aus api_server.py) ---
async def handle_scan(request):
    with open(SCAN_TRIGGER_FILE, "w") as f: pass
    return web.Response(status=204)

# main.py

async def handle_configure(request):
    try:
        data = await request.json()
        # Schreibe die Aufgaben-Datei für die Schleife
        with open(TASK_FILE, "w") as f: json.dump(data, f)
        # Erstelle die Trigger-Datei, damit die Schleife es bemerkt
        with open(CONFIGURE_TRIGGER_FILE, "w") as f: pass
        
        # KEIN Aufruf von run_configuration_logic() hier!
        
        return web.Response(status=202) # Status 202 bedeutet "Accepted" (Anfrage angenommen)
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
    log(".....................................................................................................Add-on wird gestartet.......................................................................................................")

    if not os.path.exists(WIFI_LIST_FILE):
        log("wifi_list.json nicht gefunden, erstelle eine leere Datei.")
        with open(WIFI_LIST_FILE, "w") as f:
            json.dump([], f) # Schreibe ein leeres JSON-Array
    # --- NEUER BLOCK ENDE ---

    # Nginx starten
    log("Starte Nginx...")
    subprocess.Popen(["nginx"])
    
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