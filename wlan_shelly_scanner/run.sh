#!/usr/bin/env bash
# Stellt sicher, dass das Skript bei Fehlern sofort abbricht, was das Debugging erleichtert.
set -e

# --- Prozess- und Signal-Management ---

# Globale Variablen für die Prozess-IDs (PIDs) der Hintergrunddienste.
# Das ist notwendig, um sie beim Herunterfahren sauber beenden zu können.
NGINX_PID=
SOCAT_SCAN_PID=
SOCAT_CONFIGURE_PID=
SOCAT_PROGRESS_PID=

# SIGTERM-handler: Diese Funktion wird aufgerufen, wenn Home Assistant das Add-on stoppt.
term_handler(){
    echo "Stopping background services..."
    # Beende die Prozesse nur, wenn sie auch wirklich eine PID haben.
    if [ -n "${NGINX_PID}" ]; then kill "${NGINX_PID}"; fi
    if [ -n "${SOCAT_SCAN_PID}" ]; then kill "${SOCAT_SCAN_PID}"; fi
    if [ -n "${SOCAT_CONFIGURE_PID}" ]; then kill "${SOCAT_CONFIGURE_PID}"; fi
    if [ -n "${SOCAT_PROGRESS_PID}" ]; then kill "${SOCAT_PROGRESS_PID}"; fi
    echo "WLAN Scanner stopped."
    exit 0
}
# Richte den Signal-Handler ein, um auf das Beenden-Signal (SIGTERM) zu reagieren.
trap 'term_handler' SIGTERM


# --- Start der Hintergrunddienste ---

echo "WLAN Scanner Add-on wird gestartet!"

# Starte den Nginx Webserver im Hintergrund und speichere seine PID.
echo "Starte Webserver..."
nginx -g "daemon off; error_log /dev/stdout info;" &
NGINX_PID=$!

echo "Starte API-Listener..."
# API-Listener für den Scan-Trigger auf Port 8888.
# Antwortet mit "HTTP 200 OK" und erstellt dann die Trigger-Datei.
(while true; do echo -e "HTTP/1.1 200 OK\r\n" | socat - TCP-LISTEN:8888,fork,reuseaddr EXEC:'touch /tmp/scan_now'; done) &
SOCAT_SCAN_PID=$!

# API-Listener zum Starten der Konfiguration auf Port 8889.
# Leert die Log-Datei, liest den Body der POST-Anfrage, schreibt ihn in die Task-Datei und erstellt den Konfigurations-Trigger.
(while true; do socat - TCP-LISTEN:8889,fork,reuseaddr EXEC:'/bin/bash -c "> /data/progress.log && read -r -d \"\" body && echo \"$body\" > /data/task.json && touch /tmp/configure_now"'; done) &
SOCAT_CONFIGURE_PID=$!

# API-Listener zum Abfragen des Fortschritts auf Port 8890.
# Antwortet mit HTTP-Headern und dem Inhalt der Log-Datei. `2>/dev/null` verhindert Fehler, wenn die Datei kurz nicht existiert.
(while true; do echo -e "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n" && cat /data/progress.log 2>/dev/null | socat - TCP-LISTEN:8890,fork,reuseaddr - ; done) &
SOCAT_PROGRESS_PID=$!


# --- Konfiguration auslesen ---

CONFIG_PATH=/data/options.json
INTERFACE=$(jq --raw-output '.interface // "wlan0"' $CONFIG_PATH)
INTERVAL=$(jq --raw-output '.scan_interval // 60' $CONFIG_PATH)


# --- PRÜF-SCHRITT ---

echo "Verwende Interface: ${INTERFACE}"
echo "Scan-Intervall: ${INTERVAL} Sekunden"
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
    # Prüfe zu Beginn jeder Schleife, ob eine Konfiguration ausgeführt werden soll.
    if [ -f /tmp/configure_now ]; then
        echo "Konfigurations-Trigger erkannt! Starte Konfigurations-Skript im Hintergrund."
        rm /tmp/configure_now
        # Führe das Skript im Hintergrund aus, um die Hauptschleife nicht zu blockieren.
        /configure_shellies.sh &
    fi

    echo "Suche nach WLAN-Netzwerken..."
    SCAN_OUTPUT=$(iw dev "${INTERFACE}" scan 2>&1)
    EXIT_CODE=$?

    if [ ${EXIT_CODE} -eq 0 ]; then
        # Scan war ERFOLGREICH
        echo "Scan erfolgreich."
        SSIDS=$(echo "${SCAN_OUTPUT}" | grep "SSID:" | sed 's/\tSSID: //' | sed '/^$/d')
        
        # Erstelle eine JSON-Liste der SSIDs für die Weboberfläche.
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
        # Scan ist FEHLGESCHLAGEN
        echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        echo "FEHLER: Der 'iw scan' Befehl ist fehlgeschlagen mit Exit-Code ${EXIT_CODE}."
        echo "Die Fehlermeldung war:"
        echo "${SCAN_OUTPUT}"
        echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    fi
    
    # Warte bis zum nächsten Scan, aber unterbrechbar durch die API.
    echo "Warte bis zu ${INTERVAL} Sekunden auf den nächsten Scan (oder API-Trigger)..."
    for ((i=0; i<INTERVAL; i++)); do
        # Prüfe jede Sekunde, ob ein Trigger existiert.
        if [ -f /tmp/scan_now ]; then
            echo "Scan-Trigger via API erkannt!"
            rm /tmp/scan_now
            break # Beende das Warten und starte einen neuen Scan.
        fi
        if [ -f /tmp/configure_now ]; then
            # Wenn ein Konfigurations-Job reinkommt, breche das Warten ebenfalls ab.
            echo "Konfigurations-Trigger während des Wartens erkannt!"
            break
        fi
        sleep 1
    done
done