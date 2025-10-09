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
 * Löst einen neuen WLAN-Scan im Backend aus und aktualisiert danach die Liste.
 */
async function triggerScan() {
    const wifiListDiv = document.getElementById('wifiList');
    wifiListDiv.innerHTML = '<p>Manueller Scan gestartet, bitte warten...</p>';
    try {
        // Sage dem Backend, es soll einen neuen Scan starten
        await fetch('api/scan');
        
        // Gib dem Scan etwas Zeit (z.B. 5-7 Sekunden, da er bei dir ca. 5s dauert)
        // und lade ERST DANN die Ergebnisse.
        setTimeout(loadWifiNetworks, 7000); 

    } catch (error) {
        wifiListDiv.innerHTML = `<p class="error-message">Fehler beim Auslösen des Scans: ${error.message}</p>`;
        console.error("Fehler beim Auslösen des Scans:", error);
    }
}

// Die Funktion loadWifiNetworks() selbst bleibt unverändert.

/**
 * Lädt die Liste der gefundenen WLAN-Netzwerke vom Backend.
 */
async function loadWifiNetworks() {
    const wifiListDiv = document.getElementById('wifiList');
    wifiListDiv.innerHTML = '<p>Suche nach WLAN-Netzwerken...</p>';

    try {
        // Dieser Aufruf war bereits korrekt (ohne führenden Schrägstrich)
        const response = await fetch('wifi_list.json?' + new Date().getTime());
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const ssids = await response.json();
        
        // ... Rest der Funktion bleibt unverändert ...
        ssids.sort((a, b) => {
            const aIsShelly = a.toLowerCase().includes('shelly');
            const bIsShelly = b.toLowerCase().includes('shelly');
            if (aIsShelly && !bIsShelly) return -1;
            if (!aIsShelly && bIsShelly) return 1;
            return a.localeCompare(b);
        });
        wifiListDiv.innerHTML = ''; 
        if (ssids.length === 0) {
            wifiListDiv.innerHTML = '<p>Keine WLAN-Netzwerke gefunden.</p>';
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
        wifiListDiv.innerHTML = `<p class="error-message">Fehler beim Laden der WLAN-Liste: ${error.message}</p>`;
        console.error("Fehler:", error);
    }
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