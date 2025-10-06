#!/usr/bin/env bash
set -e

echo "WLAN Scanner Add-on wird gestartet!"

# Lese die Konfiguration aus der options.json von Home Assistant
# und stelle sie als Umgebungsvariable für Python bereit
export WIFI_INTERFACE=$(jq --raw-output '.interface // "wlan0"' /data/options.json)

echo "Verwende Interface: ${WIFI_INTERFACE}"

# Prüfen, ob das Netzwerk-Interface existiert
if ! ip link show "${WIFI_INTERFACE}" > /dev/null 2>&1; then
    echo "-----------------------------------------------------------"
    echo "FEHLER: Das Interface '${WIFI_INTERFACE}' wurde nicht gefunden!"
    echo "Bitte den Namen des WLAN-Interfaces in der Add-on Konfiguration prüfen."
    echo "Add-on wird beendet."
    echo "-----------------------------------------------------------"
    exit 1
fi

echo "Starte den Webserver..."
# Starte die Python Flask Anwendung
python3 /app/main.py