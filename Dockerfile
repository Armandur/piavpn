FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    openvpn \
    tinyproxy \
    iptables \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY scripts/ /scripts/
RUN chmod +x /scripts/*.sh

COPY tinyproxy.conf /etc/tinyproxy/tinyproxy.conf

COPY app/ /app/app/

EXPOSE 8000 8888

ENTRYPOINT ["/scripts/entrypoint.sh"]
