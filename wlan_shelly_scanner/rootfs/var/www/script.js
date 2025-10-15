const HARDCODED_PIN = "0711";
const HARDCODED_ADMIN_PASSWORD = "0711Admin!"; // Neues Admin-Passwort

// Globale Variable für das Polling-Interval, damit wir es stoppen können
let progressInterval = null;
let adminDeviceList = [];
let userPin = "";

/**
 * Blendet den Benutzermodus aus und zeigt den Admin-Login an.
 */
function showAdminLogin() {
    document.getElementById('userModeContainer').style.display = 'none';
    document.getElementById('adminPanel').style.display = 'none'; // Admin-Panel auch ausblenden
    document.getElementById('adminLogin').style.display = 'block';
    document.getElementById('adminError').textContent = '';
    document.getElementById('adminPasswordInput').value = '';
}

/**
 * Überprüft das eingegebene Admin-Passwort und zeigt die PIN-Abfrage für die Geräteliste.
 */
function checkAdminPassword() {
    const adminPassword = document.getElementById('adminPasswordInput').value;
    const adminError = document.getElementById('adminError');
    if (adminPassword === HARDCODED_ADMIN_PASSWORD) {
        document.getElementById('adminLogin').style.display = 'none';
        
        // Zeige jetzt die PIN-Abfrage für die Geräteliste an
        document.getElementById('adminPanel').style.display = 'block';
        document.getElementById('adminPinPrompt').style.display = 'block';
        document.getElementById('adminDeviceManager').style.display = 'none'; // Verwalter noch ausblenden
        document.getElementById('adminPinError').textContent = '';
        document.getElementById('adminUserPinInput').value = '';

    } else {
        adminError.textContent = 'Falsches Passwort!';
        document.getElementById('adminPasswordInput').value = '';
    }
}

/**
 * Setzt die Ansicht auf den ursprünglichen Benutzermodus zurück.
 */
function showUserMode() {
    document.getElementById('adminLogin').style.display = 'none';
    document.getElementById('adminPanel').style.display = 'none';
    document.getElementById('userModeContainer').style.display = 'block';
    
    // Setze den User-Modus auf den initialen Zustand zurück (PIN-Abfrage)
    document.getElementById('step1').style.display = 'block';
    document.getElementById('step2').style.display = 'none';
    document.getElementById('pinInput').value = ''; // PIN-Feld leeren
    document.getElementById('pinError').textContent = '';
}

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

// script.js

// ====== NEUE FUNKTIONEN FÜR DIE GERÄTEVERWALTUNG ======

/**
 * Lädt die verschlüsselte Geräteliste vom Server.
 */
async function loadAndDisplayDevices() {
    const pinInput = document.getElementById('adminUserPinInput');
    const errorP = document.getElementById('adminPinError');
    userPin = pinInput.value;
    errorP.textContent = 'Lade und entschlüssle...';

    if (!userPin) {
        errorP.textContent = 'Bitte gib eine PIN ein.';
        return;
    }

    try {
        const response = await fetch('/api/admin/devices/load', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pin: userPin })
        });

        if (response.status === 400) {
            throw new Error('Entschlüsselung fehlgeschlagen. Falsche PIN?');
        }
        if (!response.ok) {
            throw new Error(`Serverfehler: ${response.status}`);
        }

        adminDeviceList = await response.json();
        
        // Wechsle zur Verwaltungsansicht
        document.getElementById('adminPinPrompt').style.display = 'none';
        document.getElementById('adminDeviceManager').style.display = 'block';
        
        renderDeviceTable();

    } catch (error) {
        errorP.textContent = `Fehler: ${error.message}`;
        console.error('Fehler beim Laden der Geräte:', error);
    }
}

/**
 * Zeichnet die Tabelle mit den Geräten aus der globalen `adminDeviceList`.
 */
function renderDeviceTable() {
    const tableBody = document.querySelector('#deviceListTable tbody');
    tableBody.innerHTML = ''; // Leere die Tabelle

    if (adminDeviceList.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="4">Keine Geräte in der Liste. Starte einen Scan, um neue Geräte zu finden.</td></tr>';
        return;
    }
    
    adminDeviceList.forEach(device => {
        const tr = document.createElement('tr');
        tr.id = `row-${device.mac}`; // Eindeutige ID für die Zeile

        // Zelle 1: Modell / SSID
        const tdModel = document.createElement('td');
        tdModel.innerHTML = `<strong>${device.model || 'Unbekannt'}</strong><br><small>${device.ssid}</small>`;
        
        // Zelle 2: Bemerkung / Raum
        const tdBemerkung = document.createElement('td');
        tdBemerkung.textContent = device.bemerkung;
        
        // Zelle 3: Name für Home Assistant
        const tdHaName = document.createElement('td');
        tdHaName.textContent = device.haName || ''; // Verwende haName oder leer

        // Zelle 4: Aktionen
        const tdActions = document.createElement('td');
        tdActions.innerHTML = `
            <button class="table-button" onclick="editDeviceRow('${device.mac}')">Bearbeiten</button>
            <button class="table-button delete-btn" onclick="deleteDeviceRow('${device.mac}')">Löschen</button>
        `;

        tr.appendChild(tdModel);
        tr.appendChild(tdBemerkung);
        tr.appendChild(tdHaName);
        tr.appendChild(tdActions);
        tableBody.appendChild(tr);
    });
}

