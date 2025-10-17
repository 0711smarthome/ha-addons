// script.js - v2.8.0

// === CONFIGURATION ===
const HARDCODED_ADMIN_PASSWORD = "admin";

// === GLOBAL STATE ===
let adminDeviceList = [];
let userDeviceList = [];
let userPIN = "";

// ====== UI HELPER FUNCTIONS ======
function showToast(message, type = 'info') {
    const container = document.querySelector('.toast-container');
    const toastEl = document.createElement('div');
    const toastColors = { success: 'bg-success', danger: 'bg-danger', warning: 'bg-warning', info: 'bg-info' };
    toastEl.className = `toast align-items-center text-white ${toastColors[type] || 'bg-secondary'} border-0`;
    toastEl.innerHTML = `<div class="d-flex"><div class="toast-body">${message}</div><button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>`;
    container.appendChild(toastEl);
    const toast = new bootstrap.Toast(toastEl, { delay: 4000 });
    toast.show();
    toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
}

function toggleSpinner(spinnerId, show) {
    document.getElementById(spinnerId)?.classList.toggle('d-none', !show);
}


// ======POLL USER Progess ======
async function pollUserProgress(interval = 1500) {
    userLog('INFO: Starte Fortschrittsabfrage (Polling) des Backend-Logs...');
    const logOutput = document.getElementById('userDebugLog');
    const configureBtn = document.getElementById('configureBtn');
    
    // Timer-Loop
    const poller = setInterval(async () => {
        try {
            const response = await fetch('api/progress');
            if (!response.ok) {
                userLog('FEHLER beim Abrufen des Fortschritts-Logs.');
                clearInterval(poller);
                return;
            }
            
            const newLogContent = await response.text();
            
            // Log-Ausgabe nur aktualisieren, wenn sie sich unterscheidet
            if (logOutput.textContent.trim() !== newLogContent.trim()) {
                logOutput.textContent = newLogContent + '\n';
                logOutput.scrollTop = logOutput.scrollHeight;
            }
            
            // Prüfen, ob der Konfigurationsprozess abgeschlossen ist (durch Log-Schlüsselwörter)
            if (newLogContent.includes('--- Konfiguration abgeschlossen ---')) {
                clearInterval(poller); // Polling beenden
                configureBtn.disabled = false; // Button wieder aktivieren
                showToast('Konfiguration abgeschlossen. Details im Log.', 'success');
                userLog('INFO: Polling beendet. Konfigurations-Task abgeschlossen.');

                // Optional: Liste neu scannen, um Status zu aktualisieren
                // await scanForUserDevices(); 
            }
        } catch (e) {
            userLog(FEHLER während des Polling: ${e.message}`);
            clearInterval(poller);
            configureBtn.disabled = false;
        }
    }, interval);
}

// ====== MODE SWITCHING LOGIC ======
function showAdminLogin() {
    document.getElementById('userModeContainer').classList.add('d-none');
    document.getElementById('adminPanel').classList.add('d-none');
    document.getElementById('adminLogin').classList.remove('d-none');
}

function checkAdminPassword() {
    const adminPassword = document.getElementById('adminPasswordInput').value;
    if (adminPassword === HARDCODED_ADMIN_PASSWORD) {
        document.getElementById('adminLogin').classList.add('d-none');
        document.getElementById('adminPanel').classList.remove('d-none');
        adminLog('Admin-Modus entsperrt. Geben Sie die PIN ein und klicken Sie auf "Laden", um eine bestehende Liste zu bearbeiten, oder starten Sie einen Scan.');
    } else {
        showToast('Falsches Admin-Passwort!', 'danger');
    }
}

function showUserMode() {
    document.getElementById('adminLogin').classList.add('d-none');
    document.getElementById('adminPanel').classList.add('d-none');
    document.getElementById('userModeContainer').classList.remove('d-none');
    document.getElementById('userPinStep').classList.remove('d-none');
    document.getElementById('userMainStep').classList.add('d-none');
    document.getElementById('pinInput').value = '';
}

// ====== USER MODE LOGIC ======
function userLog(message) {
    const logOutput = document.getElementById('userDebugLog');
    if (!logOutput) return;
    const timestamp = new Date().toLocaleTimeString('de-DE');
    logOutput.textContent += `[${timestamp}] ${message}\n`;
    logOutput.scrollTop = logOutput.scrollHeight;
}

async function loadDeviceListForUser() {
    userPIN = document.getElementById('pinInput').value;
    if (!userPIN) { showToast('Bitte PIN eingeben.', 'warning'); return; }
    userLog('Lade und entschlüssle Geräteliste...');
    try {
        const response = await fetch('api/admin/devices/load', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pin: userPIN }) });
        if (response.status === 400) throw new Error('Entschlüsselung fehlgeschlagen. Falsche PIN?');
        if (!response.ok) throw new Error('Geräteliste konnte nicht geladen werden.');
        userDeviceList = await response.json();
        userLog(`Geladene JSON-Liste:\n${JSON.stringify(userDeviceList, null, 2)}`);
        userLog(`Erfolgreich ${userDeviceList.length} Gerät(e) geladen.`);
        document.getElementById('userPinStep').classList.add('d-none');
        document.getElementById('userMainStep').classList.remove('d-none');
        showToast('Geräteliste geladen.', 'success');
    } catch (e) {
        userLog(`FEHLER: ${e.message}`);
        showToast(e.message, 'danger');
    }
}

async function scanForUserDevices() {
    userLog('Starte umfassenden Scan (WLAN-AP & Lokales Netzwerk)...');
    toggleSpinner('scanUserBtnSpinner', true);
    document.getElementById('scanUserBtn').disabled = true;
    try {
        const [apResponse, lanResponse] = await Promise.all([ fetch('api/scan'), fetch('api/lan_scan') ]);
        if (!apResponse.ok) throw new Error('WLAN-Scan (AP) fehlgeschlagen.');
        if (!lanResponse.ok) throw new Error('Netzwerk-Scan (LAN) fehlgeschlagen.');
        const availableAPs = await apResponse.json();
        const onlineDevices = await lanResponse.json();
        userLog(`WLAN-Scan: ${availableAPs.length} Netzwerke gefunden. Darunter: ${availableAPs.map(n => n.ssid).join(', ')}`);
        userLog(`LAN-Scan: ${onlineDevices.length} Online-Shellys gefunden: ${onlineDevices.map(d => d.hostname).join(', ')}`);
        renderUserDeviceList(availableAPs, onlineDevices);
    } catch (e) {
        userLog(`FEHLER beim Scan: ${e.message}`);
        showToast(e.message, 'danger');
    } finally {
        toggleSpinner('scanUserBtnSpinner', false);
        document.getElementById('scanUserBtn').disabled = false;
    }
}

function renderUserDeviceList(availableAPs, onlineDevices) {
    const tableBody = document.querySelector('#userShellyTable tbody');
    const notFoundList = document.getElementById('notFoundList');
    tableBody.innerHTML = '';
    notFoundList.innerHTML = '';
    let anyFound = false, anyNotFound = false;
    const foundSsids = new Map(availableAPs.map(net => [net.ssid, net.signal]));
    const onlineHostnames = new Set(onlineDevices.map(dev => dev.hostname.toLowerCase()));

    userDeviceList.forEach(device => {
        const logName = device.haName || device.model || device.mac;
        const expectedHostname = `shelly${(device.model || '').replace(/Shelly /g, '')}-${device.mac}`.toLowerCase();
        const isAlreadyOnline = onlineHostnames.has(expectedHostname);
        const apIsVisible = foundSsids.has(device.ssid);
        let signalCell = '', disabled = '', checked = 'checked';

        if (isAlreadyOnline) {
            userLog(`Gerät "${logName}" ist bereits im LAN online (Hostname: ${expectedHostname}). Auswahl wird deaktiviert.`);
            signalCell = '<span class="badge bg-success">Online im LAN</span>';
            disabled = 'disabled'; checked = '';
        } else if (apIsVisible) {
            userLog(`Gerät "${logName}" im AP-Modus gefunden (SSID: ${device.ssid}).`);
            const signal = foundSsids.get(device.ssid);
            const signalClass = signal > 70 ? 'signal-good' : signal > 40 ? 'signal-medium' : 'signal-poor';
            signalCell = `<span class="fw-bold ${signalClass}">${signal}%</span>`;
            anyFound = true;
        } else {
            userLog(`- Gerät "${logName}" wurde weder im LAN noch als AP gefunden.`);
            anyNotFound = true;
            notFoundList.innerHTML += `<li>${device.haName || device.model}</li>`;
            return;
        }
        
        const lastConfiguredText = device.lastConfigured || 'Nie';

        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td class="align-middle"><input class="form-check-input" type="checkbox" value="${device.mac}" name="user_selected_shelly" ${checked} ${disabled}></td>
            <td class="align-middle"><strong>${device.haName || 'N/A'}</strong><br><small class="text-muted">${device.bemerkung || 'k.A.'}</small></td>
            <td class="align-middle">${device.model || 'N/A'}<br><small class="text-muted">${device.ssid || 'N/A'}</small></td>
            <td class="align-middle">${signalCell}</td>
            <td class="align-middle small">${lastConfiguredText}</td>
        `;
        tableBody.appendChild(tr);
    });
    
    document.getElementById('userDeviceListContainer').classList.remove('d-none');
    document.getElementById('notFoundDevices').classList.toggle('d-none', !anyNotFound);
    document.getElementById('configureBtn').disabled = !anyFound;
    userLog('INFO: Geräteliste aktualisiert.');
}

async function startUserConfiguration() {
    const userSsid = document.getElementById('userSsid').value, userPassword = document.getElementById('userPassword').value;
    if (!userSsid || !userPassword) { showToast('WLAN-Zugangsdaten dürfen nicht leer sein.', 'warning'); return; }
    const selectedMacs = Array.from(document.querySelectorAll('input[name="user_selected_shelly"]:checked')).map(cb => cb.value);
    const devicesToConfigure = userDeviceList.filter(dev => selectedMacs.includes(dev.mac));
    if (devicesToConfigure.length === 0) { showToast('Keine Geräte zur Konfiguration ausgewählt.', 'warning'); return; }
    
    // --- Vorbereitung ---
    userLog(Starte Konfiguration für ${devicesToConfigure.length} Gerät(e)...);
    document.getElementById('configureBtn').disabled = true;
    
    try {
        // 1. Task an Backend senden
        const response = await fetch('api/configure', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ selectedDevices: devicesToConfigure, userSsid, userPassword }) });
        if (!response.ok) throw new Error('Konfigurations-Task konnte nicht gestartet werden.');
        
        // 2. Frontend-Listen-Timestamp aktualisieren und speichern
        const now = new Date().toLocaleString('de-DE');
        userDeviceList.forEach(device => { if (selectedMacs.includes(device.mac)) device.lastConfigured = now; });
        await fetch('api/admin/devices/save', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pin: userPIN, devices: userDeviceList }) });
        userLog("Timestamp für konfigurierte Geräte in der Liste gespeichert.");
        
        // 3. NEU: Polling des Fortschritts starten
        await pollUserProgress(); 

    } catch (e) {
        userLog(FEHLER: ${e.message});
        showToast(e.message, 'danger');
        document.getElementById('configureBtn').disabled = false; // Button wieder aktivieren bei Fehler
    }
}

