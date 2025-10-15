const HARDCODED_PIN = "0711";

// Globale Variable für das Polling-Interval, damit wir es stoppen können
let progressInterval = null;

/**
 * Überprüft die eingegebene PIN und zeigt bei Erfolg den Hauptbereich an.
 */
function checkPin() {
    const pinInput = document.getElementById('pinInput').value;
    const pinError = document.getElementById('pinError');
    if (pinInput === HARDCODED_PIN) {
        document.getElementById('step1').style.display = 'none';
        document.getElementById('step2').style.display = 'block';
        
        // WIR LADEN DIE LISTE HIER NICHT MEHR AUTOMATISCH
        // loadWifiNetworks(); // <-- Diese Zeile entfernen oder auskommentieren
        
        // Stattdessen zeigen wir eine Aufforderung an
        document.getElementById('wifiList').innerHTML = '<p>Bitte starte einen neuen Scan, um nach Shelly-Netzwerken zu suchen.</p>';

    } else {
        pinError.textContent = 'Falsche PIN!';
        document.getElementById('pinInput').value = '';
    }
}

/**
 * Löst einen neuen WLAN-Scan im Backend aus und zeigt das Ergebnis direkt an.
 */
async function triggerScan() {
    const wifiListDiv = document.getElementById('wifiList');
    const scanButton = document.querySelector('.scan-button');
    
    wifiListDiv.innerHTML = '<p>Scan wird ausgeführt, bitte warten...</p>';
    scanButton.disabled = true; // Button deaktivieren, um Doppelklicks zu verhindern

    try {
        // Der fetch-Aufruf löst jetzt den Scan aus UND wartet auf die Antwort
        const response = await fetch('api/scan');
        
        if (!response.ok) {
            // Versuche, eine detaillierte Fehlermeldung vom Backend zu bekommen
            const errorData = await response.json().catch(() => null);
            throw new Error(errorData?.details || `HTTP-Fehler ${response.status}`);
        }
        
        const ssids = await response.json();
        
        // Die Funktion zur Anzeige der Liste direkt mit den neuen Daten aufrufen
        displayWifiList(ssids);

    } catch (error) {
        wifiListDiv.innerHTML = `<p class="error-message">Fehler beim Scan: ${error.message}</p>`;
        console.error("Fehler beim Auslösen des Scans:", error);
    } finally {
        scanButton.disabled = false; // Button in jedem Fall wieder aktivieren
    }
}

// script.js

/**
 * Nimmt eine Liste von SSIDs entgegen und rendert die Checkbox-Liste im HTML.
 * @param {string[]} ssids - Ein Array von WLAN-Namen.
 */
function displayWifiList(ssids) {
    const wifiListDiv = document.getElementById('wifiList');

    // Sortiere Netzwerke, zeige Shelly-Netze zuerst an
    ssids.sort((a, b) => {
        const aIsShelly = a.toLowerCase().includes('shelly');
        const bIsShelly = b.toLowerCase().includes('shelly');
        if (aIsShelly && !bIsShelly) return -1;
        if (!aIsShelly && bIsShelly) return 1;
        return a.localeCompare(b);
    });

    wifiListDiv.innerHTML = ''; // Leere die Liste vor dem Neuaufbau
    if (ssids.length === 0) {
        wifiListDiv.innerHTML = '<p>Keine WLAN-Netzwerke gefunden. Bitte stelle sicher, dass die Shelly-Geräte im Setup-Modus sind und starte einen neuen Scan.</p>';
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
}

/**
 * Fragt den Konfigurationsfortschritt vom Backend ab und zeigt ihn an.
 */
async function updateProgress() {
    const logOutput = document.getElementById('logOutput');
    try {
        // HIER DIE KORREKTUR: Führender Schrägstrich entfernt
        const response = await fetch('api/progress?' + new Date().getTime());
        const progressText = await response.text();
        logOutput.textContent = progressText;
        logOutput.scrollTop = logOutput.scrollHeight;
        
        if (progressText.includes("abgeschlossen")) {
            clearInterval(progressInterval);
            document.querySelector('#wifiForm button[type="submit"]').disabled = false;
        }
    } catch (error) {
        logOutput.textContent += "\nFehler beim Abrufen des Fortschritts.";
        clearInterval(progressInterval);
        document.querySelector('#wifiForm button[type="submit"]').disabled = false;
    }
}

/**
 * Event Listener für das Absenden des Konfigurations-Formulars.
 */
document.getElementById('wifiForm').addEventListener('submit', async function(event) {
    event.preventDefault(); 
    
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

    const progressArea = document.getElementById('progressArea');
    progressArea.style.display = 'block';
    document.getElementById('logOutput').textContent = 'Initialisiere Konfiguration...';
    document.querySelector('#wifiForm button[type="submit"]').disabled = true;

    const taskData = {
        selectedShellies,
        userSsid,
        userPassword
    };

    try {
        // HIER DIE KORREKTUR: Führender Schrägstrich entfernt
        await fetch('api/configure', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(taskData)
        });

        progressInterval = setInterval(updateProgress, 2000);

    } catch (error) {
        document.getElementById('logOutput').textContent = 'FEHLER beim Starten der Konfiguration: ' + error.message;
        document.querySelector('#wifiForm button[type="submit"]').disabled = false;
    }
});