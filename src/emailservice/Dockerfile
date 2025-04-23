# ┌────────────────────────────────────────────────────────────────────────────┐
# │ 1) Builder: Debian‑slim, build deps + system OpenSSL for grpcio compile   │
# └────────────────────────────────────────────────────────────────────────────┘
FROM python:3.12-slim-bookworm AS builder

# install system OpenSSL and headers (for GRPC_PYTHON_BUILD_SYSTEM_OPENSSL=1)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      build-essential \
      openssl \
      libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /install

# copy in your full requirements (including grpcio)
COPY requirements.txt .

# tell grpcio to build against system OpenSSL
ENV GRPC_PYTHON_BUILD_SYSTEM_OPENSSL=1

# install everything under /install
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --prefix=/install -r requirements.txt

# ┌────────────────────────────────────────────────────────────────────────────┐
# │ 2) Runtime: Debian‑slim with just the runtime libs + your code            │
# └────────────────────────────────────────────────────────────────────────────┘
FROM python:3.12-slim-bookworm

# install runtime OpenSSL + C++ runtime
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      openssl \
      libstdc++6 \
      ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    ENABLE_PROFILER=1

WORKDIR /email_server

# pull in all the pip‑installed packages (built in builder)
COPY --from=builder /install /usr/local

# copy your application
COPY . .

EXPOSE 8080
ENTRYPOINT [ "python", "email_server.py" ]

