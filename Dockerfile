FROM python:3-alpine
ENTRYPOINT ["dumb-init", "--"]
CMD ["proxy"]
HEALTHCHECK CMD ["healthcheck"]
RUN apk add --no-cache -t .build build-base curl-dev &&\
    apk add --no-cache socat &&\
    apk add --no-cache libcurl &&\
    pip install --no-cache-dir dnspython dumb-init pycurl &&\
    apk del .build
ENV NAMESERVERS="208.67.222.222 8.8.8.8 208.67.220.220 8.8.4.4" \
    PORT="80 443" \
    PRE_RESOLVE=0 \
    MODE=tcp \
    VERBOSE=0 \
    MAX_CONNECTIONS=100 \
    UDP_ANSWERS=1 \
    HTTP_HEALTHCHECK=0\
    HTTP_HEALTHCHECK_URL="http://\$TARGET/"\
    SMTP_HEALTHCHECK=0\
    SMTP_HEALTHCHECK_URL="smtp://\$TARGET/"\
    SMTP_HEALTHCHECK_COMMAND="HELP"
COPY proxy.py /usr/local/bin/proxy
COPY healthcheck.py /usr/local/bin/healthcheck

# Labels
ARG BUILD_DATE
ARG VCS_REF
ARG VERSION
LABEL org.label-schema.build-date="$BUILD_DATE" \
    org.label-schema.name="Docker Whitelist" \
    org.label-schema.description="Simple whitelist proxy" \
    org.label-schema.license=Apache-2.0 \
    org.label-schema.url="https://www.tecnativa.com" \
    org.label-schema.vcs-ref="$VCS_REF" \
    org.label-schema.vcs-url="https://github.com/Tecnativa/docker-whitelist" \
    org.label-schema.vendor="Tecnativa" \
    org.label-schema.version="$VERSION" \
    org.label-schema.schema-version="1.0"
