#!/usr/bin/env bash

# SIGTERM-handler: Wird beim Stoppen des Add-ons ausgeführt.
term_handler(){
    echo "Stopping WLAN Scanner..."
    exit 0
}
# Setup signal handler
trap 'term_handler' SIGTERM

echo "WLAN Scanner Add-on wird gestartet!"

# Lies die Konfiguration aus der options.json von Home Assistant
CONFIG_PATH=/data/options.json
INTERFACE=$(jq --raw-output '.interface // "wlan0"' $CONFIG_PATH)
INTERVAL=$(jq --raw-output '.scan_interval // 60' $CONFIG_PATH)
SAFE_MODE=$(jq --raw-output '.safe_mode // true' $CONFIG_PATH)

echo "Verwende Interface: ${INTERFACE}"
echo "Scan-Intervall: ${INTERVAL} Sekunden"
echo "Gesicherter Modus (safe_mode): ${SAFE_MODE}"

# --- PRÜF-SCHRITT ---
# Prüfen, ob das Netzwerk-Interface überhaupt existiert (Kritische Prüfung)
echo "Prüfe, ob das Interface '${INTERFACE}' existiert..."
if ! ip link show "${INTERFACE}" > /dev/null 2>&1; then
    echo "-----------------------------------------------------------"
    echo "FEHLER: Das Interface '${INTERFACE}' wurde nicht gefunden!"
    echo "Bitte überprüfe den Namen des WLAN-Interfaces auf deinem Host-System"
    echo "und korrigiere ihn in der Add-on Konfiguration."
    echo "Mögliche Interfaces sind:"
    # Listet mögliche Interfaces zur Hilfe auf
    ip link show | grep -oP '^\d+: \K[^:]+'
    echo "-----------------------------------------------------------"
    # Sofortiger Exit bei kritischem Fehler, um den S6-Fehler zu vermeiden.
    exit 1
fi
echo "Interface '${INTERFACE}' gefunden. Starte die Schleife."

# Endlosschleife, um periodisch zu scannen
while true; do
    echo "Suche nach WLAN-Netzwerken..."
    
    # Führe den Scan aus
    SCAN_OUTPUT=$(iw dev "${INTERFACE}" scan 2>&1)
    EXIT_CODE=$?

    if [ ${EXIT_CODE} -eq 0 ]; then
        echo "Scan erfolgreich. Gefundene SSIDs:"
        
        # Logik für den GESICHERTEN MODUS (Debug-Output)
        if [ "${SAFE_MODE}" = "true" ]; then
            echo "--- Detaillierter Scan-Output (Safe Mode ist AN) ---"
            echo "${SCAN_OUTPUT}"
            echo "----------------------------------------------------"
        fi

        # Unabhängig vom Safe Mode geben wir immer die gefilterten SSIDs aus
        echo "Gefilterte SSIDs:"
        echo "${SCAN_OUTPUT}" | grep "SSID:" | sed 's/\tSSID: //'
    else
        # Fehlerbehandlung
        echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        echo "FEHLER: Der 'iw scan' Befehl ist fehlgeschlagen mit Exit-Code ${EXIT_CODE}."
        echo "Die Fehlermeldung war:"
        echo "${SCAN_OUTPUT}"
        echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    fi
    
    echo "Warte ${INTERVAL} Sekunden bis zum nächsten Scan."
    sleep "${INTERVAL}"
done
