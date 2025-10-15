#!/usr/bin/env python3
# coding: utf-8
import os
import sys
import json
import asyncio
import subprocess
import time
from urllib.parse import quote
from typing import List, Optional, Dict, Any

import aiohttp
from aiohttp import web
import fcntl
import random

print("==== NEUSTART ====")
print("======================")

# --- Globale Konstanten und Sperren ---
LOG_FILE = "/data/progress.log"
TASK_FILE = "/data/task.json"
CONFIG_PATH = "/data/options.json"
WIFI_LIST_FILE = "/var/www/wifi_list.json"
SCAN_TRIGGER_FILE = "/tmp/scan_now"
CONFIGURE_TRIGGER_FILE = "/tmp/configure_now"

CONFIGURE_LOCK = asyncio.Lock()

# --- Token-Management (wird nur einmal beim Start gelesen) ---
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN")
HEADERS = {"Authorization": f"Bearer {SUPERVISOR_TOKEN}"}

# --- Hilfsfunktionen ---

def log(message: str) -> None:
    """Schreibt eine Nachricht ins Add-on-Log und in eine Log-Datei."""
    log_message = f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {message}"
    print(log_message, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_message + "\n")
    except Exception as e:
        print(f"Error writing to log file: {e}", flush=True)

async def run_command(cmd: List[str]) -> (bool, str, str):
    """
    Führt einen externen Befehl aus, loggt ihn und gibt Erfolg, stdout und stderr zurück.
    """
    log(f"Führe aus: {' '.join(cmd)}")
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()

    stdout_str = stdout.decode('utf-8').strip()
    stderr_str = stderr.decode('utf-8').strip()

    if stdout_str:
        log(f"Ausgabe: {stdout_str}")
    if stderr_str:
        log(f"Fehler-Ausgabe: {stderr_str}")

    return proc.returncode == 0, stdout_str, stderr_str

