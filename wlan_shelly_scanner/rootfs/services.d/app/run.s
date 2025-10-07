#!/usr/bin/with-contenv bash
# ^-- WICHTIG: Benutze diesen speziellen Shebang für S6

# Der Rest des Skripts ist fast identisch.
# Wir brauchen den Workaround mit der Datei nicht mehr, da S6 den Token bereitstellt.
set -e

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
        
        # S6 stellt den Token zuverlässig bereit. Wir können ihn wieder direkt verwenden.
        /configure_shellies.py "$SUPERVISOR_TOKEN" &
    fi
    # ... (Rest der while-Schleife bleibt wie gehabt)
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