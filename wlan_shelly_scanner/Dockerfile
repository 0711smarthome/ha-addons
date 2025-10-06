ARG BUILD_FROM
FROM $BUILD_FROM

# Set shell for more robust scripts
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install necessary tools:
#   - iw: For scanning Wi-Fi networks
#   - jq: To read configuration
#   - bash: A better shell
#   - python3 & pip: For running the Flask web server
RUN apk update && apk add --no-cache \
    iw \
    jq \
    bash \
    python3 \
    py3-pip

# Copy the web application into the container
COPY rootfs/ /

# Install Python dependencies
RUN pip3 install --no-cache-dir -r /app/requirements.txt

# Copy the run script and make it executable
COPY run.sh /
RUN chmod a+x /run.sh

# Set the script as the container's entrypoint
CMD [ "/run.sh" ]