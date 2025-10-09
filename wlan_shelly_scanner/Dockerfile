ARG BUILD_FROM
FROM $BUILD_FROM

LABEL Ihr Name <IhreEmail@example.com>

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Füge "networkmanager-cli" zur Liste hinzu
RUN apk update && apk add --no-cache \
    python3 \
    py3-aiohttp \
    nginx \
    iw \
    jq \
    bash \
    curl \
    util-linux \
    networkmanager \
    networkmanager-cli

# Unser Test-Schritt bleibt zur finalen Kontrolle drin
RUN echo "Überprüfe, ob nmcli installiert wurde..." && \
    ls -l /usr/bin/nmcli && \
    echo "Überprüfe installierte Pakete..." && \
    apk info networkmanager networkmanager-cli

RUN rm -f /etc/nginx/http.d/default.conf
COPY nginx/ingress.conf /etc/nginx/http.d/ingress.conf
COPY rootfs/ /

COPY main.py /main.py
COPY run.sh /run.sh
RUN chmod a+x /main.py /run.sh

# Starte das Add-on über das run.sh Skript (das brauchen wir weiterhin!)
CMD [ "/run.sh" ]