#!/usr/bin/env bash
set -e

# --- Prozess- und Signal-Management ---
# (Dieser Teil bleibt unverändert)
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


# --- Start der Hintergrunddienste ---
echo "WLAN Scanner Add-on wird gestartet!"

# +++ NEUER DEBUGGING-BLOCK +++
echo "--- DEBUGGING START ---"
echo "Prüfe, ob 'nmcli' existiert und ausführbar ist..."
if command -v nmcli &> /dev/null; then
    echo "SUCCESS: 'nmcli' wurde im PATH gefunden."
    echo "Pfad: $(which nmcli)"
    echo "Datei-Details: $(ls -l $(which nmcli))"
else
    echo "!!!!!!!!!! FEHLER: 'nmcli' wurde NICHT im PATH gefunden. !!!!!!!!!!"
    echo "Das 'networkmanager' Paket wurde beim Rebuild wahrscheinlich nicht korrekt installiert."
fi
echo "System PATH ist: $PATH"
echo "--- DEBUGGING END ---"
# +++ ENDE DEBUGGING-BLOCK +++

nginx -g "daemon off; error_log /dev/stdout info;" &
NGINX_PID=$!
echo "Starte API-Listener..."
# (Der Rest des Skripts bleibt unverändert)
start_scan_api() {
    while true; do ncat -l 8888 -c 'echo -e "HTTP/1.1 204 No Content\r\n\r\n" && touch /tmp/scan_now'; done
}
start_configure_api() {
    while true; do ncat -l 8889 --keep-open -c 'exec /bin/bash -c " > /data/progress.log && sed '\''1,/^\r$/d'\'' > /data/task.json && touch /tmp/configure_now && echo -e \"HTTP/1.1 204 No Content\r\n\r\n\""'; done
}
start_progress_api() {
    while true; do ncat -l 8890 -c 'echo -e "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n" && cat /data/progress.log 2>/dev/null'; done
}
start_scan_api &
API_PIDS+=($!)
start_configure_api &
API_PIDS+=($!)
start_progress_api &
API_PIDS+=($!)
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