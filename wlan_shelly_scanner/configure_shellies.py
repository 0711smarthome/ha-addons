#!/usr/bin/env python3
import os
import json
import asyncio
import subprocess
import time
from urllib.parse import quote
import aiohttp

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

async def supervisor_api_post(session, url, data):
    """Sendet eine POST-Anfrage an die Supervisor API."""
    try:
        async with session.post(url, json=data, headers=HEADERS) as response:
            response_json = await response.json()
            if response.status >= 400:
                log(f"FEHLER bei API-Aufruf ({url}): {response_json.get('message')}")
                return None
            log("API-Befehl erfolgreich gesendet.")
            return response_json
    except Exception as e:
        log(f"Schwerer Fehler beim API-Aufruf: {e}")
        return None

async def get_current_ip(session, interface):
    """Holt die aktuelle IP-Adresse von der Supervisor API."""
    url = "http://supervisor/network/info"
    try:
        async with session.get(url, headers=HEADERS) as response:
            if response.status >= 400: return ""
            info = await response.json()
            for iface in info.get("data", {}).get("interfaces", []):
                if iface.get("interface") == interface:
                    ipv4 = iface.get("ipv4", {})
                    if ipv4 and ipv4.get("address"):
                        return ipv4.get("address")[0].split('/')[0]
    except Exception:
        return ""
    return ""

async def main():
    with open(LOG_FILE, 'w') as f: f.write('') # Log leeren
    log("Starte Python-Konfigurationsprozess...")

    try:
        with open(TASK_FILE, 'r') as f: task = json.load(f)
        with open(CONFIG_PATH, 'r') as f: config = json.load(f)
        
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

                if not await supervisor_api_post(session, api_url, options):
                    log(f"FEHLER beim Senden des Verbindungs-Befehls für {shelly_ssid}.")
                    continue

                log("Warte auf Verbindung (bis zu 45s)...")
                current_ip = ""
                for _ in range(15):
                    await asyncio.sleep(3)
                    current_ip = await get_current_ip(session, interface)
                    if current_ip and current_ip.startswith("192.168.33."):
                        break
                
                if current_ip and current_ip.startswith("192.168.33."):
                    log(f"Erfolgreich verbunden! IP: {current_ip}")
                    
                    url = f"http://192.168.33.1/settings/sta?ssid={quote(user_ssid)}&pass={quote(user_pass)}&enable=true"
                    log("Sende WLAN-Daten an Shelly...")
                    try:
                        subprocess.run(["curl", "-v", "--fail", "--max-time", "15", url], check=True, capture_output=True, text=True)
                        log("Erfolg! Shelly wurde konfiguriert.")
                    except subprocess.CalledProcessError as e:
                        log(f"FEHLER beim Senden der Konfiguration: {e.stderr}")
                else:
                    log(f"FEHLER: Verbindung fehlgeschlagen. Letzte IP: {current_ip}")

    except Exception as e:
        log(f"Ein unerwarteter Fehler ist aufgetreten: {e}")
    finally:
        log("--- Konfiguration abgeschlossen. ---")
        log("HINWEIS: Wiederherstellung der Host-Verbindung nicht implementiert. Bitte manuell prüfen.")
        if os.path.exists(TASK_FILE): os.remove(TASK_FILE)

if __name__ == "__main__":
    # Sperrdatei, um mehrfache Ausführung zu verhindern
    lock_fd = os.open('/tmp/configure.lock', os.O_CREAT | os.O_WRONLY)
    try:
        subprocess.check_call(['flock', '-n', str(lock_fd)])
        asyncio.run(main())
    except subprocess.CalledProcessError:
        log("Konfigurationsprozess läuft bereits.")
    finally:
        os.close(lock_fd)