#!/bin/bash

echo "Start-Skript wird ausgeführt..."

# D-Bus ist eine zwingende Voraussetzung für NetworkManager
echo "Starte D-Bus System-Dienst..."
dbus-daemon --system

# Gib D-Bus einen Moment Zeit zum Starten
sleep 1

# Starte den NetworkManager-Dienst im Hintergrund
echo "Starte NetworkManager-Dienst..."
NetworkManager &

# Gib dem NetworkManager einen Moment zum Initialisieren
sleep 3

echo "Dienste gestartet. Starte main.py..."
# Führe das Python-Skript als Hauptprozess aus
exec python3 /main.py