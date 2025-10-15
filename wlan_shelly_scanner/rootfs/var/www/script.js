const HARDCODED_PIN = "0711";
const HARDCODED_ADMIN_PASSWORD = "admin";

// === Globale Variablen ===
let progressInterval = null;
let adminDeviceList = []; // Für Admin-Modus
let userPin = ""; // Für Admin-Modus
let userShellyDeviceList = []; // Für User-Modus

// ====== MODUS-WECHSEL FUNKTIONEN ======

function showAdminLogin() {
    document.getElementById('userModeContainer').style.display = 'none';
    document.getElementById('adminPanel').style.display = 'none';
    document.getElementById('adminLogin').style.display = 'block';
    document.getElementById('adminError').textContent = '';
    document.getElementById('adminPasswordInput').value = '';
}

function checkAdminPassword() {
    const adminPassword = document.getElementById('adminPasswordInput').value;
    const adminError = document.getElementById('adminError');
    if (adminPassword === HARDCODED_ADMIN_PASSWORD) {
        document.getElementById('adminLogin').style.display = 'none';
        document.getElementById('adminPanel').style.display = 'block';
        document.getElementById('adminPinPrompt').style.display = 'block';
        document.getElementById('adminDeviceManager').style.display = 'none';
        document.getElementById('adminPinError').textContent = '';
        document.getElementById('adminUserPinInput').value = '';
    } else {
        adminError.textContent = 'Falsches Passwort!';
        document.getElementById('adminPasswordInput').value = '';
    }
}

function showUserMode() {
    document.getElementById('adminLogin').style.display = 'none';
    document.getElementById('adminPanel').style.display = 'none';
    document.getElementById('userModeContainer').style.display = 'block';
    restartUserMode(); // Setzt den User-Modus sauber zurück
}

// ====== BENUTZERMODUS FUNKTIONEN ======

function checkPin() {
    const pinInput = document.getElementById('pinInput').value;
    const pinError = document.getElementById('pinError');
    if (pinInput === HARDCODED_PIN) {
        document.getElementById('step1').style.display = 'none';
        document.getElementById('step2').style.display = 'block';
    } else {
        pinError.textContent = 'Falsche PIN!';
        document.getElementById('pinInput').value = '';
    }
}

async function loadAndScanForUser() {
    const pin = document.getElementById('pinInput').value;
    const userSsid = document.getElementById('userSsid').value;
    const userPassword = document.getElementById('userPassword').value;

    if (!userSsid || !userPassword) {
        alert("Bitte gib zuerst deine WLAN-Zugangsdaten ein.");
        return;
    }

    // 1. Lade die vom Admin vorbereitete Geräteliste
    try {
        const response = await fetch('api/admin/devices/load', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pin: pin })
        });
        if (!response.ok) throw new Error('Gespeicherte Geräteliste konnte nicht geladen werden. Wurde sie im Admin-Modus gespeichert?');
        userShellyDeviceList = await response.json();
    } catch (e) {
        alert(e.message);
        return;
    }

    // 2. Scanne nach allen aktuell sichtbaren WLANs
    let availableNetworks = [];
    try {
        const response = await fetch('api/scan');
        if (!response.ok) throw new Error('WLAN-Scan fehlgeschlagen.');
        availableNetworks = await response.json();
    } catch(e) {
        alert(e.message);
        return;
    }
    
    // 3. Wechsle die Ansicht und zeige die gemischte Liste an
    document.getElementById('userWifiCredentials').style.display = 'none';
    document.getElementById('userDeviceSelection').style.display = 'block';
    renderUserDeviceList(availableNetworks);
}

function renderUserDeviceList(availableNetworks) {
    const listDiv = document.getElementById('userShellyList');
    const notFoundDiv = document.getElementById('notFoundDevices');
    const notFoundList = document.getElementById('notFoundList');
    listDiv.innerHTML = '';
    notFoundList.innerHTML = '';
    let anyNotFound = false;

    const foundSsids = new Map(availableNetworks.map(net => [net.ssid, net.signal]));

    userShellyDeviceList.forEach(device => {
        if (foundSsids.has(device.ssid)) {
            const signal = foundSsids.get(device.ssid);
            const signalQuality = signal > 70 ? 'good' : signal > 40 ? 'medium' : 'poor';
            const itemHtml = `
                <div class="wifi-item">
                    <label>
                        <input type="checkbox" name="user_selected_shelly" value="${device.mac}" checked>
                        <strong>${device.haName || device.model}</strong> (${device.bemerkung || 'Keine Bemerkung'})
                        <span class="signal-strength ${signalQuality}">Signal: ${signal}%</span>
                    </label>
                </div>
            `;
            listDiv.innerHTML += itemHtml;
        } else {
            anyNotFound = true;
            const itemHtml = `<li>${device.haName || device.model} (${device.bemerkung || 'Keine Bemerkung'})</li>`;
            notFoundList.innerHTML += itemHtml;
        }
    });
    
    notFoundDiv.style.display = anyNotFound ? 'block' : 'none';
}

