#!/bin/bash

set -e

echo "Start-Skript wird ausgeführt (WPA-Supplicant-Version)..."

# Erstelle den Ordner, falls nicht vorhanden (Ihre ursprüngliche Zeile)
mkdir -p /var/run/dbus

echo "Starte D-Bus System-Dienst..."
# Prüfe, ob der Socket bereits existiert und versuche andernfalls den Daemon zu starten.
# Wenn der Socket bereits existiert (weil der Host-D-Bus gemappt ist),
# wird der Befehl fehlschlagen, aber das ist dann kein Problem für die Funktionalität.
dbus-daemon --system || echo "WARNUNG: dbus-daemon konnte nicht gestartet werden (evtl. schon aktiv). Weiter."
sleep 2

# Lese die Interface-Einstellung
CONFIG_PATH=/data/options.json
INTERFACE=$(jq --raw-output ".interface" $CONFIG_PATH)

echo "Aktiviere die Netzwerkschnittstelle ${INTERFACE} und setze sie hoch..."
ip link set ${INTERFACE} up || true
sleep 3 # Wartezeit für die Hardware-Initialisierung

echo "===== DIAGNOSE-CHECK ====="
echo "--> Prüfe laufende Prozesse:"
# Wir erwarten KEINEN NetworkManager mehr.
ps aux | grep -E "dbus" || echo "DIAGNOSE: D-Bus läuft."
echo "--> Prüfe, ob der D-Bus Socket existiert:"
if [ -S /var/run/dbus/system_bus_socket ]; then
    echo "DIAGNOSE: ERFOLG! D-Bus Socket wurde gefunden."
else
    echo "DIAGNOSE: FEHLER! D-Bus Socket wurde NICHT gefunden!"
fi
echo "--> Prüfe Schnittstellen-Status (mit 'ip'):"
ip a show ${INTERFACE} || echo "DIAGNOSE: Schnittstelle ${INTERFACE} nicht gefunden oder nicht aktiv."
echo "=========================="

echo "Starte Nginx..."
nginx

echo "Diagnose abgeschlossen. Starte main.py..."
exec python3 /main.py
