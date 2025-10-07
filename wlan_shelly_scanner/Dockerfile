ARG BUILD_FROM
FROM $BUILD_FROM

LABEL Ihr Name <IhreEmail@example.com>

# Dieses Argument zwingt Docker, die RUN-Zeile neu auszuführen
ARG CACHE_BUSTER=none

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Wir löschen den apk-Cache und installieren dann alles in einem Schritt
# Das stellt sicher, dass alles frisch heruntergeladen wird.
RUN rm -rf /var/cache/apk/* && \
    apk update && apk add --no-cache \
    nginx \
    iw \
    jq \
    bash \
    nmap-ncat \
    networkmanager \
    curl \
    util-linux

# ENTFERNE die Standard-Nginx-Seite, um Konflikte zu vermeiden
RUN rm -f /etc/nginx/http.d/default.conf

COPY nginx/ingress.conf /etc/nginx/http.d/ingress.conf
COPY rootfs/ /
COPY run.sh /run.sh
COPY configure_shellies.sh /configure_shellies.sh
RUN chmod a+x /run.sh /configure_shellies.sh

CMD [ "/run.sh" ]