// ====== ADMIN MODE LOGIC ======
function adminLog(message) {
    const logOutput = document.getElementById('adminDebugLog');
    if (!logOutput) return;
    const timestamp = new Date().toLocaleTimeString('de-DE');
    logOutput.textContent += `[${timestamp}] ${message}\n`;
    logOutput.scrollTop = logOutput.scrollHeight;
}

async function loadAndDisplayDevicesForAdmin() {
    const pinInput = document.getElementById('adminPinInput');
    userPIN = pinInput.value;
    if (!userPIN) { showToast('Bitte PIN für die Liste eingeben.', 'warning'); return; }
    adminLog(`Lade Geräteliste mit PIN: ${userPIN}...`);
    try {
        const response = await fetch('api/admin/devices/load', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pin: userPIN }) });
        if (response.status === 400) throw new Error('Entschlüsselung fehlgeschlagen. Falsche PIN?');
        if (!response.ok) throw new Error('Serverfehler beim Laden.');
        adminDeviceList = await response.json();
        adminLog(`Geladene JSON-Liste:\n${JSON.stringify(adminDeviceList, null, 2)}`);
        renderDeviceTable();
        showToast(`Erfolgreich ${adminDeviceList.length} Gerät(e) geladen.`, 'success');
        adminLog(`Erfolgreich ${adminDeviceList.length} Gerät(e) geladen.`);
    } catch (e) {
        adminLog(`FEHLER: ${e.message}`);
        showToast(e.message, 'danger');
    }
}

