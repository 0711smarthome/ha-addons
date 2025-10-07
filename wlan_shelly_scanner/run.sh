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
# API für Scan-Trigger
(while true; do echo -e "HTTP/1.1 200 OK\r\n" | socat - TCP-LISTEN:8888,fork,reuseaddr EXEC:'touch /tmp/scan_now'; done) &
SOCAT_SCAN_PID=$!

# API zum Starten der Konfiguration (empfängt POST-Daten)
(while true; do socat - TCP-LISTEN:8889,fork,reuseaddr EXEC:'/bin/bash -c "read -r -d \"\" body && echo \"$body\" > /data/task.json && touch /tmp/configure_now"' ; done) &
SOCAT_CONFIGURE_PID=$!

# API zum Abfragen des Fortschritts
(while true; do echo -e "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n" && cat /data/progress.log | socat - TCP-LISTEN:8890,fork,reuseaddr - ; done) &
SOCAT_PROGRESS_PID=$!


# --- Konfiguration auslesen ---

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
    echo "Bitte überprüfe den Namen des WLAN-Interfaces und korrigiere ihn in der Add-on Konfiguration."
    echo "Mögliche Interfaces sind:"
    ip link show | grep -oP '^\d+: \K[^:]+'
    echo "-----------------------------------------------------------"
    exit 1
fi
echo "Interface '${INTERFACE}' gefunden. Starte die Schleife."


# --- Hauptschleife ---

while true; do
    # Prüfe, ob eine Konfiguration gestartet werden soll
    if [ -f /tmp/configure_now ]; then
        echo "Konfigurations-Trigger erkannt!"
        rm /tmp/configure_now
        # Führe das Konfigurations-Skript im Hintergrund aus, um die Hauptschleife nicht zu blockieren
        /configure_shellies.sh &
    fi
    
    echo "Suche nach WLAN-Netzwerken..."
    SCAN_OUTPUT=$(iw dev "${INTERFACE}" scan 2>&1)
    EXIT_CODE=$?

    if [ ${EXIT_CODE} -eq 0 ]; then
        # Scan war ERFOLGREICH
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
                line=$(echo "$line" | sed 's/"/\\"/g')
                JSON_SSIDS="${JSON_SSIDS}\"$line\""
                FIRST=false
            fi
        done <<< "$SSIDS"
        JSON_SSIDS="${JSON_SSIDS}]"
        
        echo "$JSON_SSIDS" > /var/www/wifi_list.json
    else
        # Scan ist FEHLGESCHLAGEN
        echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        echo "FEHLER: Der 'iw scan' Befehl ist fehlgeschlagen mit Exit-Code ${EXIT_CODE}."
        echo "Die Fehlermeldung war:"
        echo "${SCAN_OUTPUT}"
        echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    fi
    
    # Warte bis zum nächsten Scan, aber unterbrechbar durch die API
    echo "Warte bis zu ${INTERVAL} Sekunden auf den nächsten Scan (oder API-Trigger)..."
    for ((i=0; i<INTERVAL; i++)); do
        # Prüfe jede Sekunde, ob die Trigger-Datei existiert
        if [ -f /tmp/scan_now ]; then
            echo "Scan-Trigger via API erkannt!"
            rm /tmp/scan_now  # Trigger-Datei löschen
            break  # Schleife unterbrechen und sofort neuen Scan starten
        fi
        sleep 1
    done
done