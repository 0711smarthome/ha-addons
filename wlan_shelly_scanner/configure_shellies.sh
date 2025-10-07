#!/bin/bash

main() {
    LOG_FILE="/data/progress.log"
    TASK_FILE="/data/task.json"
    CONFIG_PATH=/data/options.json

    INTERFACE=$(jq --raw-output '.interface // "wlan0"' "$CONFIG_PATH")

    log() {
        echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
    }

    log "Starte Konfigurationsprozess auf Interface: $INTERFACE"

    SELECTED_SHELLIES=$(jq -r '.selectedShellies[]' "$TASK_FILE" || true)
    USER_SSID=$(jq -r '.userSsid' "$TASK_FILE" || true)
    USER_PASS=$(jq -r '.userPassword' "$TASK_FILE" || true)

    if [ -z "$USER_SSID" ] || [ -z "$SELECTED_SHELLIES" ]; then
        log "FEHLER: Ungültige Aufgabendaten."
        exit 1
    fi

    for shelly_ssid in $SELECTED_SHELLIES; do
        log "---------------------------------------------"
        log "Bearbeite: $shelly_ssid"
        
        log "Versuche, mit dem Shelly-Hotspot zu verbinden..."
        
        if nmcli device wifi connect "$shelly_ssid" ifname "$INTERFACE" --timeout 30; then
            log "Erfolgreich mit '$shelly_ssid' verbunden."
            sleep 5
            
            ENCODED_SSID=$(printf %s "$USER_SSID" | jq -sRr @uri)
            ENCODED_PASS=$(printf %s "$USER_PASS" | jq -sRr @uri)
            URL="http://192.168.33.1/settings/sta?ssid=$ENCODED_SSID&pass=$ENCODED_PASS&enable=true"
            
            log "Sende WLAN-Daten an den Shelly..."
            CURL_OUTPUT=$(curl -v --fail --max-time 15 -s "$URL" 2>&1)
            CURL_EXIT_CODE=$?
            if [ $CURL_EXIT_CODE -eq 0 ]; then
               log "Erfolg! Shelly wurde angewiesen, sich mit '$USER_SSID' zu verbinden."
            else
               log "FEHLER: Konnte die Konfiguration nicht an den Shelly senden (Exit-Code: $CURL_EXIT_CODE)."
               log "Curl-Debug-Ausgabe: $CURL_OUTPUT"
            fi
            
            log "Trenne Verbindung zum Shelly-Hotspot..."
            CONNECTION_UUID=$(nmcli -g UUID,TYPE connection show --active | grep wifi | cut -d':' -f1)
            if [ -n "$CONNECTION_UUID" ]; then
                nmcli connection delete uuid "$CONNECTION_UUID" || log "Warnung: Temporäre Verbindung konnte nicht gelöscht werden."
            else
                log "Warnung: Aktive WLAN-Verbindung zum Löschen nicht gefunden."
            fi
        else
            log "FEHLER: Verbindung mit '$shelly_ssid' fehlgeschlagen."
        fi
    done

    log "---------------------------------------------"
    log "Konfigurationsprozess abgeschlossen."
    rm "$TASK_FILE" 2>/dev/null || true
}

(
  flock -n 200 || { echo "Konfigurationsprozess läuft bereits."; exit 1; }
  main
) 200>/tmp/configure.lock