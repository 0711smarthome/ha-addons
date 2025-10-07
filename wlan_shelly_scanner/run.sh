#!/usr/bin/env bash
# Stellt sicher, dass das Skript bei Fehlern abbricht
set -e

# --- Prozess- und Signal-Management ---

# PIDs der Hintergrundprozesse speichern, um sie sauber beenden zu können
NGINX_PID=
SOCAT_PID=

# SIGTERM-handler: Wird beim Stoppen des Add-ons ausgeführt.
term_handler(){
    echo "Stopping background services..."
    # Beende die Prozesse, falls sie laufen
    if [ -n "${NGINX_PID}" ]; then
        kill "${NGINX_PID}"
    fi
    if [ -n "${SOCAT_PID}" ]; then
        kill "${SOCAT_PID}"
    fi
    echo "WLAN Scanner stopped."
    exit 0
}

# Richte den Signal-Handler ein, um auf das Beenden-Signal von Home Assistant zu reagieren
trap 'term_handler' SIGTERM


# --- Start der Hintergrunddienste ---

echo "WLAN Scanner Add-on wird gestartet!"

# Starte den Nginx Webserver im Hintergrund
echo "Starte Webserver..."
nginx -g "daemon off; error_log /dev/stdout info;" &
NGINX_PID=$!

# Starte den API-Listener im Hintergrund
echo "Starte API-Listener auf Port 8888..."
# Diese Endlosschleife startet socat immer wieder neu, falls es sich beendet.
# Sie wird beim Herunterfahren durch den term_handler gekillt.
while true; do
  # Antwortet mit HTTP 200 OK und erstellt dann die Trigger-Datei
  echo -e "HTTP/1.1 200 OK\r\nContent-Length: 0\r\n" | socat - TCP-LISTEN:8888,fork,reuseaddr EXEC:'touch /tmp/scan_now'
done &
SOCAT_PID=$!


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