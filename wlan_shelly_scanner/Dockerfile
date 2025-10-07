ARG BUILD_FROM
FROM $BUILD_FROM

LABEL Ihr Name <IhreEmail@example.com>

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Tausche socat gegen nmap-ncat, das besser für simple Webserver geeignet ist
RUN apk update && apk add --no-cache \
    nginx \
    iw \
    jq \
    bash \
    nmap-ncat \
    networkmanager \
    curl \
    util-linux && \
    rm -rf /var/cache/apk/*

# ENTFERNE die Standard-Nginx-Seite, um Konflikte zu vermeiden
RUN rm /etc/nginx/http.d/default.conf

# Kopiere unsere Ingress-Konfiguration
COPY nginx/ingress.conf /etc/nginx/http.d/ingress.conf

# Kopiere die Web-Dateien
COPY rootfs/ /

# Kopiere die Logik-Dateien und mache sie ausführbar
COPY run.sh /run.sh
COPY configure_shellies.sh /configure_shellies.sh
RUN chmod a+x /run.sh /configure_shellies.sh

CMD [ "/run.sh" ]