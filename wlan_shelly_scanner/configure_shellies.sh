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
        log "FEHLER: Konnte keine gültigen Aufgaben aus der task.json lesen."
        log "Konfigurationsprozess mit Fehlern abgeschlossen."
        exit 1
    fi
    
    for shelly_ssid in $SELECTED_SHELLIES; do
        log "---------------------------------------------"
        log "Bearbeite: $shelly_ssid"
        
        log "Versuche, Host mit Shelly-Hotspot zu verbinden..."
        
        # HIER DIE KORREKTUR: Wir verwenden '--wifi-auth "open"' für offene Netzwerke
        ha network update "$INTERFACE" --wifi-ssid "$shelly_ssid" --wifi-auth "open" >/dev/null 2>&1
        
        log "Warte auf Verbindung (bis zu 30s)..."
        # Wir warten in kleineren Schritten und prüfen zwischendurch, ob die IP schon da ist
        for i in {1..15}; do
            CURRENT_IP=$(ha network info --raw-json | jq -r ".interfaces[] | select(.interface == \"$INTERFACE\") | .ipv4.address[0]")
            if [[ "$CURRENT_IP" == "192.168.33."* ]]; then
                break # Erfolgreich, Schleife verlassen
            fi
            sleep 2
        done

        if [[ "$CURRENT_IP" == "192.168.33."* ]]; then
            log "Erfolgreich verbunden! IP-Adresse im Shelly-Netzwerk erhalten: $CURRENT_IP"
            
            ENCODED_SSID=$(printf %s "$USER_SSID" | jq -sRr @uri)
            ENCODED_PASS=$(printf %s "$USER_PASS" | jq -sRr @uri)
            URL="http://192.168.33.1/settings/sta?ssid=$ENCODED_SSID&pass=$ENCODED_PASS&enable=true"
            
            log "Sende WLAN-Daten an den Shelly ($URL)...ÜBERSPINGE DA TEST"
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
    
    # VERBESSERTE WIEDERHERSTELLUNG mit den vom Benutzer eingegebenen Daten
    if [ -n "$USER_SSID" ]; then
        ha network update "$INTERFACE" --wifi-ssid "$USER_SSID" --wifi-auth "wpa-psk" --wifi-key "$USER_PASS" >/dev/null 2>&1
        log "Host-WLAN wird auf '$USER_SSID' zurückgesetzt. Dies kann einen Moment dauern."
    else
        log "Warnung: Konnte die ursprüngliche Konfiguration nicht wiederherstellen. Bitte überprüfe die Netzwerkeinstellungen deines Hosts manuell."
    fi

    log "Konfigurationsprozess für alle ausgewählten Geräte abgeschlossen."
    rm "$TASK_FILE" 2>/dev/null || true
}

(
  flock -n 200 || { echo "Konfigurationsprozess läuft bereits."; exit 1; }
  main
) 200>/tmp/configure.lock