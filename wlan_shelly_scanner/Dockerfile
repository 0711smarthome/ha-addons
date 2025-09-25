ARG BUILD_FROM
FROM $BUILD_FROM

# Set shell for more robust scripts
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install necessary tools:
#   - iw: The main tool for scanning Wi--Fi networks
#   - jq: To read the configuration from options.json
#   - bash: A better shell
RUN apk update && apk add --no-cache \
    iw \
    jq \
    bash

# Copy the script into the container as a long-running service
COPY run.sh /etc/services.d/wifi-scanner/run
RUN chmod a+x /etc/services.d/wifi-scanner/run

# Set the S6 overlay init as the entrypoint (this is correct!)
CMD [ "/init" ]