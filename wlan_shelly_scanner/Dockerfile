ARG BUILD_FROM
FROM $BUILD_FROM

LABEL Ihr Name <IhreEmail@example.com>

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Wir installieren Python und die offizielle Home Assistant API Bibliothek
# Dies ist der einzige Befehl, der fehlschlagen kann.
RUN apk add --no-cache \
    python3 \
    py3-pip \
    nginx \
    iw \
    jq \
    bash \
    nmap-ncat \
    curl \
    util-linux && \
    pip install --break-system-packages "homeassistant-api==0.4.1" "asyncio==3.4.3"

# Restliche Konfiguration
RUN rm -f /etc/nginx/http.d/default.conf
COPY nginx/ingress.conf /etc/nginx/http.d/ingress.conf
COPY rootfs/ /
COPY run.sh /run.sh
COPY configure_shellies.py /configure_shellies.py
RUN chmod a+x /run.sh /configure_shellies.py

CMD [ "/run.sh" ]