/**
 * Wandelt eine Zeile in den Bearbeitungsmodus um.
 * @param {string} mac Die MAC-Adresse des Geräts.
 */
function editDeviceRow(mac) {
    const device = adminDeviceList.find(d => d.mac === mac);
    if (!device) return;

    const row = document.getElementById(`row-${mac}`);
    
    // Generiere einen sinnvollen Namen, falls noch keiner existiert
    if (!device.haName) {
        device.haName = generateHaName(device);
    }

    row.cells[1].innerHTML = `<input type="text" class="editable-input" value="${device.bemerkung}" placeholder="z.B. Wohnzimmer Decke">`;
    row.cells[2].innerHTML = `<input type="text" class="editable-input" value="${device.haName}">`;
    row.cells[3].innerHTML = `
        <button class="table-button save-row-btn" onclick="saveDeviceRow('${mac}')">OK</button>
        <button class="table-button" onclick="renderDeviceTable()">Abbrechen</button>
    `;
}

/**
 * Speichert die Änderungen aus dem Bearbeitungsmodus in das globale Array.
 * @param {string} mac Die MAC-Adresse des Geräts.
 */
function saveDeviceRow(mac) {
    const device = adminDeviceList.find(d => d.mac === mac);
    if (!device) return;

    const row = document.getElementById(`row-${mac}`);
    
    const bemerkungInput = row.cells[1].querySelector('input');
    const haNameInput = row.cells[2].querySelector('input');

    // Aktualisiere das Objekt im Array
    device.bemerkung = bemerkungInput.value;
    device.haName = haNameInput.value;

    // Neu zeichnen, um den Bearbeitungsmodus zu beenden
    renderDeviceTable();
}

/**
 * Löscht ein Gerät aus der Liste (nach Bestätigung).
 * @param {string} mac Die MAC-Adresse des Geräts.
 */
function deleteDeviceRow(mac) {
    if (confirm(`Soll das Gerät mit der MAC ${mac} wirklich aus der Liste gelöscht werden?`)) {
        adminDeviceList = adminDeviceList.filter(d => d.mac !== mac);
        renderDeviceTable();
    }
}

/**
 * Scannt nach neuen, noch nicht in der Liste vorhandenen Geräten.
 */
async function scanForNewDevices() {
    const scanButton = document.querySelector('.scan-button');
    const originalText = scanButton.textContent;
    scanButton.textContent = 'Scanne...';
    scanButton.disabled = true;

    try {
        const response = await fetch('/api/admin/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ devices: adminDeviceList })
        });

        if (!response.ok) {
            throw new Error(`Scan fehlgeschlagen: ${response.statusText}`);
        }

        const newDevices = await response.json();
        if (newDevices.length > 0) {
            newDevices.forEach(dev => adminDeviceList.push(dev));
            alert(`${newDevices.length} neue(s) Shelly-Gerät(e) gefunden und zur Liste hinzugefügt.`);
            renderDeviceTable();
        } else {
            alert('Keine neuen Shelly-Geräte im AP-Modus gefunden.');
        }

    } catch (error) {
        alert(`Fehler beim Scannen: ${error.message}`);
        console.error('Scan-Fehler:', error);
    } finally {
        scanButton.textContent = originalText;
        scanButton.disabled = false;
    }
}

/**
 * Speichert die komplette Geräteliste verschlüsselt auf dem Server.
 */
async function saveChangesToServer() {
    if (!userPin) {
        alert("Fehler: Keine gültige PIN vorhanden. Bitte lade die Liste neu.");
        return;
    }
    
    try {
        const response = await fetch('/api/admin/devices/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pin: userPin, devices: adminDeviceList })
        });

        if (!response.ok) {
            throw new Error(`Speichern fehlgeschlagen: ${response.statusText}`);
        }

        alert(`Erfolgreich ${adminDeviceList.length} Gerät(e) gespeichert.`);

    } catch (error) {
        alert(`Fehler beim Speichern: ${error.message}`);
        console.error('Speicher-Fehler:', error);
    }
}

/**
 * Generiert einen Vorschlag für einen Home Assistant Namen.
 * @param {object} device Das Geräteobjekt.
 */
function generateHaName(device) {
    const bemerkung = device.bemerkung || 'Unbenannt';
    const model = (device.model || 'Shelly').replace(/\s/g, ''); // Leerzeichen entfernen
    const macPart = device.mac.slice(-6); // Letzte 6 Zeichen der MAC
    return `${bemerkung}-${model}-${macPart}`;
}