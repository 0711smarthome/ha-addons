#!/usr/bin/env bash
set -e

# --- Prozess- und Signal-Management ---
NGINX_PID=
SOCAT_SCAN_PID=
SOCAT_CONFIGURE_PID=
SOCAT_PROGRESS_PID=

term_handler(){
    echo "Stopping background services..."
    if [ -n "${NGINX_PID}" ]; then kill "${NGINX_PID}"; fi
    if [ -n "${SOCAT_SCAN_PID}" ]; then kill "${SOCAT_SCAN_PID}"; fi
    if [ -n "${SOCAT_CONFIGURE_PID}" ]; then kill "${SOCAT_CONFIGURE_PID}"; fi
    if [ -n "${SOCAT_PROGRESS_PID}" ]; then kill "${SOCAT_PROGRESS_PID}"; fi
    echo "WLAN Scanner stopped."
    exit 0
}
trap 'term_handler' SIGTERM

# --- Start der Hintergrunddienste ---
echo "WLAN Scanner Add-on wird gestartet!"
nginx -g "daemon off; error_log /dev/stdout info;" &
NGINX_PID=$!

echo "Starte API-Listener..."
# API für Scan-Trigger auf Port 8888
(while true; do socat TCP-LISTEN:8888,fork,reuseaddr EXEC:'/bin/bash -c "echo -e \"HTTP/1.1 200 OK\\r\\n\" && touch /tmp/scan_now"'; done) &
SOCAT_SCAN_PID=$!

# API zum Starten der Konfiguration auf Port 8889 (empfängt POST-Daten)
(while true; do socat TCP-LISTEN:8889,fork,reuseaddr EXEC:'/bin/bash -c "echo -e \"HTTP/1.1 200 OK\\r\\n\" && > /data/progress.log && read -r -d \"\" body && echo \"$body\" > /data/task.json && touch /tmp/configure_now"'; done) &
SOCAT_CONFIGURE_PID=$!

# API zum Abfragen des Fortschritts auf Port 8890
(while true; do socat TCP-LISTEN:8890,fork,reuseaddr EXEC:'/bin/bash -c "echo -e \"HTTP/1.1 200 OK\\r\\nContent-Type: text/plain\\r\\n\" && cat /data/progress.log 2>/dev/null"'; done) &
SOCAT_PROGRESS_PID=$!


# --- Konfiguration & Start ---
CONFIG_PATH=/data/options.json
INTERFACE=$(jq --raw-output '.interface // "wlan0"' $CONFIG_PATH)
INTERVAL=$(jq --raw-output '.scan_interval // 60' $CONFIG_PATH)

echo "Verwende Interface: ${INTERFACE}"
echo "Scan-Intervall: ${INTERVAL} Sekunden"
echo "Prüfe, ob das Interface '${INTERFACE}' existiert..."
if ! ip link show "${INTERFACE}" > /dev/null 2>&1; then
    echo "FEHLER: Interface nicht gefunden."
    exit 1
fi
echo "Interface '${INTERFACE}' gefunden. Starte die Schleife."

# --- Hauptschleife ---
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