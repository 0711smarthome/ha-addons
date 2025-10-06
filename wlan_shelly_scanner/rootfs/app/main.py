import os
import subprocess
import re
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
# Ein geheimer Schlüssel ist für Sessions notwendig.
# In einer echten Anwendung sollte dieser sicherer sein.
app.secret_key = 'super-secret-key-for-dev'

# Der hardcodierte PIN
CORRECT_PIN = "0711"

def get_wifi_list():
    """Führt einen WLAN-Scan durch und gibt zwei Listen von SSIDs zurück."""
    interface = os.getenv('WIFI_INTERFACE', 'wlan0')
    shelly_wifis = []
    other_wifis = []
    error = None

    try:
        # Führe den Scan-Befehl aus
        scan_output = subprocess.check_output(
            ['iw', 'dev', interface, 'scan'],
            stderr=subprocess.STDOUT,
            text=True
        )

        # Finde alle SSIDs mit einem regulären Ausdruck
        # Dies filtert leere SSIDs heraus
        all_ssids = re.findall(r"\tSSID: (.+)", scan_output)
        
        # Entferne Duplikate und sortiere
        unique_ssids = sorted(list(set(all_ssids)))

        for ssid in unique_ssids:
            if "shelly" in ssid.lower():
                shelly_wifis.append(ssid)
            else:
                other_wifis.append(ssid)

    except FileNotFoundError:
        error = f"Fehler: Der Befehl 'iw' wurde nicht gefunden. Ist er installiert?"
    except subprocess.CalledProcessError as e:
        error = f"Fehler beim Scannen des Interfaces '{interface}': {e.output}"

    return shelly_wifis, other_wifis, error

@app.route('/', methods=['GET'])
def index():
    # Prüfe, ob der Benutzer den PIN bereits eingegeben hat
    if not session.get('pin_verified'):
        return redirect(url_for('login'))

    # Wenn der PIN korrekt ist, scanne und zeige die Hauptseite
    shelly_wifis, other_wifis, error = get_wifi_list()
    return render_template('index.html', shelly_wifis=shelly_wifis, other_wifis=other_wifis, error=error)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        entered_pin = request.form.get('pin')
        if entered_pin == CORRECT_PIN:
            session['pin_verified'] = True
            return redirect(url_for('index'))
        else:
            error = "Falscher PIN!"
    return render_template('login.html', error=error)

@app.route('/configure', methods=['POST'])
def configure():
    """
    Dieser Teil kommt in Schritt 4.
    Aktuell dient er nur als Platzhalter, um die Formulardaten zu empfangen.
    """
    if not session.get('pin_verified'):
        return redirect(url_for('login'))

    # Hole die Daten aus dem Formular
    selected_shellies = request.form.getlist('shelly_ssids')
    home_ssid = request.form.get('home_ssid')
    home_password = request.form.get('home_password')

    # Im Moment geben wir die Daten nur aus (sichtbar im Add-on Log)
    print("--- Konfiguration empfangen ---")
    print(f"Ausgewählte Shelly-SSIDs: {selected_shellies}")
    print(f"Heim-WLAN SSID: {home_ssid}")
    print(f"Heim-WLAN Passwort: {'*' * len(home_password) if home_password else ''}")
    print("---------------------------------")
    
    # Hier würde später die eigentliche Logik zur Konfiguration der Shellies folgen.
    # Wir leiten den Benutzer vorerst auf eine einfache Erfolgsseite oder zurück.
    return "<h1>Konfiguration erhalten!</h1><p>Die Daten wurden im Add-on-Log ausgegeben. Die weitere Verarbeitung ist für Schritt 4 geplant.</p>"


if __name__ == '__main__':
    # Starte den Server auf Port 8099 und lausche auf allen Interfaces
    app.run(host='0.0.0.0', port=8099, debug=False)