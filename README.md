WLAN Scanner Add-on für Home Assistant

Ein Home Assistant Add-on, das es ermöglicht, Shelly-Geräte im Access-Point-Modus automatisch zu erkennen und mit den Anmeldedaten des Heimnetzwerks zu konfigurieren. Dies ist besonders nützlich für die einfache Massenkonfiguration neuer Geräte.

Das Add-on verwendet den NetworkManager (nmcli), um sich temporär mit den WLAN-Access-Points der Shellies zu verbinden und über deren lokale API die neuen WLAN-Zugangsdaten zu übertragen.

🚀 Installation
Das Add-on ist über das Home Assistant Add-on Store als Drittanbieter-Repository verfügbar.

Gehen Sie in Home Assistant zu Einstellungen > Add-ons.

Klicken Sie auf den Button ADD-ON STORE.

Klicken Sie oben rechts auf die drei Punkte und wählen Sie Repositories.

Fügen Sie die URL Ihres Repositorys hinzu:

https://github.com/0711smarthome/ha-addons
Das Add-on "WLAN Scanner" sollte nun in der Liste der verfügbaren Add-ons erscheinen.

Klicken Sie auf das Add-on und dann auf INSTALLIEREN.

⚙️ Kompatibilität mit Shelly-Generationen
Achtung: Die Shelly-Geräte verwenden unterschiedliche APIs zur Konfiguration:

Shelly Generation	Beispiel-Geräte	Verwendete API	Unterstützt durch dieses Add-on
Gen1	Shelly 1, Shelly 2.5	HTTP CoAP/REST	Nein (Verwendet Gen2 RPC-Befehl)
Gen2/Gen3	Shelly Plus, Shelly Pro	RPC (JSON-RPC)	Ja (Ziel-API)