#!/bin/bash

set -e

echo "Start-Skript wird ausgeführt (Takeover-Version)..."

mkdir -p /var/run/dbus

echo "Starte D-Bus System-Dienst..."
dbus-daemon --system
sleep 2

echo "Starte NetworkManager-Dienst..."
NetworkManager --no-daemon &
sleep 3

echo "===== DIAGNOSE-CHECK ====="
echo "--> Prüfe laufende Prozesse:"
ps aux | grep -E "dbus|NetworkManager" || echo "DIAGNOSE: Einer der Dienste wurde nicht im 'ps' Output gefunden."
echo "--> Prüfe, ob der D-Bus Socket existiert:"
if [ -S /var/run/dbus/system_bus_socket ]; then
    echo "DIAGNOSE: ERFOLG! D-Bus Socket wurde gefunden."
else
    echo "DIAGNOSE: FEHLER! D-Bus Socket wurde NICHT gefunden!"
fi
echo "=========================="

echo "Starte Nginx..."
nginx

echo "Diagnose abgeschlossen. Starte main.py..."
exec python3 /main.py