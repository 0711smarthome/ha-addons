ARG BUILD_FROM
FROM alpine:3.19

LABEL Ihr Name <IhreEmail@example.com>

SHELL ["/bin/sh", "-c"]

RUN apk update && apk add --no-cache \
    networkmanager \
    networkmanager-cli \
    python3 \
    py3-aiohttp \
    py3-zeroconf \
    nginx \
    jq \
    bash \
    curl \
    util-linux \
    dbus

RUN rm -f /etc/nginx/http.d/default.conf
COPY nginx/ingress.conf /etc/nginx/http.d/ingress.conf
COPY rootfs/ /

COPY main.py /main.py
COPY run.sh /run.sh
RUN chmod a+x /main.py /run.sh

CMD [ "/run.sh" ]
