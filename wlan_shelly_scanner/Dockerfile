ARG BUILD_FROM
FROM $BUILD_FROM

# Set shell for more robust scripts
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install necessary tools:
#   - iw: The main tool for scanning Wi-Fi networks
#   - jq: To read the configuration from options.json
#   - bash: A better shell
RUN apk update && apk add --no-cache \
    iw \
    jq \
    bash

# Copy the script into the container
COPY run.sh /etc/cont-init.d/
RUN chmod a+x /etc/cont-init.d/run.sh

# Set the script as the entrypoint
CMD [ "/init" ]