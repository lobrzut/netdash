FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends arp-scan iproute2 iputils-ping \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /agent
COPY scripts/netdash-agent.py /agent/netdash-agent.py
RUN chmod +x /agent/netdash-agent.py

ENV NETDASH_URL=http://127.0.0.1:18787 \
    SCAN_CIDR=192.168.1.0/24 \
    INTERVAL=300 \
    MARK_MISSING_OFFLINE=true

ENTRYPOINT ["python3", "/agent/netdash-agent.py"]
