FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libgbm1 \
    libgtk-3-0 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY sandbox/requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel \
    && python -m pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

ENV BROWSER_PATH=/usr/bin/chromium