async def wait_for_connection(interface: str, timeout: int = 45) -> bool:
    """
    Wartet, bis die Schnittstelle eine aktive Verbindung mit einer IPv4-Adresse hat.
    """
    log(f"Warte auf aktive Verbindung und IP-Adresse für '{interface}'...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        # Prüfen, ob eine IP-Adresse zugewiesen wurde. Der Shelly vergibt 192.168.33.x
        success, stdout, _ = await run_command(["nmcli", "-g", "IP4.ADDRESS", "dev", "show", interface])
        if success and '192.168.33' in stdout:
            log(f"Erfolgreich verbunden! IP-Adresse: {stdout.split('/')[0]}")
            return True
        await asyncio.sleep(2) # Alle 2 Sekunden prüfen

    log(f"FEHLER: Timeout nach {timeout}s. Keine gültige IP-Adresse für '{interface}' erhalten.")
    return False


# --- Kernlogik ---

async def run_configuration_logic(caller_id: str) -> None:
    """
    Hauptlogik zur Konfiguration der Shellies. Wird exklusiv durch einen Lock ausgeführt.
    """
    log(f"[{caller_id}] Versuch, die Konfigurations-Sperre zu bekommen...")
    async with CONFIGURE_LOCK:
        log(f"[{caller_id}] Sperre erhalten. Konfigurationsprozess wird jetzt exklusiv ausgeführt.")
        
        successful_shellies = []
        failed_shellies = []

        try:
            with open(LOG_FILE, 'w') as f: f.write('')  # Log leeren
            log(f"[{caller_id}] Konfigurationsprozess gestartet...")

            with open(TASK_FILE, 'r') as f: task = json.load(f)
            with open(CONFIG_PATH, 'r') as f: config = json.load(f)

            selected_shellies = task.get("selectedShellies", [])
            user_ssid = task.get("userSsid", "")
            user_password = task.get("userPassword", "")
            interface = config.get("interface", "wlan0")

            if not user_ssid or not selected_shellies:
                log(f"[{caller_id}] FEHLER: Ungültige Aufgabendaten (SSID oder Shellies fehlen).")
                return

            await run_command(["nmcli", "radio", "wifi", "on"])

            for shelly_ssid in selected_shellies:
                log(f"[{caller_id}] --- Bearbeite: {shelly_ssid} ---")
                
                await run_command(["nmcli", "connection", "delete", shelly_ssid])
                
                log(f"[{caller_id}] Versuche Verbindung zu {shelly_ssid}...")
                connect_success, _, _ = await run_command([
                    "nmcli", "device", "wifi", "connect", shelly_ssid,
                    "name", shelly_ssid, "ifname", interface
                ])

                if not connect_success:
                    log(f"[{caller_id}] FEHLER: Der Verbindungsaufbau zu {shelly_ssid} schlug fehl.")
                    failed_shellies.append(shelly_ssid)
                    continue
                
                if not await wait_for_connection(interface):
                    log(f"[{caller_id}] FEHLER: Konnte keine stabile Verbindung zu {shelly_ssid} herstellen.")
                    failed_shellies.append(shelly_ssid)
                    await run_command(["nmcli", "connection", "delete", shelly_ssid])
                    continue

                # Ab hier ist die Verbindung aktiv und hat eine IP
                shelly_ip = "192.168.33.1"

                # ####################################################################
                # ### START DER ÄNDERUNG: Gen2-Befehl korrekt zusammenbauen ###
                # ####################################################################

                # 1. Erstelle das Konfigurations-Objekt als Python Dictionary
                config_payload = {
                    "config": {
                        "sta": {
                            "ssid": user_ssid,
                            "pass": user_password,
                            "enable": True
                        }
                    }
                }

                # 2. Wandle das Dictionary in einen JSON-String um
                config_json_string = json.dumps(config_payload)
                
                # 3. URL-kodiere den JSON-String, um ihn sicher in der URL zu verwenden
                # HINWEIS: Laut Doku wird der gesamte JSON-Block als Wert für den "config"-Parameter erwartet.
                # Wir bauen hier aber den RPC-Aufruf nach, wie er in der URL steht.
                
                rpc_payload = {
                    "sta":{
                        "ssid": user_ssid,
                        "pass": user_password,
                        "enable": True
                    }
                }
                encoded_config = quote(json.dumps(rpc_payload))
                
                # 4. Baue die finale URL zusammen
                configure_url = f"http://{shelly_ip}/rpc/WiFi.SetConfig?config={encoded_config}"
                
                log(f"[{caller_id}] Sende Gen2-Konfigurationsbefehl an {shelly_ip}...")

                # ####################################################################
                # ### ENDE DER ÄNDERUNG                                            ###
                # ####################################################################
                
                try:
                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
                        async with session.get(configure_url) as response:
                            response_text = await response.text()
                            if response.status == 200:
                                log(f"[{caller_id}] Befehl für {shelly_ssid} erfolgreich gesendet. Antwort: {response_text}")
                                successful_shellies.append(shelly_ssid)
                            else:
                                log(f"[{caller_id}] FEHLER bei {shelly_ssid}: Shelly-Antwort: {response.status}, Text: {response_text}")
                                failed_shellies.append(shelly_ssid)
                except Exception as e:
                    log(f"[{caller_id}] FEHLER beim Senden des HTTP-Befehls für {shelly_ssid}: {e}")
                    failed_shellies.append(shelly_ssid)
                finally:
                    log(f"[{caller_id}] Trenne Verbindung zu {shelly_ssid}...")
                    await run_command(["nmcli", "connection", "down", shelly_ssid])
                    await run_command(["nmcli", "connection", "delete", shelly_ssid])
                    log(f"[{caller_id}] Verbindung getrennt.")
        
        except Exception as e:
            log(f"[{caller_id}] Ein unerwarteter, schwerer Fehler ist aufgetreten: {e}")
        finally:
            log("--- Konfiguration abgeschlossen ---")
            if successful_shellies: log(f"Erfolgreich: {len(successful_shellies)} Geräte ({', '.join(successful_shellies)})")
            if failed_shellies: log(f"Fehlgeschlagen: {len(failed_shellies)} Geräte ({', '.join(failed_shellies)})")
            if os.path.exists(TASK_FILE): os.remove(TASK_FILE)
            log(f"[{caller_id}] Sperre wird freigegeben.")
            

async def scan_wifi_networks(interface: str) -> (bool, List[str], str):
    """
    Scannt nach WLAN-Netzwerken und gibt (Erfolg, [SSID-Liste], "Fehlermeldung") zurück.
    """
    log("Scan wird ausgelöst...")
    try:
        # --rescan yes erzwingt einen frischen Scan
        success, stdout, stderr = await run_command([
            "nmcli", "-f", "SSID", "dev", "wifi", "list", "--rescan", "yes"
        ])

        if success:
            log("Scan erfolgreich.")
            lines = stdout.strip().split('\n')
            # Filtere leere Zeilen und den Header 'SSID' heraus
            ssids = [line.strip() for line in lines if line.strip() and line.strip() != 'SSID']
            
            # Die Datei wird weiterhin geschrieben, falls sie für eine spätere Funktion nützlich ist
            with open(WIFI_LIST_FILE, 'w') as f:
                json.dump(ssids, f)
            
            return True, ssids, ""
        else:
            log(f"FEHLER: 'nmcli scan' fehlgeschlagen. Fehler: {stderr}")
            return False, [], stderr
            
    except Exception as e:
        log(f"Fehler während des Scans: {e}")
        return False, [], str(e)


async def background_worker_loop() -> None:
    """
    Endlosschleife, die auf Trigger-Dateien für die Konfiguration wartet.
    """
    log("Hintergrund-Dienst gestartet. Warte auf Konfigurations-Trigger...")
    with open(CONFIG_PATH) as f:
        config = json.load(f)
    interface = config.get("interface", "wlan0")

    while True:
        if os.path.exists(CONFIGURE_TRIGGER_FILE):
            os.remove(CONFIGURE_TRIGGER_FILE)
            task_id = f"task_{random.randint(1000, 9999)}"
            asyncio.create_task(run_configuration_logic(caller_id=task_id))

        await asyncio.sleep(1)


# --- API-Server ---

async def handle_scan(request: web.Request) -> web.Response:
    """Führt einen Scan aus und gibt das Ergebnis direkt als JSON zurück."""
    with open(CONFIG_PATH) as f:
        config = json.load(f)
    interface = config.get("interface", "wlan0")

    success, ssids, error_message = await scan_wifi_networks(interface)

    if success:
        return web.json_response(ssids)
    else:
        return web.json_response({"error": "Scan fehlgeschlagen", "details": error_message}, status=500)

async def handle_configure(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        with open(TASK_FILE, "w") as f: json.dump(data, f)
        with open(CONFIGURE_TRIGGER_FILE, "w") as f: pass
        return web.Response(status=202)
    except Exception as e:
        log(f"API Fehler /api/configure: {e}")
        return web.Response(status=500)

async def handle_progress(request: web.Request) -> web.Response:
    try:
        with open(LOG_FILE, "r") as f: content = f.read()
        return web.Response(text=content, content_type="text/plain", charset="utf-8")
    except FileNotFoundError:
        return web.Response(text="Log-Datei noch nicht vorhanden.", status=200)

# --- Haupt-Startfunktion ---

async def start_background_tasks(app: web.Application) -> None:
    app['background_worker'] = asyncio.create_task(background_worker_loop())

async def main_startup() -> None:
    log(".........................................Add-on wird gestartet.........................................")

    if not os.path.exists(WIFI_LIST_FILE):
        log("wifi_list.json nicht gefunden, erstelle eine leere Datei.")
        with open(WIFI_LIST_FILE, "w") as f: json.dump([], f)

    app = web.Application()
    app.on_startup.append(start_background_tasks)
    app.router.add_get("/api/scan", handle_scan)
    app.router.add_post("/api/configure", handle_configure)
    app.router.add_get("/api/progress", handle_progress)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8888)
    await site.start()
    log("API-Server läuft auf Port 8888")
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main_startup())
    except KeyboardInterrupt:
        log("Add-on wird gestoppt.")