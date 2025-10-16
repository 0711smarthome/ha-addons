#!/usr/bin/env python3
# coding: utf-8
import os
import sys
import json
import asyncio
import subprocess
import time
import re
import base64
from itertools import cycle
from urllib.parse import quote
from typing import List, Optional, Dict, Any
import aiohttp
from aiohttp import web
from zeroconf import ServiceBrowser, Zeroconf
import socket

print("==== NEUSTART des Add-ons ====")

# --- Globale Konstanten und Sperren ---
LOG_FILE = "/data/progress.log"
TASK_FILE = "/data/task.json"
CONFIG_PATH = "/data/options.json"
ADMIN_DEVICES_FILE = "/data/shelly_devices.json.enc"
CONFIGURE_LOCK = asyncio.Lock()
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN")
HEADERS = {"Authorization": f"Bearer {SUPERVISOR_TOKEN}"}

# --- Hilfsfunktionen ---
def log(message: str) -> None:
    log_message = f"[{time.strftime('%H:%M:%S')}] {message}"
    print(log_message, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_message + "\n")
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] FEHLER beim Schreiben der Log-Datei: {e}", flush=True)

def xor_crypt(data: bytes, key: str) -> bytes:
    if not key: return data
    key_bytes = key.encode('utf-8')
    return bytes([b ^ k for b, k in zip(data, cycle(key_bytes))])

def parse_shelly_ssid(ssid: str) -> (Optional[str], Optional[str], Optional[str]):
    gen234_match = re.match(r'^(Shelly([a-zA-Z0-9\-\_]+))-([0-9A-F]{12})$', ssid, re.IGNORECASE)
    if gen234_match:
        return "Gen 2/3/4", f"Shelly {gen234_match.group(2)}", gen234_match.group(3)
    gen1_match = re.match(r'^(shelly([a-zA-Z0-9\-\_]+))-([0-9A-F]{6})$', ssid, re.IGNORECASE)
    if gen1_match:
        return "Gen 1", f"Shelly {gen1_match.group(2)}", gen1_match.group(3)
    return None, None, None

async def run_command(cmd: List[str]) -> (bool, str, str):
    log(f"DEBUG: Führe Befehl aus: {' '.join(cmd)}")
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = await proc.communicate()
    stdout_str, stderr_str = stdout.decode('utf-8').strip(), stderr.decode('utf-8').strip()
    # Logge nur, wenn es eine relevante Ausgabe gibt
    if stdout_str: log(f"DEBUG: Ausgabe von '{cmd[0]}': {stdout_str}")
    if stderr_str: log(f"DEBUG: Fehler-Ausgabe von '{cmd[0]}': {stderr_str}")
    return proc.returncode == 0, stdout_str, stderr_str

