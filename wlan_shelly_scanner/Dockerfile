ARG BUILD_FROM
FROM $BUILD_FROM

LABEL Ihr Name <IhreEmail@example.com>

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Wir installieren Python und lassen pip die korrekte Version der Bibliothek finden.
# "asyncio" wird entfernt, da es Teil von Python3 ist.
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
    pip install --break-system-packages homeassistant-api

# Restliche Konfiguration bleibt unverändert
RUN rm -f /etc/nginx/http.d/default.conf

COPY nginx/ingress.conf /etc/nginx/http.d/ingress.conf
COPY rootfs/ /

# Kopiere die finalen Skripte
COPY run.sh /run.sh
COPY configure_shellies.py /configure_shellies.py
RUN chmod a+x /run.sh /configure_shellies.py

CMD [ "/run.sh" ]