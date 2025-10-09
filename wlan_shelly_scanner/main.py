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

async def run_configuration_logic():
    lock_file_path = '/tmp/configure.lock'
    try:
        with open(lock_file_path, 'w') as lf:
            fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with open(LOG_FILE, 'w') as f: f.write('') # Log leeren
            log("Konfigurationsprozess gestartet...")

            with open(TASK_FILE, 'r') as f: task = json.load(f)
            with open(CONFIG_PATH, 'r') as f: config = json.load(f)
            
            selected_shellies = task.get("selectedShellies", [])
            user_ssid = task.get("userSsid", "")
            user_password = task.get("userPassword", "") # Passwort auslesen
            interface = config.get("interface", "wlan0")

            if not user_ssid or not selected_shellies:
                log("FEHLER: Ungültige Aufgabendaten. SSID oder Shelly-Liste fehlt.")
                return

            # WICHTIG: NetworkManager muss laufen
            await run_command(["nmcli", "radio", "wifi", "on"])

            for shelly_ssid in selected_shellies:
                log(f"--- Bearbeite: {shelly_ssid} ---")
                
                # 1. Mit dem offenen Shelly WLAN verbinden
                log(f"Versuche Verbindung zu {shelly_ssid}...")
                # Wir löschen alte Verbindungen mit diesem Namen, falls vorhanden
                await run_command(["nmcli", "connection", "delete", shelly_ssid]) 
                connect_success = await run_command([
                    "nmcli", "device", "wifi", "connect", shelly_ssid, 
                    "name", shelly_ssid, # Gib der Verbindung denselben Namen wie der SSID
                    "ifname", interface
                ])

                if not connect_success:
                    log(f"FEHLER: Konnte keine Verbindung zu {shelly_ssid} herstellen. Überspringe.")
                    continue
                
                # Kurze Pause, damit der DHCP-Server des Shelly eine IP zuweisen kann
                await asyncio.sleep(10)

                # 2. HTTP-Befehl an den Shelly senden
                # Shellies im AP-Modus haben immer die IP 192.168.33.1
                shelly_ip = "192.168.33.1"
                # URL-encodieren von SSID und Passwort
                encoded_ssid = quote(user_ssid)
                encoded_pass = quote(user_password)
                
                # Der genaue API-Endpunkt kann je nach Shelly-Firmware variieren.
                # Dies ist der häufigste für Gen1-Geräte.
                configure_url = (
                    f"http://{shelly_ip}/settings/sta?"
                    f"ssid={encoded_ssid}&"
                    f"key={encoded_pass}&"
                    "enabled=1"
                )

                log(f"Sende Konfigurationsbefehl an {configure_url}")
                try:
                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
                        async with session.get(configure_url) as response:
                            if response.status == 200:
                                log("Konfigurationsbefehl erfolgreich gesendet.")
                            else:
                                log(f"FEHLER: Shelly hat mit Status {response.status} geantwortet.")
                except Exception as e:
                    log(f"FEHLER beim Senden des HTTP-Befehls: {e}")
                
                finally:
                    # 3. Verbindung zum Shelly trennen, egal was passiert
                    log(f"Trenne Verbindung zu {shelly_ssid}...")
                    await run_command(["nmcli", "connection", "down", shelly_ssid])
                    await run_command(["nmcli", "connection", "delete", shelly_ssid])
                    log("Verbindung getrennt.")

    except IOError:
        log("Konfigurationsprozess läuft bereits (Lock-Datei vorhanden).")
    except Exception as e:
        log(f"Ein unerwarteter Fehler im Konfigurationsprozess ist aufgetreten: {e}")
    finally:
        log("--- Konfiguration abgeschlossen. ---")
        if os.path.exists(TASK_FILE): os.remove(TASK_FILE)
        
# --- WLAN-Scan-Schleife (aus run.sh) ---
# main.py

async def wifi_scan_loop():
    log("WLAN Scan-Dienst gestartet. Warte auf Trigger...")
    config = json.load(open(CONFIG_PATH))
    interface = config.get("interface", "wlan0")

    while True:
        # Warte, bis eine der Trigger-Dateien erscheint
        while not os.path.exists(SCAN_TRIGGER_FILE) and not os.path.exists(CONFIGURE_TRIGGER_FILE):
            await asyncio.sleep(1)

        # Wenn die Konfiguration getriggert wird, hat diese Vorrang
        if os.path.exists(CONFIGURE_TRIGGER_FILE):
            os.remove(CONFIGURE_TRIGGER_FILE)
            # DIES ist der EINZIGE Ort, an dem die Logik aufgerufen wird.
            await run_configuration_logic() 
            continue # Gehe zum Anfang der Schleife und warte erneut

        # Ansonsten führe einen Scan aus
        if os.path.exists(SCAN_TRIGGER_FILE):
            os.remove(SCAN_TRIGGER_FILE)
            log("Manueller Scan getriggert...")
            try:
                cmd = ["iw", "dev", interface, "scan"]
                proc = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = await proc.communicate()

                if proc.returncode == 0:
                    log("Scan erfolgreich.")
                    output = stdout.decode('utf-8')
                    # Extrahiere nur SSIDs, die nicht leer sind
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
    log(".....................................................................................................Add-on wird gestartet...")
    log(f"DEBUG: Supervisor Token vorhanden: {'Ja' if SUPERVISOR_TOKEN else 'Nein'}")
    if SUPERVISOR_TOKEN:
        log(f"DEBUG: Token beginnt mit: {SUPERVISOR_TOKEN[:5]}, endet mit: {SUPERVISOR_TOKEN[-5:]}")

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