async function startUserConfiguration() {
    const userSsid = document.getElementById('userSsid').value;
    const userPassword = document.getElementById('userPassword').value;

    const selectedMacs = Array.from(document.querySelectorAll('input[name="user_selected_shelly"]:checked')).map(cb => cb.value);
    const devicesToConfigure = userShellyDeviceList.filter(dev => selectedMacs.includes(dev.mac));

    if (devicesToConfigure.length === 0) {
        alert('Bitte wähle mindestens ein gefundenes Gerät aus.');
        return;
    }
    
    document.getElementById('userDeviceSelection').style.display = 'none';
    document.getElementById('userProgressArea').style.display = 'block';
    document.getElementById('userLogOutput').textContent = 'Initialisiere Konfiguration...\n';
    
    await fetch('api/configure', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            selectedDevices: devicesToConfigure,
            userSsid: userSsid,
            userPassword: userPassword
        })
    });

    progressInterval = setInterval(updateProgressForUser, 2000);
}

async function updateProgressForUser() {
    const logOutput = document.getElementById('userLogOutput');
    try {
        const response = await fetch('api/progress?' + new Date().getTime());
        const progressText = await response.text();
        logOutput.textContent = progressText;
        logOutput.scrollTop = logOutput.scrollHeight;
        
        if (progressText.includes("Konfiguration abgeschlossen")) {
            clearInterval(progressInterval);
        }
    } catch (error) {
        logOutput.textContent += "\nFehler beim Abrufen des Fortschritts.";
        clearInterval(progressInterval);
    }
}

function restartUserMode() {
    if(progressInterval) clearInterval(progressInterval);
    document.getElementById('userWifiCredentials').style.display = 'block';
    document.getElementById('userDeviceSelection').style.display = 'none';
    document.getElementById('userProgressArea').style.display = 'none';
    document.getElementById('userSsid').value = '';
    document.getElementById('userPassword').value = '';
}


// ====== ADMIN-MODUS FUNKTIONEN ======

function adminLog(message) {
    const logOutput = document.getElementById('adminDebugLog');
    if (!logOutput) return;
    const timestamp = new Date().toLocaleTimeString();
    logOutput.textContent += `[${timestamp}] ${message}\n`;
    logOutput.scrollTop = logOutput.scrollHeight;
}

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
        const response = await fetch('api/admin/devices/load', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pin: userPin })
        });

        if (response.status === 400) throw new Error('Entschlüsselung fehlgeschlagen. Falsche PIN?');
        if (!response.ok) throw new Error(`Serverfehler: ${response.status}`);

        adminDeviceList = await response.json();
        
        document.getElementById('adminPinPrompt').style.display = 'none';
        document.getElementById('adminDeviceManager').style.display = 'block';
        
        renderDeviceTable();
        adminLog(`Erfolgreich ${adminDeviceList.length} Gerät(e) aus der Liste geladen.`);

    } catch (error) {
        errorP.textContent = `Fehler: ${error.message}`;
        console.error('Fehler beim Laden der Geräte:', error);
    }
}

function renderDeviceTable() {
    const tableBody = document.querySelector('#deviceListTable tbody');
    tableBody.innerHTML = '';

    if (adminDeviceList.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="5">Keine Geräte in der Liste. Starte einen Scan, um neue Geräte zu finden.</td></tr>';
        return;
    }
    
    adminDeviceList.forEach(device => {
        const tr = document.createElement('tr');
        tr.id = `row-${device.mac}`;

        tr.innerHTML = `
            <td><strong>${device.model || 'Unbekannt'}</strong><br><small>${device.ssid}</small></td>
            <td>${device.generation || 'N/A'}</td>
            <td>${device.bemerkung || ''}</td>
            <td>${device.haName || ''}</td>
            <td>
                <button class="table-button" onclick="editDeviceRow('${device.mac}')">Bearbeiten</button>
                <button class="table-button delete-btn" onclick="deleteDeviceRow('${device.mac}')">Löschen</button>
            </td>
        `;
        tableBody.appendChild(tr);
    });
}

