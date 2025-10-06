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