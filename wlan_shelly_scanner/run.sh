#!/bin/bash

set -e

echo "Start-Skript wird ausgeführt..."

CONFIG_PATH=/data/options.json
INTERFACE=$(jq --raw-output ".interface" $CONFIG_PATH)

echo "===== System-Voraussetzungen prüfen ====="

echo "--> Prüfe, ob D-Bus Socket existiert..."
if [ ! -S /var/run/dbus/system_bus_socket ]; then
    echo "KRITISCHER FEHLER: D-Bus Socket nicht gefunden!"
    exit 1
fi
echo "ERFOLG: D-Bus Socket ist verfügbar."

# --- START DER ÄNDERUNGEN ---

echo "--> Konfiguriere NetworkManager für ${INTERFACE}..."

# 1. Dem NetworkManager sagen, dass er die Schnittstelle nicht mehr
#    automatisch verwalten soll. Das gibt uns die Kontrolle.
nmcli device set "${INTERFACE}" managed no

# 2. Jetzt, wo der NetworkManager sich nicht mehr einmischt,
#    können wir die Schnittstelle sicher mit 'ip' hochfahren.
ip link set "${INTERFACE}" up

sleep 2 # Kurze Pause

echo "--> Überprüfe finalen Status von ${INTERFACE}..."
if ! ip a show "${INTERFACE}" | grep -q 'state UP\|state DORMANT'; then
    echo "KRITISCHER FEHLER: Konnte ${INTERFACE} nicht aktivieren."
    echo "Aktueller Status:"
    ip a show "${INTERFACE}"
    exit 1
fi

# --- ENDE DER ÄNDERUNGEN ---

echo "ERFOLG: Schnittstelle ${INTERFACE} ist jetzt betriebsbereit."
ip a show "${INTERFACE}"
echo "=========================================="

echo "Starte Nginx-Server..."
nginx

echo "Voraussetzungen erfüllt. Starte die Hauptanwendung (main.py)..."
exec python3 /main.py