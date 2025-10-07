#!/usr/bin/env bash
set -e

# --- SCHRITT 1: TOKEN SOFORT BEI SKRIPTSTART SICHERN ---
echo "WLAN Scanner: Capturing SUPERVISOR_TOKEN at startup..."
# Wir schreiben den Inhalt der Variable in eine temporäre Datei.
echo $SUPERVISOR_TOKEN
echo "$SUPERVISOR_TOKEN" > /tmp/supervisor_token
echo "WLAN Scanner: Token captured."
# --------------------------------------------------------

NGINX_PID=
API_PIDS=()

term_handler(){
    echo "Stopping background services..."
    if [ -n "${NGINX_PID}" ]; then kill "${NGINX_PID}"; fi
    for pid in "${API_PIDS[@]}"; do kill "$pid" 2>/dev/null; done
    # Bereinigen der Token-Datei beim Stoppen
    if [ -f /tmp/supervisor_token ]; then rm /tmp/supervisor_token; fi
    echo "WLAN Scanner stopped."
    exit 0
}
trap 'term_handler' SIGTERM

echo "WLAN Scanner Add-on wird gestartet!"
nginx -g "daemon off; error_log /dev/stdout info;" &
NGINX_PID=$!

echo "Starte Python API-Server..."
python3 /api_server.py > /data/api_server.log 2>&1 &
API_PIDS+=($!)

echo "Warte 2 Sekunden, damit der API-Server vollständig initialisiert ist..."
sleep 2

CONFIG_PATH=/data/options.json
INTERFACE=$(jq --raw-output '.interface // "wlan0"' $CONFIG_PATH)
INTERVAL=$(jq --raw-output '.scan_interval // 60' $CONFIG_PATH)

echo "Verwende Interface: ${INTERFACE}"
echo "Prüfe, ob das Interface '${INTERFACE}' existiert..."
if ! ip link show "${INTERFACE}" > /dev/null 2>&1; then echo "FEHLER: Interface nicht gefunden."; exit 1; fi
echo "Interface '${INTERFACE}' gefunden. Starte die Schleife."

while true; do
    if [ -f /tmp/configure_now ]; then
        echo "Konfigurations-Trigger erkannt! Starte Python-Konfigurations-Skript."
        rm /tmp/configure_now
        
        # --- SCHRITT 2: TOKEN VOR GEBRAUCH AUS DER DATEI LESEN ---
        echo "Reading token from file..."
        TOKEN_FROM_FILE=$(cat /tmp/supervisor_token)
        
        # DEBUG-Zeile, um zu sehen, ob das Lesen geklappt hat
        echo "DEBUG: Token from file has length: ${#TOKEN_FROM_FILE}"

        # Wir übergeben den aus der Datei gelesenen Token an das Skript
        /configure_shellies.py "$TOKEN_FROM_FILE" &
        # -------------------------------------------------------------
    fi
    echo "Suche nach WLAN-Netzwerken..."
    SCAN_OUTPUT=$(iw dev "${INTERFACE}" scan 2>&1)
    EXIT_CODE=$?
    if [ ${EXIT_CODE} -eq 0 ]; then
        echo "Scan erfolgreich."
        SSIDS=$(echo "${SCAN_OUTPUT}" | grep "SSID:" | sed 's/\tSSID: //' | sed '/^$/d')
        JSON_SSIDS="["
        FIRST=true
        while IFS= read -r line; do
            if [ -n "$line" ]; then
                if [ "$FIRST" = "false" ]; then JSON_SSIDS="${JSON_SSIDS},"; fi
                line=$(echo "$line" | sed 's/"/\\"/g')
                JSON_SSIDS="${JSON_SSIDS}\"$line\""
                FIRST=false
            fi
        done <<< "$SSIDS"
        JSON_SSIDS="${JSON_SSIDS}]"
        echo "$JSON_SSIDS" > /var/www/wifi_list.json
    else
        echo "FEHLER: Der 'iw scan' Befehl ist fehlgeschlagen mit Exit-Code ${EXIT_CODE}."
        echo "Fehlermeldung: ${SCAN_OUTPUT}"
    fi
    echo "Warte bis zu ${INTERVAL} Sekunden..."
    for ((i=0; i<INTERVAL; i++)); do
        if [ -f /tmp/scan_now ] || [ -f /tmp/configure_now ]; then break; fi
        sleep 1
    done
done