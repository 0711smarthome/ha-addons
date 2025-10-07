#!/usr/bin/env python3
import os
import json
import asyncio
import subprocess
from urllib.parse import quote
import time

# Konstanten
LOG_FILE = "/data/progress.log"
TASK_FILE = "/data/task.json"
CONFIG_PATH = "/data/options.json"
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN")
HEADERS = {"Authorization": f"Bearer {SUPERVISOR_TOKEN}"}

def log(message):
    log_message = f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {message}"
    print(log_message)
    with open(LOG_FILE, "a") as f:
        f.write(log_message + "\n")

async def update_network(interface, options):
    """Sendet einen Befehl an die Supervisor Network API."""
    url = f"http://supervisor/network/interface/{interface}/update"
    try:
        proc = await asyncio.create_subprocess_exec(
            "curl", "-X", "POST", "-H", f"Authorization: Bearer {SUPERVISOR_TOKEN}",
            "-H", "Content-Type: application/json", "--data", json.dumps(options), url,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            log(f"FEHLER bei API-Aufruf: {stderr.decode()}")
            return False
        log("API-Befehl zur Netzwerk-Änderung erfolgreich gesendet.")
        return True
    except Exception as e:
        log(f"Schwerer Fehler beim API-Aufruf: {e}")
        return False

async def get_current_ip(interface):
    """Holt die aktuelle IP-Adresse von der Supervisor API."""
    url = "http://supervisor/network/info"
    try:
        proc = await asyncio.create_subprocess_exec(
            "curl", "-H", f"Authorization: Bearer {SUPERVISOR_TOKEN}", url,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0: return ""
        
        info = json.loads(stdout)
        for iface in info.get("data", {}).get("interfaces", []):
            if iface.get("interface") == interface:
                ipv4 = iface.get("ipv4", {})
                if ipv4.get("address"):
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

        for shelly_ssid in selected_shellies:
            log(f"--- Bearbeite: {shelly_ssid} ---")
            
            options = {"wifi": {"ssid": shelly_ssid, "auth": "open"}}
            if not await update_network(interface, options):
                log(f"FEHLER beim Senden des Verbindungs-Befehls für {shelly_ssid}.")
                continue

            log("Warte auf Verbindung (bis zu 45s)...")
            current_ip = ""
            for _ in range(15):
                await asyncio.sleep(3)
                current_ip = await get_current_ip(interface)
                if current_ip and current_ip.startswith("192.168.33."):
                    break
            
            if current_ip and current_ip.startswith("192.168.33."):
                log(f"Erfolgreich verbunden! IP: {current_ip}")
                
                url = f"http://192.168.33.1/settings/sta?ssid={quote(user_ssid)}&pass={quote(user_pass)}&enable=true"
                log("Sende WLAN-Daten an Shelly...")
                try:
                    subprocess.run(["curl", "-v", "--fail", "--max-time", "15", url], check=True, capture_output=True)
                    log("Erfolg! Shelly wurde konfiguriert.")
                except subprocess.CalledProcessError as e:
                    log(f"FEHLER beim Senden der Konfiguration: {e.stderr.decode()}")
            else:
                log(f"FEHLER: Verbindung fehlgeschlagen. Letzte IP: {current_ip}")

    except Exception as e:
        log(f"Ein unerwarteter Fehler ist aufgetreten: {e}")
    finally:
        log("--- Konfiguration abgeschlossen. ---")
        log("HINWEIS: WLAN-Verbindung des Hosts wird nicht automatisch zurückgesetzt. Bitte bei Bedarf manuell prüfen.")
        if os.path.exists(TASK_FILE): os.remove(TASK_FILE)

if __name__ == "__main__":
    asyncio.run(main())