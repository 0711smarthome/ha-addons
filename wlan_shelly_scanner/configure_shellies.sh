#!/bin/bash

main() {
    LOG_FILE="/data/progress.log"
    TASK_FILE="/data/task.json"
    CONFIG_PATH=/data/options.json

    INTERFACE=$(jq --raw-output '.interface // "wlan0"' $CONFIG_PATH)

    log() {
        echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
    }

    log "Starte Konfigurationsprozess auf Interface: $INTERFACE"

    SELECTED_SHELLIES=$(jq -r '.selectedShellies[]' "$TASK_FILE" || true)
    USER_SSID=$(jq -r '.userSsid' "$TASK_FILE" || true)
    USER_PASS=$(jq -r '.userPassword' "$TASK_FILE" || true)

    if [ -z "$USER_SSID" ] || [ -z "$SELECTED_SHELLIES" ]; then
        log "FEHLER: Konnte keine gültigen Aufgaben aus der task.json lesen."
        log "Konfigurationsprozess mit Fehlern abgeschlossen."
        exit 1
    fi

    for shelly_ssid in $SELECTED_SHELLIES; do
        log "---------------------------------------------"
        log "Bearbeite: $shelly_ssid"
        
        # Generiere eine temporäre UUID für die WLAN-Verbindung
        CONNECTION_UUID=$(ha network info --raw-json | jq -r ".interfaces[] | select(.interface == \"$INTERFACE\") | .ipv4.address[0]" | cut -d'/' -f1)-$(date +%s)
        
        log "Versuche, mit dem Shelly-Hotspot via 'ha network' zu verbinden..."
        
        # Benutze 'ha network update' um eine Verbindung herzustellen. Das ist der offizielle Weg.
        if ha network update "$INTERFACE" --wifi-ssid "$shelly_ssid" --wifi-mode "infrastructure"; then
            log "Erfolgreich mit '$shelly_ssid' verbunden (kann bis zu 60s dauern)."
            # Gib dem System reichlich Zeit, die Verbindung vollständig herzustellen
            sleep 15
            
            # Überprüfe, ob wir die erwartete IP-Adresse (192.168.33.x) haben
            CURRENT_IP=$(ha network info --raw-json | jq -r ".interfaces[] | select(.interface == \"$INTERFACE\") | .ipv4.address[0]")
            if [[ "$CURRENT_IP" == "192.168.33."* ]]; then
                log "IP-Adresse im Shelly-Netzwerk erhalten: $CURRENT_IP"
                
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
            else
                log "FEHLER: Mit Shelly-WLAN verbunden, aber keine gültige IP-Adresse erhalten. Aktuelle IP: $CURRENT_IP"
            fi
            
            log "Setze WLAN des Hosts auf die ursprüngliche Konfiguration zurück..."
            # WICHTIG: Verbinde den Host wieder mit dem ursprünglichen WLAN.
            # HINWEIS: Hier müsstest du eigentlich die ursprünglichen WLAN-Daten wieder eintragen.
            # Für einen Test setzen wir es erstmal nur zurück, was oft reicht, damit es sich neu verbindet.
            # Ein robusteres Skript würde sich die alte Konfiguration merken.
            ha network update "$INTERFACE" --wifi-ssid "$USER_SSID" --wifi-auth "wpa-psk" --wifi-key "$USER_PASS"
            log "Host-WLAN wird wiederhergestellt. Dies kann einen Moment dauern."

        else
            log "FEHLER: Der Befehl 'ha network update' zur Verbindung mit '$shelly_ssid' ist fehlgeschlagen."
        fi
    done

    log "---------------------------------------------"
    log "Konfigurationsprozess für alle ausgewählten Geräte abgeschlossen."
    rm "$TASK_FILE"
}

(
  flock -n 200 || { echo "Konfigurationsprozess läuft bereits."; exit 1; }
  main
) 200>/tmp/configure.lock