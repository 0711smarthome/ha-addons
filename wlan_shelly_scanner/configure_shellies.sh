#!/bin/bash

main() {
    LOG_FILE="/data/progress.log"
    RAW_TASK_FILE="/data/raw_task.tmp"
    TASK_FILE="/data/task.json"
    CONFIG_PATH=/data/options.json

    log() {
        echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
    }

    # Leere die Log-Datei für den neuen Lauf
    > "$LOG_FILE"
    log "Starte Konfigurationsprozess..."
    
    # NEU: Extrahiere den JSON-Body aus der rohen Anfrage
    log "Verarbeite Aufgaben-Daten..."
    sed '1,/^\r$/d' "$RAW_TASK_FILE" > "$TASK_FILE"
    rm "$RAW_TASK_FILE"

    INTERFACE=$(jq --raw-output '.interface // "wlan0"' "$CONFIG_PATH")
    log "Verwende Interface: $INTERFACE"

    # ... (Rest des Skripts mit der `ha`-Logik bleibt exakt gleich) ...
    SELECTED_SHELLIES=$(jq -r '.selectedShellies[]' "$TASK_FILE" || true)
    USER_SSID=$(jq -r '.userSsid' "$TASK_FILE" || true)
    USER_PASS=$(jq -r '.userPassword' "$TASK_FILE" || true)
    if [ -z "$USER_SSID" ] || [ -z "$SELECTED_SHELLIES" ]; then
        log "FEHLER: Konnte keine gültigen Aufgaben aus der task.json lesen."
        log "Konfigurationsprozess mit Fehlern abgeschlossen."
        exit 1
    fi
    log "Sichere die aktuelle Netzwerkkonfiguration..."
    HOST_UUID=$(ha network info --raw-json | jq -r ".interfaces[] | select(.interface == \"$INTERFACE\") | .primary")
    for shelly_ssid in $SELECTED_SHELLIES; do
        log "---------------------------------------------"
        log "Bearbeite: $shelly_ssid"
        log "Versuche, Host mit Shelly-Hotspot zu verbinden..."
        ha network update "$INTERFACE" --wifi-ssid "$shelly_ssid" --wifi-auth "wpa-psk" --wifi-key "" >/dev/null 2>&1
        log "Warte auf Verbindung (bis zu 30s)..."
        sleep 30
        CURRENT_IP=$(ha network info --raw-json | jq -r ".interfaces[] | select(.interface == \"$INTERFACE\") | .ipv4.address[0]")
        if [[ "$CURRENT_IP" == "192.168.33."* ]]; then
            log "Erfolgreich verbunden! IP-Adresse im Shelly-Netzwerk erhalten: $CURRENT_IP"
            ENCODED_SSID=$(printf %s "$USER_SSID" | jq -sRr @uri)
            ENCODED_PASS=$(printf %s "$USER_PASS" | jq -sRr @uri)
            URL="http://192.168.31/settings/sta?ssid=$ENCODED_SSID&pass=$ENCODED_PASS&enable=true"
            log "Sende WLAN-Daten an den Shelly..."
            #CURL_OUTPUT=$(curl -v --fail --max-time 15 -s "$URL" 2>&1)
            #CURL_EXIT_CODE=$?
            #if [ $CURL_EXIT_CODE -eq 0 ]; then
            #   log "Erfolg! Shelly wurde angewiesen, sich mit '$USER_SSID' zu verbinden."
            #else
            #   log "FEHLER: Konnte die Konfiguration nicht an den Shelly senden (Exit-Code: $CURL_EXIT_CODE)."
            #   log "Curl-Debug-Ausgabe: $CURL_OUTPUT"
            #fi
        else
            log "FEHLER: Verbindung mit Shelly-WLAN fehlgeschlagen oder keine gültige IP-Adresse erhalten. Aktuelle IP: $CURRENT_IP"
        fi
    done
    log "---------------------------------------------"
    log "Stelle die ursprüngliche Netzwerkkonfiguration des Hosts wieder her..."
    if [ -n "$HOST_UUID" ] && [ "$HOST_UUID" != "null" ]; then
        # This part remains a challenge, as we don't know the original password.
        # It will likely fail to restore properly without it.
        # This is where a dedicated USB stick would solve all problems.
        log "Versuche, bekannte Verbindung '$HOST_UUID' zu reaktivieren. Dies kann fehlschlagen, wenn das Passwort nicht im System gespeichert ist."
        ha network update "$INTERFACE" --ipv4-method "auto" 
    else
        log "Warnung: Konnte die ursprüngliche Konfiguration nicht finden. Bitte überprüfe die Netzwerkeinstellungen deines Hosts manuell."
    fi
    log "Konfigurationsprozess für alle ausgewählten Geräte abgeschlossen."
}

(
  flock -n 200 || { echo "Konfigurationsprozess läuft bereits."; exit 1; }
  main
) 200>/tmp/configure.lock