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

print("==== NEUSTART (WPA-Supplicant-Logik) ====")
print("==========================================")

CONFIGURE_LOCK = asyncio.Lock()

# --- Alle Konstanten an einem Ort ---
LOG_FILE = "/data/progress.log"
TASK_FILE = "/data/task.json"
CONFIG_PATH = "/data/options.json"
WIFI_LIST_FILE = "/var/www/wifi_list.json"
SCAN_TRIGGER_FILE = "/tmp/scan_now"
CONFIGURE_TRIGGER_FILE = "/tmp/configure_now"

# NEUE KONSTANTEN FÜR WPA-SUPPLICANT
WPA_SUPP_CONF = "/tmp/wpa_supplicant.conf"
WPA_SUPP_PID = "/tmp/wpa_supplicant.pid"
SHELLEY_AP_IP = "192.168.33.1"
ADDON_STATIC_IP = "192.168.33.2/24"


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

# --- MODIFIZIERTE Hilfsfunktion für wpa_supplicant Cleanup (mit Freigabe) ---
async def cleanup_wpa_supplicant(interface):
    log(f"Starte Cleanup für Schnittstelle {interface}...")
    
    # 0. Setze das Gerät manuell zurück/freigeben, um "Resource busy" zu vermeiden
    log(f"Setze Gerät {interface} auf Down und dann Up zur Freigabe...")
    await run_command(["ip", "link", "set", interface, "down"])
    await run_command(["ip", "link", "set", interface, "up"])
    await asyncio.sleep(1) 

    # 1. Stoppe wpa_supplicant Prozess
    if os.path.exists(WPA_SUPP_PID):
        try:
            with open(WPA_SUPP_PID, 'r') as f:
                pid = f.read().strip()
            if pid:
                log(f"Sende SIGTERM/SIGKILL an wpa_supplicant mit PID {pid}...")
                await run_command(["kill", "-9", pid])
        except Exception as e:
            log(f"Fehler beim Stoppen von wpa_supplicant: {e}")
        finally:
            if os.path.exists(WPA_SUPP_PID):
                os.remove(WPA_SUPP_PID)

    # 2. Entferne IP-Adresse (Flush)
    log(f"Setze IP-Adresse für {interface} zurück...")
    await run_command(["ip", "addr", "flush", "dev", interface])

    # 3. Entferne temporäre Konfigurationsdatei
    if os.path.exists(WPA_SUPP_CONF):
        os.remove(WPA_SUPP_CONF)
    
    await asyncio.sleep(2) # Kurze Pause nach dem Aufräumen


