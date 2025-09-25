#!/usr/bin/env bash
# Stellt sicher, dass das Skript bei einem Fehler abbricht
set -e

echo "WLAN Scanner Add-on wird gestartet!"

# Lies die Konfiguration aus der options.json von Home Assistant
# z.B. das WLAN-Interface und das Scan-Intervall
INTERFACE=$(jq --raw-output '.interface // "wlan0"' /data/options.json)
INTERVAL=$(jq --raw-output '.scan_interval // 60' /data/options.json)

echo "Verwende Interface: ${INTERFACE}"
echo "Scan-Intervall: ${INTERVAL} Sekunden"

# Endlosschleife, um periodisch zu scannen
while true; do
    echo "Suche nach WLAN-Netzwerken..."
    
    # Führe den Scan-Befehl aus. 
    # Die Ausgabe kannst du weiterverarbeiten, z.B. an MQTT senden.
    # Das '-u' bei 'iw' verhindert Buffer-Probleme.
    iw dev "${INTERFACE}" scan | grep "SSID:"
    
    echo "Scan beendet. Warte ${INTERVAL} Sekunden bis zum nächsten Scan."
    sleep "${INTERVAL}"
done