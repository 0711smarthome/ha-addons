// script.js - v2.1.0 with Bootstrap & dynamic PIN

// === CONFIGURATION ===
const HARDCODED_ADMIN_PASSWORD = "admin";

// === GLOBAL STATE ===
let adminDeviceList = [];
let userDeviceList = [];
let userPIN = ""; // Die einzige PIN, die verwendet wird

// ====== UI HELPER FUNCTIONS ======

function showToast(message, type = 'info') {
    const container = document.querySelector('.toast-container');
    const toastEl = document.createElement('div');
    toastEl.className = `toast align-items-center text-white bg-${type} border-0`;
    toastEl.setAttribute('role', 'alert');
    toastEl.setAttribute('aria-live', 'assertive');
    toastEl.setAttribute('aria-atomic', 'true');
    
    toastEl.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
    `;
    container.appendChild(toastEl);
    
    const toast = new bootstrap.Toast(toastEl, { delay: 3000 });
    toast.show();
    toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
}

function toggleSpinner(spinnerId, show) {
    document.getElementById(spinnerId)?.classList.toggle('d-none', !show);
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
        adminLog('Admin-Modus entsperrt. Lade Geräteliste zum Bearbeiten.');
        // PIN-Eingabe im Admin-Modus ist nun Teil des Speicher-Vorgangs
    } else {
        showToast('Falsches Admin-Passwort!', 'danger');
    }
}

function showUserMode() {
    document.getElementById('adminLogin').classList.add('d-none');
    document.getElementById('adminPanel').classList.add('d-none');
    document.getElementById('userModeContainer').classList.remove('d-none');
    
    // Reset user mode to initial PIN step
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
    if (!userPIN) {
        showToast('Bitte PIN eingeben.', 'warning');
        return;
    }

    userLog('Lade und entschlüssle Geräteliste mit der angegebenen PIN...');
    try {
        const response = await fetch('api/admin/devices/load', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pin: userPIN })
        });

        if (response.status === 400) throw new Error('Entschlüsselung fehlgeschlagen. Falsche PIN?');
        if (!response.ok) throw new Error('Geräteliste konnte nicht vom Server geladen werden.');

        userDeviceList = await response.json();
        userLog(`Erfolgreich ${userDeviceList.length} Gerät(e) geladen.`);
        document.getElementById('userPinStep').classList.add('d-none');
        document.getElementById('userMainStep').classList.remove('d-none');
        showToast('Geräteliste erfolgreich geladen.', 'success');
    } catch (e) {
        userLog(`FEHLER: ${e.message}`);
        showToast(e.message, 'danger');
    }
}

async function scanForUserDevices() {
    userLog('Starte umfassenden Scan...');
    toggleSpinner('scanUserBtnSpinner', true);
    document.getElementById('scanUserBtn').disabled = true;

    try {
        // Starte beide Scans parallel
        const [apResponse, lanResponse] = await Promise.all([
            fetch('api/scan'),
            fetch('api/lan_scan')
        ]);

        if (!apResponse.ok) throw new Error('WLAN-Scan (AP) ist fehlgeschlagen.');
        if (!lanResponse.ok) throw new Error('Netzwerk-Scan (LAN) ist fehlgeschlagen.');

        const availableAPs = await apResponse.json();
        const onlineDevices = await lanResponse.json();
        
        userLog(`Scan (AP) beendet: ${availableAPs.length} Netzwerke gefunden.`);
        userLog(`Scan (LAN) beendet: ${onlineDevices.length} Online-Shellys gefunden.`);
        
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
    const listDiv = document.getElementById('userShellyList');
    const notFoundDiv = document.getElementById('notFoundDevices');
    const notFoundList = document.getElementById('notFoundList');
    listDiv.innerHTML = '';
    notFoundList.innerHTML = '';
    let anyFound = false;
    let anyNotFound = false;

    const foundSsids = new Map(availableAPs.map(net => [net.ssid, net.signal]));
    const onlineHostnames = new Set(onlineDevices.map(dev => dev.hostname.toLowerCase()));

    userDeviceList.forEach(device => {
        const isAlreadyOnline = onlineHostnames.has(`shelly${device.model.replace(/Shelly /g, '').toLowerCase()}-${device.mac.toLowerCase()}`);
        const apIsVisible = foundSsids.has(device.ssid);

        let statusBadge = '';
        let disabled = '';
        let checked = 'checked';

        if (isAlreadyOnline) {
            statusBadge = '<span class="badge bg-success float-end">Online im LAN</span>';
            disabled = 'disabled';
            checked = ''; // Online-Geräte nicht standardmäßig auswählen
            anyFound = true; // Zählt als "gefunden", damit Konfig-Button aktiv wird
        } else if (apIsVisible) {
            const signal = foundSsids.get(device.ssid);
            const signalClass = signal > 70 ? 'signal-good' : signal > 40 ? 'signal-medium' : 'signal-poor';
            statusBadge = `<span class="badge float-end ${signalClass}">AP Signal: ${signal}%</span>`;
            anyFound = true;
        } else {
            anyNotFound = true;
            notFoundList.innerHTML += `<li>${device.haName || device.model}</li>`;
            return; // Nächstes Gerät in der Schleife
        }
        
        const lastConfiguredText = device.lastConfigured ? `<small class="d-block text-muted">Zuletzt konfiguriert: ${device.lastConfigured}</small>` : '';

        listDiv.innerHTML += `
            <div class="list-group-item">
                <input class="form-check-input me-2" type="checkbox" value="${device.mac}" id="user_shelly_${device.mac}" name="user_selected_shelly" ${checked} ${disabled}>
                <label class="form-check-label" for="user_shelly_${device.mac}">
                    <strong>${device.haName || device.model}</strong> (${device.bemerkung || 'Keine Bemerkung'})
                </label>
                ${statusBadge}
                ${lastConfiguredText}
            </div>
        `;
    });
    
    document.getElementById('userDeviceListContainer').classList.remove('d-none');
    notFoundDiv.classList.toggle('d-none', !anyNotFound);
    document.getElementById('configureBtn').disabled = !anyFound;
    userLog('Geräteliste aktualisiert. Bereits im LAN gefundene Geräte sind deaktiviert.');
}

async function startUserConfiguration() {
    const userSsid = document.getElementById('userSsid').value;
    const userPassword = document.getElementById('userPassword').value;

    if (!userSsid || !userPassword) {
        showToast('WLAN-Zugangsdaten dürfen nicht leer sein.', 'warning');
        return;
    }

    const selectedMacs = Array.from(document.querySelectorAll('input[name="user_selected_shelly"]:checked')).map(cb => cb.value);
    const devicesToConfigure = userDeviceList.filter(dev => selectedMacs.includes(dev.mac));

    if (devicesToConfigure.length === 0) {
        showToast('Keine Geräte zur Konfiguration ausgewählt.', 'warning');
        return;
    }

    userLog(`Starte Konfiguration für ${devicesToConfigure.length} Gerät(e)...`);
    document.getElementById('configureBtn').disabled = true;

    try {
        const response = await fetch('api/configure', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ selectedDevices: devicesToConfigure, userSsid, userPassword })
        });
        if (!response.ok) throw new Error('Konfigurations-Task konnte nicht gestartet werden.');
        
        // Update timestamp for configured devices locally
        const now = new Date().toLocaleString('de-DE');
        userDeviceList.forEach(device => {
            if (selectedMacs.includes(device.mac)) {
                device.lastConfigured = now;
            }
        });

        // Save the updated list in the background
        await fetch('api/admin/devices/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pin: userPIN, devices: userDeviceList })
        });
        userLog("Timestamp für konfigurierte Geräte in der Liste gespeichert.");

    } catch (e) {
        userLog(`FEHLER: ${e.message}`);
        showToast(e.message, 'danger');
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

function renderDeviceTable() {
    const tableBody = document.querySelector('#deviceListTable tbody');
    tableBody.innerHTML = '';
    adminDeviceList.forEach(device => {
        const tr = document.createElement('tr');
        tr.id = `row-${device.mac}`;
        tr.innerHTML = `
            <td><strong>${device.model || 'N/A'}</strong><br><small class="text-body-secondary">${device.ssid}</small></td>
            <td>${device.generation || 'N/A'}</td>
            <td>${device.bemerkung || ''}</td>
            <td>${device.haName || ''}</td>
            <td class="small">${device.lastConfigured || 'Nie'}</td>
            <td>
                <button class="btn btn-link text-info p-0" onclick="editDeviceRow('${device.mac}')">Bearbeiten</button>
                <button class="btn btn-link text-danger p-0 ms-2" onclick="deleteDeviceRow('${device.mac}')">Löschen</button>
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
        const newPin = prompt("Zum Verschlüsseln der Liste bitte eine PIN für den Benutzermodus festlegen (4 Ziffern):", "");
        if (!newPin || !/^\d{4}$/.test(newPin)) {
            showToast('Speichern abgebrochen. Ungültige PIN.', 'warning');
            return;
        }
        userPIN = newPin;
    }

    adminLog('Speichere Geräteliste...');
    try {
        const response = await fetch('api/admin/devices/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pin: userPIN, devices: adminDeviceList })
        });
        if (!response.ok) throw new Error('Speichern auf dem Server fehlgeschlagen.');
        showToast('Geräteliste erfolgreich gespeichert!', 'success');
        adminLog(`Geräteliste erfolgreich gespeichert. Die PIN lautet: ${userPIN}`);
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