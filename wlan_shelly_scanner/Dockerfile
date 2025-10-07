ARG BUILD_FROM
FROM $BUILD_FROM

LABEL Ihr Name <IhreEmail@example.com>

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apk add --no-cache \
    python3 \
    py3-aiohttp \
    nginx \
    iw \
    jq \
    bash \
    nmap-ncat \
    curl \
    util-linux

RUN rm -f /etc/nginx/http.d/default.conf
COPY nginx/ingress.conf /etc/nginx/http.d/ingress.conf
COPY rootfs/ /
COPY run.sh /run.sh
COPY configure_shellies.py /configure_shellies.py
# --- FÜGE DIESE ZEILEN HINZU ---
COPY api_server.py /api_server.py
RUN chmod a+x /run.sh /configure_shellies.py /api_server.py
# -----------------------------

# --- ÄNDERE DIESE ZEILE (um die alte chmod zu ersetzen) ---
# RUN chmod a+x /run.sh /configure_shellies.py 
# wurde bereits oben ersetzt

CMD [ "/run.sh" ]