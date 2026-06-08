# Use the official Playwright Python image — handles Chromium and all
# Linux dependencies automatically. No manual apt-get required.
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

# Install Python dependencies first (better Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Chromium browser via Playwright
RUN playwright install chromium

# Copy application code
COPY . .

# Cloud Run expects the app to listen on 8080
ENV PORT=8080

# Run with gunicorn in production
# --timeout 300 gives Playwright up to 5 minutes per request
# --workers 1 keeps a single browser instance (scale via Cloud Run instances)
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--timeout", "300", "--workers", "1", "app:app"]