function editDeviceRow(mac) {
    const device = adminDeviceList.find(d => d.mac === mac);
    if (!device) return;

    const row = document.getElementById(`row-${mac}`);
    
    if (!device.haName) {
        device.haName = generateHaName(device);
    }
    
    // Die Spalten sind jetzt: Modell, Gen, Bemerkung, HA-Name, Aktionen
    row.cells[2].innerHTML = `<input type="text" class="editable-input" value="${device.bemerkung || ''}" placeholder="z.B. Wohnzimmer Decke">`;
    row.cells[3].innerHTML = `<input type="text" class="editable-input" value="${device.haName || ''}">`;
    row.cells[4].innerHTML = `
        <button class="table-button save-row-btn" onclick="saveDeviceRow('${mac}')">OK</button>
        <button class="table-button" onclick="renderDeviceTable()">Abbrechen</button>
    `;
}

function saveDeviceRow(mac) {
    const device = adminDeviceList.find(d => d.mac === mac);
    if (!device) return;

    const row = document.getElementById(`row-${mac}`);
    
    const bemerkungInput = row.cells[2].querySelector('input');
    const haNameInput = row.cells[3].querySelector('input');

    device.bemerkung = bemerkungInput.value;
    device.haName = haNameInput.value;

    renderDeviceTable();
}

function deleteDeviceRow(mac) {
    if (confirm(`Soll das Gerät mit der MAC ${mac} wirklich aus der Liste gelöscht werden?`)) {
        adminDeviceList = adminDeviceList.filter(d => d.mac !== mac);
        renderDeviceTable();
        adminLog(`Gerät mit MAC ${mac} aus der Liste entfernt. Nicht vergessen zu speichern!`);
    }
}

async function scanForNewDevices() {
    const scanButton = document.querySelector('#adminDeviceManager .scan-button');
    const originalText = scanButton.textContent;
    scanButton.textContent = 'Scanne...';
    scanButton.disabled = true;
    adminLog("Manueller Scan für neue Geräte gestartet...");

    try {
        const response = await fetch('api/admin/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ devices: adminDeviceList })
        });

        const responseData = await response.json();

        if (responseData.logs && responseData.logs.length > 0) {
            responseData.logs.forEach(logMsg => adminLog(logMsg));
        }

        if (!response.ok) throw new Error(responseData.details || 'Scan auf dem Server fehlgeschlagen');

        const newDevices = responseData.new_devices || [];
        if (newDevices.length > 0) {
            newDevices.forEach(dev => adminDeviceList.push(dev));
            adminLog(`ERFOLG: ${newDevices.length} neue(s) Shelly-Gerät(e) gefunden und zur Liste hinzugefügt.`);
            renderDeviceTable();
        } else {
            adminLog("INFO: Scan beendet. Keine *neuen* Shelly-Geräte im AP-Modus gefunden.");
        }

    } catch (error) {
        adminLog(`FEHLER beim Scannen: ${error.message}`);
        console.error('Scan-Fehler:', error);
    } finally {
        scanButton.textContent = originalText;
        scanButton.disabled = false;
    }
}

async function saveChangesToServer() {
    if (!userPin) {
        adminLog("FEHLER: Speichern nicht möglich. Keine gültige PIN vorhanden. Bitte lade die Liste neu.");
        return;
    }
    adminLog("Speichere Änderungen auf dem Server...");
    
    try {
        const response = await fetch('api/admin/devices/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pin: userPin, devices: adminDeviceList })
        });

        if (!response.ok) throw new Error(`Speichern fehlgeschlagen: ${response.statusText}`);
        
        adminLog(`ERFOLG: ${adminDeviceList.length} Gerät(e) erfolgreich verschlüsselt und gespeichert.`);

    } catch (error) {
        adminLog(`FEHLER beim Speichern: ${error.message}`);
        console.error('Speicher-Fehler:', error);
    }
}

function generateHaName(device) {
    const bemerkung = device.bemerkung || 'Unbenannt';
    const model = (device.model || 'Shelly').replace(/\s/g, '');
    const macPart = device.mac.slice(-6);
    return `${bemerkung}-${model}-${macPart}`;
}