FROM python:3.12-slim

# Install Node.js, Chromium, and Puppeteer dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    chromium \
    fonts-liberation \
    libnss3 libatk-bridge2.0-0 libx11-xcb1 libxcomposite1 libxdamage1 \
    libxrandr2 libgbm1 libasound2 libpangocairo-1.0-0 libgtk-3-0 \
    --no-install-recommends && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium

WORKDIR /app

# Install Python requirements
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy WhatsApp bridge code and install Node dependencies
COPY whatsapp-bridge ./whatsapp-bridge
RUN cd whatsapp-bridge && npm install --omit=dev

# Copy FastAPI backend code
COPY backend/app ./app

RUN mkdir -p logs

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
