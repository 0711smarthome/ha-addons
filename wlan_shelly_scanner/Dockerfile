ARG BUILD_FROM
FROM $BUILD_FROM

LABEL Ihr Name <IhreEmail@example.com>

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Wir installieren Python und die offizielle Home Assistant API-Bibliothek
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
    pip install homeassistant-api

# ... Rest des Dockerfiles bleibt gleich ...
RUN rm -f /etc/nginx/http.d/default.conf

COPY nginx/ingress.conf /etc/nginx/http.d/ingress.conf
COPY rootfs/ /

# Ersetze das alte Shell-Skript durch das neue Python-Skript
COPY run.sh /run.sh
COPY configure_shellies.py /configure_shellies.py
RUN chmod a+x /run.sh /configure_shellies.py

CMD [ "/run.sh" ]