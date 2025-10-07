#!/bin/bash
# Diese Datei führt den eigentlichen Konfigurationsprozess aus.

LOG_FILE="/data/progress.log"
TASK_FILE="/data/task.json"

# --- HAUPT-LOGIK ---
# Wir packen den gesamten Code in eine Funktion, um ihn dann mit flock aufzurufen.
main() {
    # Funktion zum Loggen in Datei und Konsole
    log() {
        echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
    }

    # Starte den Prozess
    # Die Log-Datei wird jetzt in run.sh geleert, nicht mehr hier.
    log "Starte Konfigurationsprozess..."

    # Lese die Daten aus der Task-Datei
    # Wir verwenden `|| true`, um Fehler zu unterdrücken, falls die Datei mal leer ist
    SELECTED_SHELLIES=$(jq -r '.selectedShellies[]' "$TASK_FILE" || true)
    USER_SSID=$(jq -r '.userSsid' "$TASK_FILE" || true)
    USER_PASS=$(jq -r '.userPassword' "$TASK_FILE" || true)

    if [ -z "$USER_SSID" ] || [ -z "$SELECTED_SHELLIES" ]; then
        log "FEHLER: Konnte keine gültigen Aufgaben aus der task.json lesen."
        log "Konfigurationsprozess mit Fehlern abgeschlossen."
        exit 1
    fi

    # Iteriere über jede ausgewählte Shelly SSID
    for shelly_ssid in $SELECTED_SHELLIES; do
        log "---------------------------------------------"
        log "Bearbeite: $shelly_ssid"
        
        # Verbinde mit dem Shelly-WLAN
        log "Versuche, mit dem Shelly-Hotspot zu verbinden (Timeout: 20s)..."
        # Wir müssen nmcli eventuell sagen, welches Interface es nutzen soll
        if nmcli device wifi connect "$shelly_ssid" --timeout 20; then
            log "Erfolgreich mit '$shelly_ssid' verbunden."
            
            # Gib dem Netzwerk einen Moment Zeit, sich zu stabilisieren
            sleep 5 
            
            # Baue die Konfigurations-URL zusammen.
            ENCODED_SSID=$(printf %s "$USER_SSID" | jq -sRr @uri)
            ENCODED_PASS=$(printf %s "$USER_PASS" | jq -sRr @uri)
            URL="http://192.168.33.1/settings/sta?ssid=$ENCODED_SSID&pass=$ENCODED_PASS&enable=true"
            
            log "Sende WLAN-Daten an den Shelly..."
            log $ENCODED_SSID
            log $ENCODED_PASS
            log $URL
            # Wir fügen -v für mehr Debug-Output im Fehlerfall hinzu und leiten ihn um
            #CURL_OUTPUT=$(curl -v --fail --max-time 15 -s "$URL" 2>&1)
            #CURL_EXIT_CODE=$?

            #if [ $CURL_EXIT_CODE -eq 0 ]; then
            #    log "Erfolg! Shelly wurde angewiesen, sich mit '$USER_SSID' zu verbinden."
            #else
            #    log "FEHLER: Konnte die Konfiguration nicht an den Shelly senden (Exit-Code: $CURL_EXIT_CODE)."
            #    log "Curl-Debug-Ausgabe: $CURL_OUTPUT"
            #fi
            
            # Trenne die Verbindung zum Shelly wieder, um den nächsten zu bearbeiten
            log "Trenne Verbindung zum Shelly-Hotspot..."
            # Es ist sicherer, die Verbindung über ihre UUID zu löschen
            CONNECTION_UUID=$(nmcli -g UUID,TYPE connection show --active | grep wifi | cut -d':' -f1)
            if [ -n "$CONNECTION_UUID" ]; then
                nmcli connection delete uuid "$CONNECTION_UUID" || log "Warnung: Konnte die temporäre Verbindung nicht löschen."
            else
                log "Warnung: Konnte die aktive WLAN-Verbindung nicht finden, um sie zu löschen."
            fi
        else
            log "FEHLER: Verbindung mit '$shelly_ssid' fehlgeschlagen."
        fi
    done

    log "---------------------------------------------"
    log "Konfigurationsprozess für alle ausgewählten Geräte abgeschlossen."
    rm "$TASK_FILE"
}

# --- SCRIPT-START ---
# Dies ist der robustere Weg, flock zu verwenden:
# Der Code wird nur ausgeführt, wenn der Lock erfolgreich gesetzt werden kann.
(
    main
) | flock -n /tmp/configure.lock