async def wait_for_connection(interface: str, timeout: int = 45) -> bool:
    log(f"INFO: Warte auf IP-Adresse für '{interface}' (max. {timeout}s)...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        success, stdout, _ = await run_command(["nmcli", "-g", "IP4.ADDRESS", "dev", "show", interface])
        if success and '192.168.33' in stdout:
            log(f"ERFOLG: IP-Adresse {stdout.split('/')[0]} erhalten.")
            return True
        await asyncio.sleep(2)
    log(f"FEHLER: Timeout bei der IP-Adressvergabe für '{interface}'.")
    return False

# --- Kernlogik ---
async def run_configuration_logic(caller_id: str) -> None:
    log(f"INFO: Konfigurations-Task {caller_id} gestartet.")
    if not await CONFIGURE_LOCK.acquire():
        log("WARNUNG: Konfigurations-Lock konnte nicht erhalten werden. Breche ab.")
        return
    
    log("INFO: Konfigurations-Sperre erhalten.")
    successful_shellies, failed_shellies = [], []
    try:
        with open(LOG_FILE, 'w') as f: f.write('')
        log("INFO: Konfigurations-Log zurückgesetzt.")
        with open(TASK_FILE, 'r') as f: task = json.load(f)
        with open(CONFIG_PATH, 'r') as f: config = json.load(f)

        selected_devices = task.get("selectedDevices", [])
        user_ssid, user_password = task.get("userSsid", ""), task.get("userPassword", "")
        interface = config.get("interface", "wlan0")
        log(f"DEBUG: Task-Daten geladen: {len(selected_devices)} Geräte, SSID '{user_ssid}', Interface '{interface}'")

        if not user_ssid or not selected_devices:
            log("FEHLER: Ungültige Task-Daten. SSID oder Geräte fehlen.")
            return

        for device in selected_devices:
            shelly_ssid = device.get("ssid")
            generation = device.get("generation", "Gen 1")
            if not shelly_ssid:
                log(f"WARNUNG: Überspringe Gerät ohne SSID: {device}")
                continue

            log(f"--- Starte Verarbeitung für: {shelly_ssid} (Gen: {generation}) ---")
            await run_command(["nmcli", "connection", "delete", shelly_ssid])
            log(f"INFO: Versuche, Verbindung zu '{shelly_ssid}' herzustellen...")
            connect_success, _, _ = await run_command(["nmcli", "device", "wifi", "connect", shelly_ssid, "name", shelly_ssid, "ifname", interface])

            if not connect_success or not await wait_for_connection(interface):
                log(f"FEHLER: Verbindung zu {shelly_ssid} fehlgeschlagen.")
                failed_shellies.append(shelly_ssid)
                await run_command(["nmcli", "connection", "delete", shelly_ssid])
                continue

            shelly_ip = "192.168.33.1"
            configure_url = ""

            if "Gen 1" in generation:
                log("DEBUG: Baue Gen1-Konfigurations-URL...")
                encoded_ssid, encoded_pass = quote(user_ssid), quote(user_password)
                configure_url = f"http://{shelly_ip}/settings/sta?ssid={encoded_ssid}&pass={encoded_pass}&enable=1"
            else:
                log("DEBUG: Baue Gen2+-Konfigurations-URL...")
                rpc_payload = {"sta": {"ssid": user_ssid, "pass": user_password, "enable": True}}
                encoded_config = quote(json.dumps(rpc_payload))
                configure_url = f"http://{shelly_ip}/rpc/WiFi.SetConfig?config={encoded_config}"
            log(f"DEBUG: Finale URL: {configure_url.replace(quote(user_password), '********')}")

            try:
                log(f"INFO: Sende Konfigurationsbefehl an {shelly_ip}...")
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
                    async with session.get(configure_url) as response:
                        response_text = await response.text()
                        if response.status == 200:
                            log(f"ERFOLG: Befehl für {shelly_ssid} erfolgreich. Antwort: {response_text}")
                            successful_shellies.append(shelly_ssid)
                        else:
                            log(f"FEHLER bei {shelly_ssid}: Shelly-Antwort: Status {response.status}, Text: {response_text}")
                            failed_shellies.append(shelly_ssid)
            except Exception as e:
                log(f"FEHLER beim Senden des HTTP-Befehls für {shelly_ssid}: {e}")
                failed_shellies.append(shelly_ssid)
            finally:
                log(f"INFO: Trenne Verbindung zu {shelly_ssid}...")
                await run_command(["nmcli", "connection", "down", shelly_ssid])
                await run_command(["nmcli", "connection", "delete", shelly_ssid])
    except Exception as e:
        log(f"FATAL: Ein unerwarteter Fehler ist im Konfigurationsprozess aufgetreten: {e}")
    finally:
        log("--- Konfiguration abgeschlossen ---")
        if successful_shellies: log(f"ERFOLGSBILANZ: {len(successful_shellies)} Geräte ({', '.join(successful_shellies)})")
        if failed_shellies: log(f"FEHLERBILANZ: {len(failed_shellies)} Geräte ({', '.join(failed_shellies)})")
        if os.path.exists(TASK_FILE): os.remove(TASK_FILE)
        CONFIGURE_LOCK.release()
        log("INFO: Konfigurations-Sperre freigegeben.")
        

async def scan_wifi_networks(interface: str, existing_macs: List[str] = None) -> (bool, List[Dict[str, Any]], List[str], str):
    """Scannt nach WLANs, parst Shelly-SSIDs und ignoriert bereits bekannte MACs."""
    if existing_macs is None: existing_macs = []
    log_entries, found_devices = [], []
    log_entries.append(f"Starte WLAN-Scan auf Interface '{interface}'...")
    try:
        success, stdout, stderr = await run_command(["nmcli", "-f", "SSID", "dev", "wifi", "list", "--rescan", "yes"])
        if not success:
            msg = f"FEHLER: 'nmcli scan' fehlgeschlagen. Fehler: {stderr}"
            log(msg); log_entries.append(msg)
            return False, [], log_entries, stderr
        lines = stdout.strip().split('\n')[1:]
        log_entries.append(f"Scan abgeschlossen. {len(lines)} Netzwerke gefunden.")
        for line in lines:
            ssid = line.strip()
            if not ssid or ssid == '--': continue
            log_entries.append(f"- Gefundenes WLAN: '{ssid}'")
            generation, model, mac = parse_shelly_ssid(ssid)
            if mac:
                if mac not in existing_macs:
                    log_entries.append(f"  -> Shelly erkannt! Gen: {generation}, Modell: {model}, MAC: {mac}")
                    found_devices.append({"mac": mac, "ssid": ssid, "generation": generation, "model": model, "bemerkung": "", "haName": "", "lastConfigured": ""})
                else:
                    log_entries.append("  -> Shelly bereits in der Liste, wird ignoriert.")
        log(f"{len(found_devices)} neue Geräte zur Liste hinzugefügt.")
        return True, found_devices, log_entries, ""
    except Exception as e:
        msg = f"Ein schwerer Fehler ist während des Scans aufgetreten: {e}"
        log(msg); log_entries.append(msg)
        return False, [], log_entries, str(e)

async def background_worker_loop() -> None:
    """Wartet auf die Trigger-Datei für die Konfiguration."""
    log("Hintergrund-Dienst gestartet. Warte auf Konfigurations-Trigger...")
    while True:
        if os.path.exists("/data/configure_now"):
            os.remove("/data/configure_now")
            task_id = f"task_{random.randint(1000, 9999)}"
            asyncio.create_task(run_configuration_logic(caller_id=task_id))
        await asyncio.sleep(1)

# --- API-Server ---
class ShellyListener:
    def __init__(self): self.found_devices = []
    def remove_service(self, zeroconf, type, name): pass
    def add_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        if info and name.lower().startswith("shelly"):
            hostname = info.server.replace(".local.", "")
            self.found_devices.append({"hostname": hostname, "ip_address": socket.inet_ntoa(info.addresses[0])})

async def handle_lan_scan(request: web.Request) -> web.Response:
    """Sucht via mDNS nach Shelly-Geräten im lokalen Netzwerk."""
    log("Starte LAN-Scan nach Online-Shellys...")
    zeroconf = None
    try:
        zeroconf = Zeroconf()
        listener = ShellyListener()
        ServiceBrowser(zeroconf, "_http._tcp.local.", listener)
        await asyncio.sleep(3)
        log(f"{len(listener.found_devices)} Shellies im LAN gefunden.")
        return web.json_response(listener.found_devices)
    except Exception as e:
        log(f"!!! SCHWERER FEHLER im LAN-Scan: {e}")
        return web.Response(status=500, text=f"LAN scan failed: {e}")
    finally:
        if zeroconf: zeroconf.close()

async def handle_scan(request: web.Request) -> web.Response:
    """Führt einen Scan für den User-Modus aus und gibt SSIDs mit Signalstärke zurück."""
    with open(CONFIG_PATH) as f: config = json.load(f)
    interface = config.get("interface", "wlan0")
    log("User-Mode Scan wird ausgelöst...")
    networks = []
    try:
        success, stdout, stderr = await run_command(["nmcli", "-f", "SSID,SIGNAL", "dev", "wifi", "list", "--rescan", "yes"])
        if success:
            lines = stdout.strip().split('\n')[1:]
            for line in lines:
                try:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        signal, ssid = parts[-1], " ".join(parts[:-1]).strip()
                        if ssid and ssid != '--': networks.append({"ssid": ssid, "signal": int(signal)})
                except (ValueError, IndexError): log(f"Konnte Zeile nicht parsen: '{line}'")
            return web.json_response(networks)
        else:
            return web.json_response({"error": "Scan fehlgeschlagen", "details": stderr}, status=500)
    except Exception as e:
        log(f"Fehler bei handle_scan: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def handle_configure(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        with open(TASK_FILE, "w") as f: json.dump(data, f)
        with open("/data/configure_now", "w") as f: pass
        return web.Response(status=202)
    except Exception as e:
        log(f"API Fehler /api/configure: {e}")
        return web.Response(status=500)

async def handle_progress(request: web.Request) -> web.Response:
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f: content = f.read()
        return web.Response(text=content, content_type="text/plain", charset="utf-8")
    except FileNotFoundError:
        return web.Response(text="Log-Datei noch nicht vorhanden.", status=200)

async def handle_admin_load_devices(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        pin = data.get("pin")
        if not pin: return web.Response(status=400, text="PIN fehlt")
        if not os.path.exists(ADMIN_DEVICES_FILE): return web.json_response([])
        with open(ADMIN_DEVICES_FILE, "rb") as f: encrypted_data = f.read()
        decrypted_bytes = xor_crypt(encrypted_data, pin)
        devices = json.loads(decrypted_bytes.decode('utf-8'))
        return web.json_response(devices)
    except (json.JSONDecodeError, UnicodeDecodeError):
        log("FEHLER: Konnte Gerätedatei nicht entschlüsseln. Falsche PIN oder korrupte Datei.")
        return web.Response(status=400, text="Entschlüsselung fehlgeschlagen. Falsche PIN?")
    except Exception as e:
        log(f"Fehler beim Laden der Geräte: {e}")
        return web.Response(status=500)

async def handle_admin_save_devices(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        pin, devices = data.get("pin"), data.get("devices")
        if not pin or devices is None: return web.Response(status=400, text="PIN oder Gerätedaten fehlen")
        json_string = json.dumps(devices, indent=4)
        encrypted_data = xor_crypt(json_string.encode('utf-8'), pin)
        with open(ADMIN_DEVICES_FILE, "wb") as f: f.write(encrypted_data)
        log(f"{len(devices)} Geräte erfolgreich verschlüsselt und gespeichert.")
        return web.Response(status=200)
    except Exception as e:
        log(f"Fehler beim Speichern der Geräte: {e}")
        return web.Response(status=500)

async def handle_admin_scan(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        existing_devices = data.get("devices", [])
        existing_macs = [dev.get("mac") for dev in existing_devices if dev.get("mac")]
        with open(CONFIG_PATH) as f: config = json.load(f)
        interface = config.get("interface", "wlan0")
        success, new_devices, log_entries, error_message = await scan_wifi_networks(interface, existing_macs)
        response_data = {"new_devices": new_devices, "logs": log_entries}
        if success:
            return web.json_response(response_data)
        else:
            return web.json_response({"error": "Scan fehlgeschlagen", "details": error_message, "logs": log_entries}, status=500)
    except Exception as e:
        log(f"API Fehler /api/admin/scan: {e}")
        return web.json_response({"error": str(e)}, status=500)

# --- Haupt-Startfunktion ---
async def start_background_tasks(app: web.Application) -> None:
    app['background_worker'] = asyncio.create_task(background_worker_loop())

async def main_startup() -> None:
    log(".........................................Add-on wird gestartet.........................................")
    app = web.Application()
    app.on_startup.append(start_background_tasks)
    
    # KORREKTUR: Fehlende Route für LAN-Scan hinzugefügt
    app.router.add_get("/api/lan_scan", handle_lan_scan)
    app.router.add_get("/api/scan", handle_scan)
    app.router.add_post("/api/configure", handle_configure)
    app.router.add_get("/api/progress", handle_progress)
    app.router.add_post("/api/admin/devices/load", handle_admin_load_devices)
    app.router.add_post("/api/admin/devices/save", handle_admin_save_devices)
    app.router.add_post("/api/admin/scan", handle_admin_scan)

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