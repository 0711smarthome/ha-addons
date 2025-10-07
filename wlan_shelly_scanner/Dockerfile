ARG BUILD_FROM
FROM $BUILD_FROM

LABEL Ihr Name <IhreEmail@example.com>

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Wir brauchen networkmanager NICHT. Die ha CLI ist der richtige Weg.
RUN apk update && apk add --no-cache \
    nginx \
    iw \
    jq \
    bash \
    nmap-ncat \
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