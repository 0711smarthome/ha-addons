ARG BUILD_FROM
FROM $BUILD_FROM

LABEL Ihr Name <IhreEmail@example.com>

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apk update && apk add --no-cache \
    nginx \
    iw \
    jq \
    bash && \
    rm -rf /var/cache/apk/*

# Kopiere unsere Nginx-Konfiguration an den richtigen Ort im Container
COPY nginx/nginx.conf /etc/nginx/nginx.conf

# Kopiere die Web-Dateien
COPY rootfs/ /

# Kopiere die Logik-Datei
COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]