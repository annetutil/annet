# Use docker/ as the build context.
FROM python:3.12-slim-bookworm AS sources
WORKDIR /build
ARG GNETCLI_VERSION=latest
COPY resolve_gnetcli.py fetch_sources.py ./
RUN python resolve_gnetcli.py sources.json --version "$GNETCLI_VERSION" \
    && python fetch_sources.py

FROM golang:1.25-bookworm AS go-build
COPY --from=sources /sources/gnetcli /src
WORKDIR /src
RUN CGO_ENABLED=0 go build -trimpath -o /out/gnetcli ./cmd/cli \
    && CGO_ENABLED=0 go build -trimpath -o /out/gnetcli_server ./cmd/gnetcli_server

FROM python:3.12-slim-bookworm
COPY requirements.in /tmp/requirements.in
# Empty means latest from PyPI; release CI supplies its published version.
ARG ANNET_VERSION
RUN if [ -n "$ANNET_VERSION" ]; then \
        pip install --no-cache-dir --upgrade -r /tmp/requirements.in "annet[netbox]==$ANNET_VERSION"; \
    else \
        pip install --no-cache-dir --upgrade -r /tmp/requirements.in; \
    fi \
    && pip check

RUN groupadd --gid 10001 annet && useradd --uid 10001 --gid 10001 --create-home annet \
    && mkdir -p /work && chown annet:annet /work
COPY --from=go-build /out/ /usr/local/bin/
COPY --from=sources /build/sources.json /usr/local/share/annet/versions.json
RUN python -c 'import json, importlib.metadata as m; from pathlib import Path; p = Path("/usr/local/share/annet/versions.json"); data = json.loads(p.read_text()); data["packages"] = {d.metadata["Name"]: d.version for d in m.distributions()}; p.write_text(json.dumps(data, indent=2) + "\n")'
ENV PYTHONUNBUFFERED=1 HOME=/home/annet ANN_CONTEXT_CONFIG_PATH=/work/context.yml
WORKDIR /work
USER 10001:10001
ENTRYPOINT ["annet"]
CMD ["--help"]
