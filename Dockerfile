FROM python:3.14.7-slim@sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6 AS builder

ENV POETRY_VERSION=2.4.1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

WORKDIR /build
RUN python -m pip install --no-cache-dir "poetry==${POETRY_VERSION}" && \
    python -m venv /opt/lease-lurker
ENV VIRTUAL_ENV=/opt/lease-lurker \
    PATH="/opt/lease-lurker/bin:${PATH}"
COPY pyproject.toml poetry.lock README.md LICENSE ./
COPY src ./src
RUN poetry install --only main --no-root && poetry build --format wheel && \
    pip install --no-cache-dir dist/*.whl && \
    pip uninstall --yes msgpack setuptools pip

FROM python:3.14.7-slim@sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6

ENV PATH="/opt/lease-lurker/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LEASELURKER_CONFIG=/etc/lease-lurker/config.yaml

RUN apt-get update && \
    apt-get upgrade --yes && \
    rm -rf /var/lib/apt/lists/* && \
    python -m pip uninstall --yes msgpack setuptools pip && \
    addgroup --system lease-lurker && \
    adduser --system --ingroup lease-lurker lease-lurker
COPY --from=builder /opt/lease-lurker /opt/lease-lurker
COPY --chown=lease-lurker:lease-lurker config.example.yaml /etc/lease-lurker/config.yaml

USER lease-lurker
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health/live', timeout=2)"]
ENTRYPOINT ["lease-lurker"]