function renderDeviceTable() {
    const tableBody = document.querySelector('#deviceListTable tbody');
    tableBody.innerHTML = '';
    adminDeviceList.forEach(device => {
        const tr = document.createElement('tr');
        tr.id = `row-${device.mac}`;
        tr.innerHTML = `
            <td><strong>${device.model || 'N/A'}</strong><br><small class="text-muted">${device.ssid}</small></td>
            <td>${device.generation || 'N/A'}</td>
            <td>${device.bemerkung || ''}</td>
            <td>${device.haName || ''}</td>
            <td class="small">${device.lastConfigured || 'Nie'}</td>
            <td>
                <button class="btn btn-sm btn-outline-primary" onclick="editDeviceRow('${device.mac}')">Bearbeiten</button>
                <button class="btn btn-sm btn-outline-danger ms-1" onclick="deleteDeviceRow('${device.mac}')">Löschen</button>
            </td>
        `;
        tableBody.appendChild(tr);
    });
}

function editDeviceRow(mac) {
    const device = adminDeviceList.find(d => d.mac === mac);
    if (!device) return;
    const row = document.getElementById(`row-${mac}`);
    if (!device.haName) device.haName = generateHaName(device);
    
    row.cells[2].innerHTML = `<input type="text" class="form-control form-control-sm" value="${device.bemerkung || ''}">`;
    row.cells[3].innerHTML = `<input type="text" class="form-control form-control-sm" value="${device.haName || ''}">`;
    row.cells[5].innerHTML = `
        <button class="btn btn-sm btn-success" onclick="saveDeviceRow('${device.mac}')">OK</button>
        <button class="btn btn-sm btn-secondary ms-1" onclick="renderDeviceTable()">X</button>
    `;
}

