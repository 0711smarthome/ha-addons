ARG BUILD_FROM
FROM $BUILD_FROM

LABEL Ihr Name <IhreEmail@example.com>

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Installiere Pakete
RUN apk add --no-cache \
    python3 \
    py3-aiohttp \
    nginx \
    iw \
    jq \
    bash \
    curl \
    util-linux \
    networkmanager

# === NEUER DEBUG-SCHRITT ===
# Überprüfe direkt nach der Installation, ob die Datei existiert.
# Wenn dieser Schritt fehlschlägt, bricht der ganze Build ab.
RUN echo "Überprüfe, ob nmcli installiert wurde..." && \
    ls -l /usr/bin/nmcli && \
    apk info networkmanager

RUN rm -f /etc/nginx/http.d/default.conf
COPY nginx/ingress.conf /etc/nginx/http.d/ingress.conf
COPY rootfs/ /

# Kopiere das Python-Skript UND das neue Start-Skript
COPY main.py /main.py
COPY run.sh /run.sh
RUN chmod a+x /main.py /run.sh

# Starte das Add-on über das neue run.sh Skript
CMD [ "/run.sh" ]