#!/bin/bash

# Diese Zeile sorgt dafür, dass das Skript bei jedem Fehler sofort abbricht.
set -e

echo "Start-Skript wird ausgeführt (Diagnose-Version)..."

# D-Bus braucht dieses Verzeichnis, das in manchen minimalen Systemen fehlt.
# Wir erstellen es vorsichtshalber.
mkdir -p /var/run/dbus

echo "Starte D-Bus System-Dienst..."
dbus-daemon --system

# Gib D-Bus einen Moment Zeit zum Starten
sleep 2

echo "Starte NetworkManager-Dienst..."
# Wir starten den Dienst jetzt mit der Option --no-daemon im Hintergrund.
# Das verbessert oft die Protokollierung in Docker-Containern.
NetworkManager --no-daemon &

# Gib dem NetworkManager einen Moment zum Initialisieren
sleep 3

echo "===== DIAGNOSE-CHECK ====="
echo "--> Prüfe laufende Prozesse:"
# Wir listen alle Prozesse auf und filtern nach unseren Diensten.
# Wenn hier nichts erscheint, sind sie nicht gestartet.
ps aux | grep -E "dbus|NetworkManager" || echo "DIAGNOSE: Einer der Dienste wurde nicht im 'ps' Output gefunden."

echo "--> Prüfe, ob der D-Bus Socket existiert:"
# Das ist der entscheidende Test. Der Fehler "No such file or directory"
# bezieht sich auf genau diese Datei (den Socket).
if [ -S /var/run/dbus/system_bus_socket ]; then
    echo "DIAGNOSE: ERFOLG! D-Bus Socket wurde gefunden."
else
    echo "DIAGNOSE: FEHLER! D-Bus Socket (/var/run/dbus/system_bus_socket) wurde NICHT gefunden!"
fi
echo "=========================="

echo "Diagnose abgeschlossen. Starte main.py..."
# Führe das Python-Skript als Hauptprozess aus
exec python3 /main.py