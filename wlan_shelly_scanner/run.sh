#!/usr/bin/env bash
set -e

# --- Prozess-Management ---
NGINX_PID=
API_PIDS=()
term_handler(){
    echo "Stopping background services..."
    if [ -n "${NGINX_PID}" ]; then kill "${NGINX_PID}"; fi
    for pid in "${API_PIDS[@]}"; do kill "$pid" 2>/dev/null; done
    echo "WLAN Scanner stopped."
    exit 0
}
trap 'term_handler' SIGTERM

# --- Start der Dienste ---
echo "WLAN Scanner Add-on wird gestartet!"

# +++ DEBUGGING-BLOCK für "ha" +++
echo "--- HA CLI DEBUGGING START ---"
if command -v ha &> /dev/null; then
    echo "SUCCESS: 'ha' CLI wurde im PATH gefunden."
    echo "Pfad: $(which ha)"
else
    echo "WARNUNG: 'ha' CLI wurde NICHT im Standard-PATH gefunden. Das Skript verwendet den Hardcode-Pfad /usr/bin/ha."
fi
if [ -f /usr/bin/ha ]; then
    echo "INFO: Die Datei /usr/bin/ha existiert."
else
    echo "!!!!!!!!!! FATALER FEHLER: Die Datei /usr/bin/ha existiert NICHT. !!!!!!!!!!"
fi
echo "--- HA CLI DEBUGGING END ---"
# +++ ENDE DEBUGGING-BLOCK +++


nginx -g "daemon off; error_log /dev/stdout info;" &
NGINX_PID=$!

echo "Starte API-Listener..."
# API für Scan-Trigger auf Port 8888 (unverändert)
(while true; do ncat -l 8888 -c 'echo -e "HTTP/1.1 204 No Content\r\n\r\n" && touch /tmp/scan_now'; done) &
API_PIDS+=($!)

# API zum Starten der Konfiguration auf Port 8889 (NEU und VEREINFACHT)
# Dieser Listener schreibt nur noch die rohe Anfrage weg und ist sofort fertig.
(while true; do ncat -l 8889 -c 'cat > /data/raw_task.tmp && echo -e "HTTP/1.1 204 No Content\r\n\r\n" && touch /tmp/configure_now'; done) &
API_PIDS+=($!)

# API zum Abfragen des Fortschritts auf Port 8890 (unverändert)
(while true; do ncat -l 8890 -c 'echo -e "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n" && cat /data/progress.log 2>/dev/null'; done) &
API_PIDS+=($!)

# --- Konfiguration & Start-Schleife (unverändert) ---
# ... (der Rest der run.sh bleibt exakt gleich wie in der letzten Version) ...
CONFIG_PATH=/data/options.json
INTERFACE=$(jq --raw-output '.interface // "wlan0"' $CONFIG_PATH)
INTERVAL=$(jq --raw-output '.scan_interval // 60' $CONFIG_PATH)
echo "Verwende Interface: ${INTERFACE}"
echo "Scan-Intervall: ${INTERVAL} Sekunden"
echo "Prüfe, ob das Interface '${INTERFACE}' existiert..."
if ! ip link show "${INTERFACE}" > /dev/null 2>&1; then echo "FEHLER: Interface nicht gefunden."; exit 1; fi
echo "Interface '${INTERFACE}' gefunden. Starte die Schleife."
while true; do
    if [ -f /tmp/configure_now ]; then
        echo "Konfigurations-Trigger erkannt! Starte Konfigurations-Skript im Hintergrund."
        rm /tmp/configure_now
        /configure_shellies.sh &
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
    fi
    echo "Warte bis zu ${INTERVAL} Sekunden auf den nächsten Scan (oder API-Trigger)..."
    for ((i=0; i<INTERVAL; i++)); do
        if [ -f /tmp/scan_now ]; then
            echo "Scan-Trigger via API erkannt!"
            rm /tmp/scan_now
            break
        fi
        if [ -f /tmp/configure_now ]; then
            echo "Konfigurations-Trigger während des Wartens erkannt!"
            break
        fi
        sleep 1
    done
done