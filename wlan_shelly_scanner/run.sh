#!/bin/bash

echo "Start-Skript wird ausgeführt..."

# Starte den NetworkManager-Dienst im Hintergrund
echo "Starte NetworkManager-Dienst..."
NetworkManager &

# Gib dem Dienst einen Moment zum Initialisieren
sleep 3

echo "NetworkManager sollte jetzt laufen. Starte main.py..."
# Führe das Python-Skript als Hauptprozess aus
exec python3 /main.py