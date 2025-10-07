// Globale Variable für das Polling-Interval
let progressInterval = null;

// Funktion zum Abfragen und Anzeigen des Fortschritts
async function updateProgress() {
    const logOutput = document.getElementById('logOutput');
    try {
        const response = await fetch('/api/progress?' + new Date().getTime()); // Cache umgehen
        const progressText = await response.text();
        logOutput.textContent = progressText;
        // Scrolle die Box automatisch nach unten
        logOutput.scrollTop = logOutput.scrollHeight;
        
        // Stoppe das Polling, wenn das Log-File das Ende anzeigt
        if (progressText.includes("abgeschlossen")) {
            clearInterval(progressInterval);
            document.querySelector('#wifiForm button[type="submit"]').disabled = false; // Button wieder aktivieren
        }
    } catch (error) {
        logOutput.textContent += "\nFehler beim Abrufen des Fortschritts.";
        clearInterval(progressInterval);
        document.querySelector('#wifiForm button[type="submit"]').disabled = false;
    }
}

// Event Listener für das Formular
document.getElementById('wifiForm').addEventListener('submit', async function(event) {
    event.preventDefault(); 
    
    // Stoppe eventuell laufendes altes Polling
    if (progressInterval) {
        clearInterval(progressInterval);
    }

    const selectedShellies = Array.from(document.querySelectorAll('input[name="selected_shelly"]:checked')).map(cb => cb.value);
    const userSsid = document.getElementById('userSsid').value;
    const userPassword = document.getElementById('userPassword').value;

    if (selectedShellies.length === 0) {
        alert('Bitte wähle mindestens ein Shelly-Gerät aus.');
        return;
    }

    // Zeige den Log-Bereich an und deaktiviere den Button
    const progressArea = document.getElementById('progressArea');
    progressArea.style.display = 'block';
    document.getElementById('logOutput').textContent = 'Initialisiere Konfiguration...';
    document.querySelector('#wifiForm button[type="submit"]').disabled = true;

    // Bereite die Daten für den POST-Request vor
    const taskData = {
        selectedShellies,
        userSsid,
        userPassword
    };

    try {
        // Sende die Aufgabe an das Backend
        await fetch('/api/configure', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(taskData)
        });

        // Starte das Polling, um den Fortschritt abzufragen
        progressInterval = setInterval(updateProgress, 2000); // Alle 2 Sekunden

    } catch (error) {
        document.getElementById('logOutput').textContent = 'FEHLER beim Starten der Konfiguration: ' + error.message;
        document.querySelector('#wifiForm button[type="submit"]').disabled = false;
    }
});

async function triggerScan() {
    const wifiListDiv = document.getElementById('wifiList');
    wifiListDiv.innerHTML = '<p>Manueller Scan gestartet, bitte warten...</p>';
    try {
        // Sende die Anfrage an unsere API, um den Scan auszulösen
        await fetch('/api/scan');
        
        // Gib dem Backend einen Moment Zeit, den Scan durchzuführen und die Datei zu schreiben
        setTimeout(loadWifiNetworks, 2000); // Warte 2 Sekunden, dann lade die Liste neu
    } catch (error) {
        wifiListDiv.innerHTML = `<p class="error-message">Fehler beim Auslösen des Scans: ${error.message}</p>`;
        console.error("Fehler beim Auslösen des Scans:", error);
    }
}

const HARDCODED_PIN = "0711";

// Funktion zur Überprüfung der PIN
function checkPin() {
    const pinInput = document.getElementById('pinInput').value;
    const pinError = document.getElementById('pinError');
    if (pinInput === HARDCODED_PIN) {
        document.getElementById('step1').style.display = 'none';
        document.getElementById('step2').style.display = 'block';
        loadWifiNetworks();
    } else {
        pinError.textContent = 'Falsche PIN!';
        // PIN-Feld leeren nach Fehleingabe
        document.getElementById('pinInput').value = '';
    }
}

// Funktion zum Laden und Anzeigen der WLAN-Netzwerke
async function loadWifiNetworks() {
    const wifiListDiv = document.getElementById('wifiList');
    wifiListDiv.innerHTML = '<p>Suche nach WLAN-Netzwerken...</p>';

    try {
        // Wir fügen einen Zeitstempel hinzu, um Caching zu verhindern
        const response = await fetch('wifi_list.json?' + new Date().getTime());
        if (!response.ok) {
            throw new Error(`Netzwerk-Antwort war nicht ok: ${response.statusText}`);
        }
        const ssids = await response.json();

        // Sortiere die SSIDs: "shelly"-Netzwerke zuerst, dann der Rest alphabetisch
        ssids.sort((a, b) => {
            const aIsShelly = a.toLowerCase().includes('shelly');
            const bIsShelly = b.toLowerCase().includes('shelly');
            if (aIsShelly && !bIsShelly) return -1;
            if (!aIsShelly && bIsShelly) return 1;
            return a.localeCompare(b);
        });

        wifiListDiv.innerHTML = ''; // Leere die Liste ("Suche...")

        if (ssids.length === 0) {
            wifiListDiv.innerHTML = '<p>Keine WLAN-Netzwerke gefunden. Bitte warte auf den nächsten Scan.</p>';
            return;
        }

        ssids.forEach(ssid => {
            const isShelly = ssid.toLowerCase().includes('shelly');
            
            const itemDiv = document.createElement('div');
            itemDiv.className = 'wifi-item';
            if (!isShelly) {
                itemDiv.classList.add('disabled');
            }

            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.id = ssid;
            checkbox.name = 'selected_shelly';
            checkbox.value = ssid;
            checkbox.disabled = !isShelly;

            const label = document.createElement('label');
            label.htmlFor = ssid;
            label.textContent = ssid;
            
            label.prepend(checkbox);
            itemDiv.appendChild(label);
            wifiListDiv.appendChild(itemDiv);
        });

    } catch (error) {
        wifiListDiv.innerHTML = `<p class="error-message">Fehler beim Laden der WLAN-Liste. Add-on-Logs prüfen.</p>`;
        console.error("Fehler beim Abrufen der WLAN-Liste:", error);
    }
}

// Event Listener für das Formular (Vorbereitung für Schritt 4)
document.getElementById('wifiForm').addEventListener('submit', function(event) {
    event.preventDefault(); // Standard-Formular-Aktion verhindern
    
    const selectedShellies = Array.from(document.querySelectorAll('input[name="selected_shelly"]:checked')).map(cb => cb.value);
    const userSsid = document.getElementById('userSsid').value;
    const userPassword = document.getElementById('userPassword').value;

    if (selectedShellies.length === 0) {
        alert('Bitte wähle mindestens ein Shelly-Gerät aus.');
        return;
    }

    if (!userSsid || !userPassword) {
        alert('Bitte gib die Zugangsdaten für dein WLAN ein.');
        return;
    }

    console.log("Ausgewählte Shellies:", selectedShellies);
    console.log("Benutzer-WLAN SSID:", userSsid);
    // Passwort aus Sicherheitsgründen nicht in der Konsole ausgeben
    
    alert('Konfiguration wird gestartet! (Diese Funktionalität wird in Schritt 4 implementiert)');
});