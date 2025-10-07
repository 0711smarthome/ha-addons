ARG BUILD_FROM
FROM $BUILD_FROM

LABEL Ihr Name <IhreEmail@example.com>

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Stellt sicher, dass alle unsere Werkzeuge installiert sind
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

COPY nginx/ingress.conf /etc/nginx/http.d/ingress.conf
COPY rootfs/ /
COPY run.sh /run.sh
COPY configure_shellies.sh /configure_shellies.sh
RUN chmod a+x /run.sh /configure_shellies.sh

CMD [ "/run.sh" ]