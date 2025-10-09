ARG BUILD_FROM
FROM $BUILD_FROM

LABEL Ihr Name <IhreEmail@example.com>

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Wir brauchen kein nmap-ncat mehr
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

RUN rm -f /etc/nginx/http.d/default.conf
COPY nginx/ingress.conf /etc/nginx/http.d/ingress.conf
COPY rootfs/ /

# Nur noch eine Python-Datei kopieren
COPY main.py /main.py
RUN chmod a+x /main.py

# Starte das zentrale Python-Skript als Hauptprozess
CMD [ "python3", "/main.py" ]