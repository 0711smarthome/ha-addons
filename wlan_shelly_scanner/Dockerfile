ARG BUILD_FROM
FROM $BUILD_FROM

LABEL Ihr Name <IhreEmail@example.com>

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Wir installieren NUR die benötigten Pakete für die Shell-Lösung.
RUN apk add --no-cache \
    nginx \
    iw \
    jq \
    bash \
    nmap-ncat \
    networkmanager \
    curl \
    util-linux

# Test, der den Build abbricht, falls nmcli fehlt.
RUN if ! command -v nmcli; then echo "!!! FATAL: nmcli wurde nicht installiert !!!"; exit 1; fi

# ENTFERNE die Standard-Nginx-Seite.
RUN rm -f /etc/nginx/http.d/default.conf

COPY nginx/ingress.conf /etc/nginx/http.d/ingress.conf
COPY rootfs/ /
COPY run.sh /run.sh
COPY configure_shellies.sh /configure_shellies.sh
RUN chmod a+x /run.sh /configure_shellies.sh

CMD [ "/run.sh" ]