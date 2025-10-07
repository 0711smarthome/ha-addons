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

# Test, der den Build abbricht, falls nmcli absolut nirgends zu finden ist.
# Wir suchen im gesamten Dateisystem nach der Datei.
RUN if ! find / -name "nmcli" -print -quit | grep -q nmcli; then \
        echo "!!! FATAL: nmcli wurde nirgends im System gefunden !!!"; \
        exit 1; \
    else \
        echo "--- SUCCESS: nmcli wurde im Dateisystem gefunden. ---"; \
    fi

# ... Rest bleibt gleich ...
RUN rm -f /etc/nginx/http.d/default.conf
COPY nginx/ingress.conf /etc/nginx/http.d/ingress.conf
COPY rootfs/ /
COPY run.sh /run.sh
COPY configure_shellies.sh /configure_shellies.sh
RUN chmod a+x /run.sh /configure_shellies.sh

CMD [ "/run.sh" ]