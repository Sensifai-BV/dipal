FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive


RUN apt update && \
    apt install -y python3 \
    python3-pip


WORKDIR /app

COPY api_gateway/requirements.txt .

RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

COPY infrastructure/ ./infrastructure/
COPY shared/ ./shared/
COPY api_gateway/ ./api_gateway/
COPY pyproject.toml ./pyproject.toml
COPY benchmark ./benchmark/

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python3 -c "import os,urllib.request; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"API_GATEWAY_PORT\",8080)}/health/')"