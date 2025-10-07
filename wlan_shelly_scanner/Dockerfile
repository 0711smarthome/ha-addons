ARG BUILD_FROM
FROM $BUILD_FROM

LABEL Ihr Name <IhreEmail@example.com>

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Wir fügen die Python-Bibliothek für HTTP-Anfragen hinzu
RUN apk add --no-cache \
    python3 \
    py3-aiohttp \
    nginx \
    iw \
    jq \
    bash \
    nmap-ncat \
    curl \
    util-linux

# Restliche Konfiguration
RUN rm -f /etc/nginx/http.d/default.conf
COPY nginx/ingress.conf /etc/nginx/http.d/ingress.conf
COPY rootfs/ /
COPY run.sh /run.sh
COPY configure_shellies.py /configure_shellies.py
RUN chmod a+x /run.sh /configure_shellies.py

CMD [ "/run.sh" ]