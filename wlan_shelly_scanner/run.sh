#!/bin/bash

# Port-Definition, damit wir sie leicht ändern können
INGRESS_PORT=54321

echo "===== DETEKTIV-SKRIPT STARTET ====="
echo "Ich werde jetzt prüfen, ob Port ${INGRESS_PORT} bereits verwendet wird, BEVOR ich Nginx starte..."
echo "-------------------------------------"

# netstat ist möglicherweise nicht installiert, ss ist eine gute Alternative
if command -v netstat &> /dev/null
then
    LISTENING_PROCESS=$(netstat -tulpn | grep ":${INGRESS_PORT}")
else
    # ss ist auf den HA base images vorhanden
    LISTENING_PROCESS=$(ss -tulpn | grep ":${INGRESS_PORT}")
fi


if [ -z "$LISTENING_PROCESS" ]
then
    echo "DIAGNOSE: Port ${INGRESS_PORT} ist FREI. Das ist gut."
else
    echo "DIAGNOSE: ALARM! Port ${INGRESS_PORT} wird bereits von einem anderen Prozess verwendet!"
    echo "Hier ist der blockierende Prozess:"
    echo "$LISTENING_PROCESS"
    echo "Das beweist die Theorie des doppelten Starts."
    echo "Das Skript wird jetzt trotzdem versuchen, Nginx zu starten, was fehlschlagen wird."
fi
echo "-------------------------------------"


echo "Starte Nginx..."
# Dieser Befehl wird fehlschlagen, wenn der Port belegt ist
nginx

echo "Starte main.py..."
exec python3 /main.py