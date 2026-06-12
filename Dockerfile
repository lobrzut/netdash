FROM python:3.12-slim

ARG NETDASH_BUILD_DATE=""
ENV NETDASH_BUILD_DATE=${NETDASH_BUILD_DATE}

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    iputils-ping iproute2 net-tools curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY run.py .

RUN mkdir -p /app/data

ENV NETDASH_PORT=18787
EXPOSE 18787

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD-SHELL curl -f "http://127.0.0.1:$${NETDASH_PORT:-18787}/api/health" || exit 1

CMD ["python", "run.py"]
