#!/usr/bin/env bash
# Wir entfernen vorübergehend 'set -e', um Fehler selbst zu behandeln
# set -e

echo "WLAN Scanner Add-on wird gestartet!"

# Lies die Konfiguration aus der options.json von Home Assistant
INTERFACE=$(jq --raw-output '.interface // "wlan0"' /data/options.json)
INTERVAL=$(jq --raw-output '.scan_interval // 60' /data/options.json)

echo "Verwende Interface: ${INTERFACE}"
echo "Scan-Intervall: ${INTERVAL} Sekunden"

# --- NEUER PRÜF-SCHRITT ---
# Prüfen, ob das Netzwerk-Interface überhaupt existiert
echo "Prüfe, ob das Interface '${INTERFACE}' existiert..."
if ! ip link show "${INTERFACE}" > /dev/null 2>&1; then
    echo "-----------------------------------------------------------"
    echo "FEHLER: Das Interface '${INTERFACE}' wurde nicht gefunden!"
    echo "Bitte überprüfe den Namen des WLAN-Interfaces auf deinem Host-System"
    echo "und korrigiere ihn in der Add-on Konfiguration."
    echo "Mögliche Interfaces sind:"
    ip link show | grep -oP '^\d+: \K[^:]+'
    echo "-----------------------------------------------------------"
    # Warte eine lange Zeit, damit der Fehler im Log sichtbar bleibt
    sleep 3600 
    exit 1
fi
echo "Interface '${INTERFACE}' gefunden. Starte die Schleife."


# Endlosschleife, um periodisch zu scannen
while true; do
    echo "Suche nach WLAN-Netzwerken..."
    
    # --- VERBESSERTE FEHLERBEHANDLUNG ---
    # Führe den Scan-Befehl aus und fange allen Output (stdout & stderr) ab
    SCAN_OUTPUT=$(iw dev "${INTERFACE}" scan 2>&1)
    EXIT_CODE=$? # Speichere den Exit-Code des letzten Befehls

    # Prüfe, ob der Befehl erfolgreich war (Exit-Code 0)
    if [ ${EXIT_CODE} -eq 0 ]; then
        echo "Scan erfolgreich. Gefundene SSIDs:"
        # Verarbeite den erfolgreichen Output
        echo "${SCAN_OUTPUT}" | grep "SSID:" | sed 's/\tSSID: //'
    else
        echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        echo "FEHLER: Der 'iw scan' Befehl ist fehlgeschlagen mit Exit-Code ${EXIT_CODE}."
        echo "Die Fehlermeldung war:"
        echo "${SCAN_OUTPUT}"
        echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    fi
    
    echo "Warte ${INTERVAL} Sekunden bis zum nächsten Scan."
    sleep "${INTERVAL}"
done