ARG BUILD_FROM
FROM $BUILD_FROM

LABEL Ihr Name <IhreEmail@example.com>

# Set shell for more robust scripts
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install necessary tools:
# - iw: The main tool for scanning Wi-Fi networks
# - jq: To read the configuration from options.json
# - bash: A better shell
RUN apk update && apk add --no-cache \
    iw \
    jq \
    bash && \
    rm -rf /var/cache/apk/*

# Kopieren Sie die Logik-Datei
COPY run.sh /run.sh
RUN chmod a+x /run.sh

# Startet das Skript als PID 1 des Containers (ersetzt den S6-Mechanismus)
CMD [ "/run.sh" ]
