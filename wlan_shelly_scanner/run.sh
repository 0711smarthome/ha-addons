#!/bin/bash

set -e

echo "Start-Skript wird ausgeführt (nmcli-Version)..."

# Lese die Interface-Einstellung
CONFIG_PATH=/data/options.json
INTERFACE=$(jq --raw-output ".interface" $CONFIG_PATH)

echo "Starte D-Bus System-Dienst, falls noch nicht aktiv..."
# Prüfe, ob der Prozess bereits läuft, bevor wir versuchen, ihn zu starten
if ! pgrep -f "dbus-daemon --system" > /dev/null; then
    dbus-daemon --system
    sleep 1 # Gib dem Dienst einen Moment zum Starten
fi

echo "===== DIAGNOSE-CHECK (Vorher) ====="
echo "Schnittstellen-Status vor dem Aktivierungsversuch:"
ip a show ${INTERFACE} || echo "Info: Schnittstelle ${INTERFACE} nicht gefunden."
echo "==================================="

echo "Versuche, die Netzwerkschnittstelle ${INTERFACE} zu aktivieren..."
# Versuche, die Schnittstelle hochzufahren. Wir entfernen '|| true', um Fehler zu sehen.
ip link set ${INTERFACE} up

# Gib dem System Zeit, den Befehl zu verarbeiten
sleep 2 

echo "===== DIAGNOSE-CHECK (Nachher) ====="
echo "Prüfe, ob die Schnittstelle jetzt UP oder DORMANT ist..."

# Überprüfe den finalen Zustand der Schnittstelle.
# grep -q "state UP" || grep -q "state DORMANT" würde nach exakten Zuständen suchen.
# Eine einfachere Prüfung ist zu schauen, ob das <NO-CARRIER> Flag weg ist oder ob UP im Output steht.
if ! ip a show ${INTERFACE} | grep -q 'state UP\|state DORMANT'; then
    echo "KRITISCHER FEHLER: Konnte die Schnittstelle ${INTERFACE} nicht aktivieren. Sie ist weiterhin DOWN."
    echo "Finaler Status:"
    ip a show ${INTERFACE}
    exit 1 # Skript mit Fehler beenden
fi

echo "ERFOLG: Schnittstelle ${INTERFACE} ist jetzt betriebsbereit."
echo "Finaler Status:"
ip a show ${INTERFACE}
echo "==================================="

echo "Starte Nginx..."
nginx

echo "Voraussetzungen erfüllt. Starte main.py..."
exec python3 /main.py