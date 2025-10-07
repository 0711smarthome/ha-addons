#!/bin/bash
# Stellt sicher, dass immer nur eine Instanz dieses Skripts läuft
exec flock -n /tmp/configure.lock || { echo "Konfiguration läuft bereits."; exit 1; }

LOG_FILE="/data/progress.log"
TASK_FILE="/data/task.json"

# Funktion zum Loggen in Datei und Konsole
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Starte den Prozess
echo "" > "$LOG_FILE" # Log-Datei leeren
log "Starte Konfigurationsprozess..."

# Lese die Daten aus der Task-Datei
SELECTED_SHELLIES=$(jq -r '.selectedShellies[]' "$TASK_FILE")
USER_SSID=$(jq -r '.userSsid' "$TASK_FILE")
USER_PASS=$(jq -r '.userPassword' "$TASK_FILE")

if [ -z "$USER_SSID" ] || [ -z "$SELECTED_SHELLIES" ]; then
    log "FEHLER: Konnte keine gültigen Aufgaben aus task.json lesen."
    exit 1
fi

# Iteriere über jede ausgewählte Shelly SSID
for shelly_ssid in $SELECTED_SHELLIES; do
    log "---------------------------------------------"
    log "Bearbeite: $shelly_ssid"
    
    # Verbinde mit dem Shelly-WLAN
    log "Versuche, mit dem Shelly-Hotspot zu verbinden..."
    # --timeout 20 gibt nmcli 20 Sekunden Zeit für den Verbindungsaufbau
    if nmcli device wifi connect "$shelly_ssid" --timeout 20; then
        log "Erfolgreich mit '$shelly_ssid' verbunden."
        
        # Gib dem Netzwerk einen Moment Zeit, sich zu stabilisieren
        sleep 5 
        
        # Baue die Konfigurations-URL zusammen. WICHTIG: Passwörter in URLs müssen URL-kodiert sein!
        ENCODED_PASS=$(printf %s "$USER_PASS" | jq -sRr @uri)
        URL="http://192.168.33.1/settings/sta?ssid=$USER_SSID&pass=$ENCODED_PASS&enable=true"
        
        log "Sende WLAN-Daten an den Shelly..."
        log "Überspringe den tatsächliche CURL-Befehl zum ändern der WIFI Zugangsdaten vorerst"
        # --fail lässt curl bei HTTP-Fehlern (wie 404) mit einem Fehlercode abbrechen
        # --max-time 15 gibt curl 15 Sekunden Zeit für die Anfrage
        #if curl --fail --max-time 15 -s "$URL"; then
        #    log "Erfolg! Shelly wurde angewiesen, sich mit '$USER_SSID' zu verbinden."
        #else
        #    log "FEHLER: Konnte die Konfiguration nicht an den Shelly senden. Ist er erreichbar unter 192.168.33.1?"
        #fi
        
        # Trenne die Verbindung zum Shelly wieder, um den nächsten zu bearbeiten
        log "Trenne Verbindung zum Shelly-Hotspot..."
        nmcli connection delete "$shelly_ssid" || log "Warnung: Konnte die temporäre Verbindung '$shelly_ssid' nicht löschen."
    else
        log "FEHLER: Verbindung mit '$shelly_ssid' fehlgeschlagen."
    fi
done

log "---------------------------------------------"
log "Konfigurationsprozess für alle ausgewählten Geräte abgeschlossen."
rm "$TASK_FILE"