ARG BUILD_FROM
FROM $BUILD_FROM

LABEL Ihr Name <IhreEmail@example.com>

# Set shell for more robust scripts
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install necessary tools:
# - nginx: For serving the web UI
# - iw: The main tool for scanning Wi-Fi networks
# - jq: To read the configuration from options.json
# - bash: A better shell
RUN apk update && apk add --no-cache \
    nginx \
    iw \
    jq \
    bash && \
    rm -rf /var/cache/apk/*

# Kopiere die Web-Dateien in den Nginx-Ordner
# Wir erstellen das Verzeichnis und kopieren den Inhalt
COPY rootfs/ /

# Kopiere die Logik-Datei
COPY run.sh /run.sh
RUN chmod a+x /run.sh

# Startet das Skript als PID 1 des Containers
CMD [ "/run.sh" ]