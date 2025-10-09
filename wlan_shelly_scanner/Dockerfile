ARG BUILD_FROM
FROM $BUILD_FROM

LABEL Ihr Name <IhreEmail@example.com>

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apk update && apk add --no-cache \
    python3 \
    py3-aiohttp \
    nginx \
    iw \
    jq \
    bash \
    curl \
    util-linux \
    wpa_supplicant \
    dbus 

RUN rm -f /etc/nginx/http.d/default.conf
COPY nginx/ingress.conf /etc/nginx/http.d/ingress.conf
COPY rootfs/ /

COPY main.py /main.py
COPY run.sh /run.sh
RUN chmod a+x /main.py /run.sh

CMD [ "/run.sh" ]
