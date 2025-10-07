#!/usr/bin/env python3
import os
import json
import asyncio
import subprocess
import time
from urllib.parse import quote
import aiohttp
import fcntl

# Konstanten
LOG_FILE = "/data/progress.log"
TASK_FILE = "/data/task.json"
CONFIG_PATH = "/data/options.json"
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN")
HEADERS = {"Authorization": f"Bearer {SUPERVISOR_TOKEN}"}

def log(message):
    log_message = f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {message}"
    print(log_message)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_message + "\n")

async def supervisor_api_request(session, method, url, data=None):
    """Führt eine allgemeine Anfrage an die Supervisor API aus und gibt die Antwort zurück."""
    try:
        async with session.request(method, url, json=data, headers=HEADERS, timeout=40) as response:
            # --- DEBUGGING-ÄNDERUNG START ---
            raw_text = await response.text()
            try:
                # Versuche, die Antwort als JSON zu parsen
                response_json = json.loads(raw_text)
            except json.JSONDecodeError:
                # Wenn das Parsen fehlschlägt, logge die Roh-Antwort
                log("!!!!!!!!!! JSON PARSE FEHLER !!!!!!!!!!!")
                log(f"API-Antwort (Status: {response.status}) war kein gültiges JSON.")
                log(f"ROH-ANTWORT: >>>{raw_text}<<<")
                log("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                return None
            # --- DEBUGGING-ÄNDERUNG ENDE ---

            if response.status >= 400:
                log(f"FEHLER bei API-Aufruf ({url}): {response_json.get('message')}")
                return None
            
            return response_json
            
    except Exception as e:
        log(f"Schwerer Fehler beim API-Aufruf: {e}")
        return None

async def main():
    with open(LOG_FILE, 'w') as f: f.write('') # Log leeren
    log("Starte Python-Konfigurationsprozess...")

    # --- NEUE DEBUG-ZEILE HINZUFÜGEN ---
    log(f"DEBUG: Supervisor Token vorhanden: {'Ja' if SUPERVISOR_TOKEN else 'Nein'}")
    if SUPERVISOR_TOKEN:
        log(f"DEBUG: Token beginnt mit: {SUPERVISOR_TOKEN[:5]}, endet mit: {SUPERVISOR_TOKEN[-5:]}")
    # --- ENDE DEBUG-ZEILE ---    

    try:
        # Prüfen, ob die Datei existiert und nicht leer ist
        if not os.path.exists(TASK_FILE) or os.path.getsize(TASK_FILE) == 0:
            log(f"FEHLER: Aufgabendatei ({TASK_FILE}) ist leer oder existiert nicht.")
            return # Beendet das Skript hier

        with open(TASK_FILE, 'r') as f: task = json.load(f)
        with open(CONFIG_PATH, 'r') as f: config = json.load(f)
        
        # ... (Rest der main-Funktion bleibt gleich, nutzt jetzt aber supervisor_api_request)
        selected_shellies = task.get("selectedShellies", [])
        user_ssid = task.get("userSsid", "")
        user_pass = task.get("userPassword", "")
        interface = config.get("interface", "wlan0")

        if not user_ssid or not selected_shellies:
            log("FEHLER: Ungültige Aufgabendaten.")
            return

        async with aiohttp.ClientSession() as session:
            for shelly_ssid in selected_shellies:
                log(f"--- Bearbeite: {shelly_ssid} ---")
                
                options = {"ipv4": {"method": "auto"}, "wifi": {"ssid": shelly_ssid, "auth": "open"}}
                api_url = f"http://supervisor/network/interface/{interface}/update"

                if not await supervisor_api_request(session, 'post', api_url, options):
                    log(f"FEHLER beim Senden des Verbindungs-Befehls für {shelly_ssid}.")
                    continue

                log("Warte auf Verbindung (bis zu 45s)...")
                current_ip = ""
                for _ in range(15):
                    await asyncio.sleep(3)
                    info_url = "http://supervisor/network/info"
                    network_info = await supervisor_api_request(session, 'get', info_url)
                    if network_info:
                        for iface in network_info.get("data", {}).get("interfaces", []):
                            if iface.get("interface") == interface:
                                ipv4 = iface.get("ipv4", {})
                                if ipv4 and ipv4.get("address"):
                                    current_ip = ipv4.get("address")[0].split('/')[0]
                                    if current_ip.startswith("192.168.33."): break
                        if current_ip.startswith("192.168.33."): break
                
                if current_ip and current_ip.startswith("192.168.33."):
                    log(f"Erfolgreich verbunden! IP: {current_ip}")
                    # ... (curl-Teil bleibt unverändert)
                else:
                    log(f"FEHLER: Verbindung fehlgeschlagen. Letzte IP: {current_ip}")

    except json.JSONDecodeError as e:
        log(f"FEHLER beim Parsen der JSON-Aufgabendatei: {e}")
    except Exception as e:
        log(f"Ein unerwarteter Fehler ist aufgetreten: {e}")
    finally:
        log("--- Konfiguration abgeschlossen. ---")
        log("HINWEIS: Wiederherstellung der Host-Verbindung nicht implementiert.")
        if os.path.exists(TASK_FILE): os.remove(TASK_FILE)

if __name__ == "__main__":
    lock_file_path = '/tmp/configure.lock'
    with open(lock_file_path, 'w') as lf:
        try:
            fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
            asyncio.run(main())
        except IOError:
            log("Konfigurationsprozess läuft bereits.")