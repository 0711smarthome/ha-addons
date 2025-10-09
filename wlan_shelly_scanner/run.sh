#!/bin/bash

echo "Start-Skript (vereinfachte Version) wird ausgeführt..."

# Starte den Nginx Webserver im Hintergrund
nginx

# Führe das Python-Skript als Hauptprozess aus
echo "Starte main.py..."
exec python3 /main.py