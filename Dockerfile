FROM python:3-alpine
ENTRYPOINT ["dumb-init", "--"]
CMD ["proxy"]
RUN apk add --no-cache -t .build build-base &&\
    apk add --no-cache socat &&\
    pip install --no-cache-dir dnspython dumb-init &&\
    apk del .build
ENV NAMESERVERS="208.67.222.222 8.8.8.8 208.67.220.220 8.8.4.4" \
    PORT="80 443" \
    PRE_RESOLVE=0 \
    MODE=tcp \
    VERBOSE=0
COPY proxy.py /usr/local/bin/proxy

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
