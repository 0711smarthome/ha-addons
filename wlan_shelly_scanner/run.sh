#!/bin/bash

set -e

echo "Start-Skript wird ausgeführt..."

# Lese die Interface-Einstellung aus der Konfiguration
CONFIG_PATH=/data/options.json
INTERFACE=$(jq --raw-output ".interface" $CONFIG_PATH)

echo "===== System-Voraussetzungen prüfen ====="

# 1. Prüfe, ob der D-Bus Socket des Hosts verfügbar ist.
#    Wir versuchen NICHT, den Dienst selbst zu starten.
echo "--> Prüfe, ob D-Bus Socket existiert..."
if [ ! -S /var/run/dbus/system_bus_socket ]; then
    echo "KRITISCHER FEHLER: Der D-Bus Socket des Host-Systems wurde nicht gefunden!"
    echo "Stelle sicher, dass das Add-on im 'Host-Netzwerk'-Modus läuft oder der DBus-Zugriff gewährt wird."
    exit 1
fi
echo "ERFOLG: D-Bus Socket ist verfügbar."

# 2. Versuche, die Netzwerkschnittstelle zu aktivieren.
echo "--> Aktiviere Netzwerkschnittstelle ${INTERFACE}..."
ip link set ${INTERFACE} up

# Gib dem System einen Moment Zeit, den Zustand zu aktualisieren
sleep 2

# 3. Überprüfe den finalen Zustand der Schnittstelle.
echo "--> Überprüfe finalen Status von ${INTERFACE}..."
if ! ip a show ${INTERFACE} | grep -q 'state UP\|state DORMANT'; then
    echo "KRITISCHER FEHLER: Konnte die Schnittstelle ${INTERFACE} nicht in einen betriebsbereiten Zustand (UP/DORMANT) versetzen."
    echo "Aktueller Status:"
    ip a show ${INTERFACE}
    exit 1 # Skript mit Fehler beenden
fi

echo "ERFOLG: Schnittstelle ${INTERFACE} ist jetzt betriebsbereit."
ip a show ${INTERFACE}
echo "=========================================="

echo "Starte Nginx-Server..."
nginx

echo "Voraussetzungen erfüllt. Starte die Hauptanwendung (main.py)..."
exec python3 /main.py