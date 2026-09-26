# Build only the allowlisted context produced by docker/prepare.py.
FROM python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2 AS sources
WORKDIR /build
COPY sources.json fetch_sources.py ./
RUN python fetch_sources.py

FROM golang:1.25.14-bookworm@sha256:3b4a11519ad929d1e1d261a12cff056f0c85b735253d7d861346b9c6f8b36437 AS go-build
COPY --from=sources /sources/gnetcli /src
WORKDIR /src
RUN CGO_ENABLED=0 go build -trimpath -o /out/gnetcli ./cmd/cli \
    && CGO_ENABLED=0 go build -trimpath -o /out/gnetcli_server ./cmd/gnetcli_server

FROM sources AS wheels
COPY build.lock requirements.lock ./
RUN pip install --no-cache-dir --require-hashes -r build.lock
RUN pip download --only-binary=:all: --require-hashes -r requirements.lock -d /wheels
COPY annet /src/annet
# Optional package version override; defaults to sources.json.
ARG ANNET_VERSION
RUN VERSION="${ANNET_VERSION:-$(python -c 'import json; print(json.load(open("sources.json"))["annet_dev_version"])')}" \
    pip wheel --no-build-isolation --no-deps /src/annet -w /wheels
RUN VERSION="$(python -c 'import json; print(json.load(open("sources.json"))["gnetcli"]["version"])')" \
    pip wheel --no-build-isolation --no-deps /sources/gnetcli/grpc_sdk/python -w /wheels
RUN VERSION="$(python -c 'import json; print(json.load(open("sources.json"))["gnetcli_adapter"]["version"])')" \
    pip wheel --no-build-isolation --no-deps /sources/gnetcli_adapter -w /wheels

FROM python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2
COPY --from=wheels /wheels /tmp/wheels
RUN pip install --no-cache-dir --no-index --find-links=/tmp/wheels 'annet[netbox]' gnetcli_adapter gnetclisdk \
    && pip check && rm -rf /tmp/wheels \
    && groupadd --gid 10001 annet && useradd --uid 10001 --gid 10001 --create-home annet \
    && mkdir -p /work && chown annet:annet /work
COPY --from=go-build /out/ /usr/local/bin/
COPY versions.json /usr/local/share/annet/versions.json
ENV PYTHONUNBUFFERED=1 HOME=/home/annet ANN_CONTEXT_CONFIG_PATH=/work/context.yml
WORKDIR /work
USER 10001:10001
ENTRYPOINT ["annet"]
CMD ["--help"]