# --- Konfigurations-Logik (MODIFIZIERT) ---
async def run_configuration_logic(caller_id="unknown"):
    log(f"[{caller_id}] Versuch, die Konfigurations-Sperre zu bekommen...")
    
    async with CONFIGURE_LOCK:
        log(f"[{caller_id}] Sperre erhalten. Konfigurationsprozess wird jetzt exklusiv ausgeführt.")
        
        try:
            with open(LOG_FILE, 'w') as f: f.write('')
            log(f"[{caller_id}] Konfigurationsprozess gestartet...")

            with open(TASK_FILE, 'r') as f: task = json.load(f)
            with open(CONFIG_PATH, 'r') as f: config = json.load(f)
            
            selected_shellies = task.get("selectedShellies", [])
            user_ssid = task.get("userSsid", "")
            user_password = task.get("userPassword", "")
            interface = config.get("interface", "wlan0")

            if not user_ssid or not selected_shellies:
                log(f"[{caller_id}] FEHLER: Ungültige Aufgabendaten.")
                return

            # Initialer Cleanup
            await cleanup_wpa_supplicant(interface)
            
            encoded_ssid = quote(user_ssid)
            encoded_pass = quote(user_password)
            configure_url_base = f"http://{SHELLEY_AP_IP}/settings/sta?ssid={encoded_ssid}&key={encoded_pass}&enabled=1"

            for shelly_ssid in selected_shellies:
                log(f"[{caller_id}] --- Bearbeite: {shelly_ssid} ---")
                
                # --- 1. Konfiguration für wpa_supplicant erstellen ---
                wpa_config_content = f"""
ctrl_interface=/var/run/wpa_supplicant
network={{
    ssid="{shelly_ssid}"
    key_mgmt=NONE
}}
"""
                with open(WPA_SUPP_CONF, "w") as f:
                    f.write(wpa_config_content)

                log(f"[{caller_id}] Starte wpa_supplicant für Verbindung zu {shelly_ssid}...")
                
                # --- 2. wpa_supplicant starten und warten ---
                start_success = await run_command([
                    "wpa_supplicant",
                    "-i", interface,
                    "-c", WPA_SUPP_CONF,
                    "-B",                 # Im Hintergrund ausführen
                    "-P", WPA_SUPP_PID,   # PID-Datei schreiben
                    "-D", "nl80211",      # Treiber explizit setzen
                    "-N"                  # NEU: Deaktiviere P2P-Funktionen, um "Resource busy" zu vermeiden
                ])

                if not start_success:
                    log(f"[{caller_id}] FEHLER: Konnte wpa_supplicant nicht starten.")
                    await cleanup_wpa_supplicant(interface)
                    continue
                
                log(f"[{caller_id}] wpa_supplicant gestartet. Warte 10s auf Verbindung...")
                await asyncio.sleep(10) # Längere Wartezeit für die wpa-Verbindung

                # --- 3. Statische IP zuweisen (Shelly bietet kein DHCP im AP-Modus) ---
                log(f"[{caller_id}] Weise statische IP {ADDON_STATIC_IP} zu...")
                ip_config_success = await run_command([
                    "ip", "addr", "add", ADDON_STATIC_IP, "dev", interface
                ])
                
                if not ip_config_success:
                     log(f"[{caller_id}] FEHLER: Konnte die statische IP-Adresse nicht setzen.")
                     await cleanup_wpa_supplicant(interface)
                     continue
                
                await asyncio.sleep(8) # Längere Wartezeit für Stabilität und Netzwerk-Discovery
                
                # --- 4. Sende Konfigurationsbefehl (mit Retry) ---
                configure_url = configure_url_base
                success = False

                for attempt in range(3):
                    log(f"[{caller_id}] Sende Konfigurationsbefehl an Shelly (Versuch {attempt + 1})...")
                    try:
                        # Reduziertes Request-Timeout für schnelleren Retry
                        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session: 
                            async with session.get(configure_url) as response:
                                if response.status == 200:
                                    log(f"[{caller_id}] Befehl erfolgreich gesendet.")
                                    success = True
                                    break
                                else:
                                    raw_text = await response.text()
                                    log(f"[{caller_id}] FEHLER: Shelly-Antwort: Status {response.status}, Text: {raw_text[:100]}")
                    except Exception as e:
                        log(f"[{caller_id}] FEHLER beim Senden des HTTP-Befehls (Versuch {attempt + 1}): {e}")
                        
                    if not success and attempt < 2:
                        await asyncio.sleep(5) # Kurze Wartezeit vor dem nächsten Retry

                if not success:
                    log(f"[{caller_id}] KRITISCHER FEHLER: Konnte Shelly nach 3 Versuchen nicht konfigurieren.")
                
                # --- 5. Aufräumen der Verbindung ---
                log(f"[{caller_id}] Trenne Verbindung und bereinige wpa_supplicant...")
                await cleanup_wpa_supplicant(interface)
                
        except Exception as e:
            log(f"[{caller_id}] Ein unerwarteter Fehler ist aufgetreten: {e}")
            await cleanup_wpa_supplicant(interface)
        finally:
            log(f"[{caller_id}] --- Konfiguration abgeschlossen. ---")
            if os.path.exists(TASK_FILE): os.remove(TASK_FILE)
            log(f"[{caller_id}] Sperre wird freigegeben.")


# --- WLAN-Scan-Schleife (bleibt gleich) ---
async def wifi_scan_loop():
    log("WLAN Scan-Dienst gestartet. Warte auf Trigger...")
    config = json.load(open(CONFIG_PATH))
    interface = config.get("interface", "wlan0")

    while True:
        while not os.path.exists(SCAN_TRIGGER_FILE) and not os.path.exists(CONFIGURE_TRIGGER_FILE):
            await asyncio.sleep(1)

        if os.path.exists(CONFIGURE_TRIGGER_FILE):
            os.remove(CONFIGURE_TRIGGER_FILE)
            
            task_id = f"task_{random.randint(1000, 9999)}"
            
            await run_configuration_logic(caller_id=task_id)
            continue

        if os.path.exists(SCAN_TRIGGER_FILE):
            os.remove(SCAN_TRIGGER_FILE)
            
            log("Manueller Scan getriggert...")
            try:
                # iw scan ist die korrekte und direkte Methode
                cmd = ["iw", "dev", interface, "scan"]
                proc = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = await proc.communicate()
                if proc.returncode == 0:
                    log("Scan erfolgreich.")
                    output = stdout.decode('utf-8')
                    # HINWEIS: Die einfache SSID-Extraktion funktioniert nur mit iw in manchen Ausgaben
                    ssids = [line.split("SSID: ")[1] for line in output.split('\n') if "SSID: " in line and line.split("SSID: ")[1]]
                    with open(WIFI_LIST_FILE, 'w') as f:
                        json.dump(ssids, f)
                else:
                    log(f"FEHLER: 'iw scan' fehlgeschlagen. Fehler: {stderr.decode('utf-8')}")
            except Exception as e:
                log(f"Fehler während des Scans: {e}")

# --- API-Server-Handler (bleiben gleich) ---
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

# --- Haupt-Startfunktion (bleibt gleich) ---
async def start_background_tasks(app):
    app['wifi_scanner'] = asyncio.create_task(wifi_scan_loop())

async def main_startup():
    log(".........................................Add-on wird gestartet.........................................")

    if not os.path.exists(WIFI_LIST_FILE):
        log("wifi_list.json nicht gefunden, erstelle eine leere Datei.")
        with open(WIFI_LIST_FILE, "w") as f:
            json.dump([], f) 

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
    
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main_startup())
    except KeyboardInterrupt:
        log("Add-on wird gestoppt.")
