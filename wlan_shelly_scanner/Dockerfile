ARG BUILD_FROM
FROM $BUILD_FROM

LABEL Ihr Name <IhreEmail@example.com>

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

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

RUN rm -f /etc/nginx/http.d/default.conf
COPY nginx/ingress.conf /etc/nginx/http.d/ingress.conf

# Dieser Befehl kopiert jetzt auch unsere neue S6-Service-Definition
COPY rootfs/ /

COPY configure_shellies.py /configure_shellies.py
COPY api_server.py /api_server.py

# Mache die Skripte und die neue S6-run-Datei ausführbar
RUN chmod a+x \
    /configure_shellies.py \
    /api_server.py \
    /etc/services.d/app/run

# ENTFERNE das CMD-Kommando. S6 übernimmt die Kontrolle.
# CMD [ "/run.sh" ]