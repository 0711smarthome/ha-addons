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

# ENTFERNE die Standard-Nginx-Seite, um Konflikte zu vermeiden
RUN rm /etc/nginx/http.d/default.conf

# Kopiere unsere Ingress-Konfiguration in den Standard-Ordner für Server-Blöcke
COPY nginx/ingress.conf /etc/nginx/http.d/ingress.conf

# Kopiere die Web-Dateien
COPY rootfs/ /

# Kopiere die Logik-Datei
COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]