function saveDeviceRow(mac) {
    const device = adminDeviceList.find(d => d.mac === mac);
    if (!device) return;
    const row = document.getElementById(`row-${mac}`);
    device.bemerkung = row.cells[2].querySelector('input').value;
    device.haName = row.cells[3].querySelector('input').value;
    renderDeviceTable();
}

function deleteDeviceRow(mac) {
    if (confirm(`Soll das Gerät mit der MAC ${mac} wirklich gelöscht werden?`)) {
        adminDeviceList = adminDeviceList.filter(d => d.mac !== mac);
        renderDeviceTable();
        adminLog(`Gerät ${mac} entfernt. Speichern nicht vergessen!`);
    }
}

async function scanForNewDevices() {
    adminLog('Starte Suche nach neuen Geräten...');
    toggleSpinner('adminScanBtnSpinner', true);
    document.getElementById('adminScanBtn').disabled = true;

    try {
        const response = await fetch('api/admin/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ devices: adminDeviceList })
        });
        const data = await response.json();
        if(data.logs) data.logs.forEach(log => adminLog(log));
        if (!response.ok) throw new Error(data.details || 'Scan fehlgeschlagen');
        
        const newDevices = data.new_devices || [];
        if (newDevices.length > 0) {
            newDevices.forEach(dev => adminDeviceList.push(dev));
            renderDeviceTable();
            showToast(`${newDevices.length} neue(s) Gerät(e) gefunden!`, 'success');
        } else {
            showToast('Keine neuen Geräte gefunden.', 'info');
        }
    } catch (e) {
        adminLog(`FEHLER: ${e.message}`);
        showToast(e.message, 'danger');
    } finally {
        toggleSpinner('adminScanBtnSpinner', false);
        document.getElementById('adminScanBtn').disabled = false;
    }
}

async function saveChangesToServer() {
    if (!userPIN) {
        const newPin = prompt("Zum Verschlüsseln der Liste bitte eine PIN für den Benutzermodus festlegen (exakt 4 Ziffern):", "");
        if (!newPin || !/^\d{4}$/.test(newPin)) {
            showToast('Speichern abgebrochen. Ungültige PIN.', 'warning');
            return;
        }
        userPIN = newPin;
        document.getElementById('adminPinInput').value = userPIN;
    }
    adminLog(`Speichere Geräteliste mit PIN: ${userPIN}...`);
    try {
        const response = await fetch('api/admin/devices/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pin: userPIN, devices: adminDeviceList })
        });
        if (!response.ok) throw new Error('Speichern auf dem Server fehlgeschlagen.');
        showToast('Geräteliste erfolgreich gespeichert!', 'success');
        adminLog('Geräteliste erfolgreich gespeichert.');
    } catch(e) {
        adminLog(`FEHLER: ${e.message}`);
        showToast(e.message, 'danger');
    }
}

function generateHaName(device) {
    const bemerkung = device.bemerkung || 'Unbenannt';
    const model = (device.model || 'Shelly').replace(/\s/g, '');
    const macPart = device.mac.slice(-6);
    return `${bemerkung}-${model}-${macPart}`;
}
