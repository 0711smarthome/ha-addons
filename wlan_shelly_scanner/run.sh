#!/bin/bash

echo "WLAN Shelly Scanner wird gestartet..."

# Pfad zur Konfigurationsdatei
CONFIG_PATH=/data/options.json

# Lese die Konfiguration mit jq
INTERFACE=$(jq --raw-output ".interface" $CONFIG_PATH)
SEARCH_TERM=$(jq --raw-output ".search_term" $CONFIG_PATH)

# Überprüfe, ob eine Schnittstelle konfiguriert wurde
if [[ -z "$INTERFACE" ]]; then
    echo "Fehler: Es wurde keine WLAN-Schnittstelle in der Addon-Konfiguration festgelegt!"
    exit 1
fi

echo "Suche auf Interface '$INTERFACE' nach SSIDs, die '$SEARCH_TERM' enthalten..."
echo "--- Gefundene Netzwerke ---"

# Der Kernbefehl:
# 1. iw dev $INTERFACE scan -> Führt den Scan auf der angegebenen Schnittstelle durch
# 2. grep "SSID:"           -> Filtert nur die Zeilen mit der SSID heraus
# 3. grep "$SEARCH_TERM"    -> Filtert diese Zeilen erneut nach dem Suchbegriff
# 4. sed 's/\s*SSID: //'    -> Entfernt den "SSID: " Teil für eine saubere Ausgabe
iw dev "$INTERFACE" scan | grep "SSID:" | grep "$SEARCH_TERM" | sed 's/\s*SSID: //'

echo "--------------------------"
echo "Scan beendet."