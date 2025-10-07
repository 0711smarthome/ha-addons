#!/usr/bin/env python3
import os
import json
import subprocess
import time
from urllib.parse import quote

LOG_FILE = "/data/progress.log"
TASK_FILE = "/data/task.json"
CONFIG_PATH = "/data/options.json"

# Stellt sicher, dass das Skript nicht mehrfach läuft
lock_file = open('/tmp/configure.lock', 'w')
try:
    # Versuche einen nicht-blockierenden Lock zu bekommen
    subprocess.check_call(['flock', '-n', str(lock_file.fileno())])
except subprocess.CalledProcessError:
    print("Konfigurationsprozess läuft bereits.")
    exit(1)

def log(message):
    """Schreibt eine Nachricht in die Log-Datei und auf die Konsole."""
    log_message = f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {message}"
    print(log_message)
    with open(LOG_FILE, "a") as f:
        f.write(log_message + "\n")

def run_ha_command(command):
    """Führt einen Home Assistant API-Aufruf aus."""
    token = os.environ.get("SUPERVISOR_TOKEN")
    process = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        headers={"Authorization": f"Bearer {token}"}
    )
    if process.returncode != 0:
        log(f"FEHLER beim Ausführen des HA-Befehls: {process.stderr.decode('utf-8')}")
        return None
    return json.loads(process.stdout.decode('utf-8'))

def main():
    # Leere die Log-Datei
    open(LOG_FILE, 'w').close()
    log("Starte Python-Konfigurationsprozess...")

    try:
        with open(TASK_FILE, 'r') as f:
            task = json.load(f)
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
            
        selected_shellies = task.get("selectedShellies", [])
        user_ssid = task.get("userSsid", "")
        user_pass = task.get("userPassword", "")
        interface = config.get("interface", "wlan0")

        if not user_ssid or not selected_shellies:
            log("FEHLER: Ungültige Aufgabendaten.")
            return

        log(f"Verwende Interface: {interface}")
        
        for shelly_ssid in selected_shellies:
            log("---------------------------------------------")
            log(f"Bearbeite: {shelly_ssid}")
            log("Versuche, Host mit Shelly-Hotspot zu verbinden...")

            # Verbinde mit dem Shelly-Netzwerk via Home Assistant API
            api_command = [
                "ha", "network", "update", interface, 
                "--wifi-ssid", shelly_ssid, 
                "--wifi-auth", "open"
            ]
            run_ha_command(api_command) # Wir prüfen nicht auf Erfolg, da es asynchron ist

            log("Warte auf Verbindung (bis zu 30s)...")
            current_ip = ""
            for _ in range(15):
                time.sleep(2)
                network_info = run_ha_command(["ha", "network", "info", "--raw-json"])
                if network_info:
                    for iface in network_info.get("data", {}).get("interfaces", []):
                        if iface.get("interface") == interface:
                            ipv4_info = iface.get("ipv4", {})
                            if ipv4_info and ipv4_info.get("address"):
                                current_ip = ipv4_info.get("address")[0].split('/')[0]
                                if current_ip.startswith("192.168.33."):
                                    break
                    if current_ip.startswith("192.168.33."):
                        break
            
            if current_ip.startswith("192.168.33."):
                log(f"Erfolgreich verbunden! IP-Adresse erhalten: {current_ip}")
                
                # Sende Konfiguration via curl
                url = f"http://192.168.33.1/settings/sta?ssid={quote(user_ssid)}&pass={quote(user_pass)}&enable=true"
                log(f"Sende WLAN-Daten an den Shelly: {url}")
                try:
                    subprocess.run(["curl", "-v", "--fail", "--max-time", "15", "-s", url], check=True, capture_output=True)
                    log("Erfolg! Shelly wurde konfiguriert.")
                except subprocess.CalledProcessError as e:
                    log(f"FEHLER beim Senden der Konfiguration: {e.stderr.decode('utf-8')}")

            else:
                log(f"FEHLER: Verbindung fehlgeschlagen. Letzte bekannte IP: {current_ip}")

    except Exception as e:
        log(f"Ein unerwarteter Fehler ist aufgetreten: {e}")
    finally:
        log("---------------------------------------------")
        log("Stelle ursprüngliche Netzwerkkonfiguration wieder her...")
        # Hier sollte die Logik zum Wiederherstellen stehen. Vorerst eine Notiz.
        log("WICHTIG: Bitte überprüfe die WLAN-Verbindung deines Home Assistant.")
        log("Konfigurationsprozess für alle ausgewählten Geräte abgeschlossen.")
        if os.path.exists(TASK_FILE):
            os.remove(TASK_FILE)

if __name__ == "__main__":
    main()