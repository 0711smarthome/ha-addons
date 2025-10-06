#!/usr/bin/env bash

# SIGTERM-handler: Wird beim Stoppen des Add-ons ausgeführt.
term_handler(){
    echo "Stopping WLAN Scanner..."
    # Stoppe auch den Webserver
    kill "$(pidof nginx)"
    exit 0
}
# Setup signal handler
trap 'term_handler' SIGTERM

echo "WLAN Scanner Add-on wird gestartet!"

# Starte den Nginx Webserver im Hintergrund
echo "Starte Webserver..."
nginx -g "daemon off;" &

# Lies die Konfiguration aus der options.json von Home Assistant
CONFIG_PATH=/data/options.json
INTERFACE=$(jq --raw-output '.interface // "wlan0"' $CONFIG_PATH)
INTERVAL=$(jq --raw-output '.scan_interval // 60' $CONFIG_PATH)
SAFE_MODE=$(jq --raw-output '.safe_mode // true' $CONFIG_PATH)

echo "Verwende Interface: ${INTERFACE}"
echo "Scan-Intervall: ${INTERVAL} Sekunden"
echo "Gesicherter Modus (safe_mode): ${SAFE_MODE}"

# --- PRÜF-SCHRITT ---
echo "Prüfe, ob das Interface '${INTERFACE}' existiert..."
if ! ip link show "${INTERFACE}" > /dev/null 2>&1; then
    echo "-----------------------------------------------------------"
    echo "FEHLER: Das Interface '${INTERFACE}' wurde nicht gefunden!"
    # ... (Rest der Fehlerbehandlung wie gehabt)
    exit 1
fi
echo "Interface '${INTERFACE}' gefunden. Starte die Schleife."

# Endlosschleife, um periodisch zu scannen
# Endlosschleife, um periodisch zu scannen
while true; do
    echo "Suche nach WLAN-Netzwerken..."
    SCAN_OUTPUT=$(iw dev "${INTERFACE}" scan 2>&1)
    EXIT_CODE=$?

    if [ ${EXIT_CODE} -eq 0 ]; then
        # Scan war ERFOLGREICH
        
        # Unabhängig vom Safe Mode geben wir immer die gefilterten SSIDs aus
        echo "Scan erfolgreich. Gefilterte SSIDs:"
        SSIDS=$(echo "${SCAN_OUTPUT}" | grep "SSID:" | sed 's/\tSSID: //' | sed '/^$/d')
        echo "${SSIDS}"
        
        # Erstelle eine JSON-Liste der SSIDs für die Weboberfläche
        JSON_SSIDS="["
        FIRST=true
        while IFS= read -r line; do
            if [ -n "$line" ]; then
                if [ "$FIRST" = "false" ]; then
                    JSON_SSIDS="${JSON_SSIDS},"
                fi
                # Escape Anführungszeichen in SSIDs, um gültiges JSON zu erzeugen
                line=$(echo "$line" | sed 's/"/\\"/g')
                JSON_SSIDS="${JSON_SSIDS}\"$line\""
                FIRST=false
            fi
        done <<< "$SSIDS"
        JSON_SSIDS="${JSON_SSIDS}]"
        
        # Schreibe die JSON-Datei in das Web-Verzeichnis
        echo "$JSON_SSIDS" > /var/www/wifi_list.json
    else
        # Scan ist FEHLGESCHLAGEN -> HIER KOMMT DIE FEHLERBEHANDLUNG
        echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        echo "FEHLER: Der 'iw scan' Befehl ist fehlgeschlagen mit Exit-Code ${EXIT_CODE}."
        echo "Die Fehlermeldung war:"
        echo "${SCAN_OUTPUT}"
        echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    fi
    
    echo "Warte ${INTERVAL} Sekunden bis zum nächsten Scan."
    sleep "${INTERVAL}"
done