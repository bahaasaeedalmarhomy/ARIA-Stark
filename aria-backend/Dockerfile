FROM mcr.microsoft.com/playwright:v1.50.0-jammy

# Install Python 3.11 — base Jammy ships Python 3.10; ADK requires >=3.11
RUN apt-get update \
    && apt-get install -y --no-install-recommends software-properties-common \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y --no-install-recommends python3.11 python3.11-venv python3-pip \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer cache optimization)
COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium browser
# Note: base image includes system deps but NOT the Python playwright browser binaries
RUN python3 -m playwright install chromium

# Copy application source
COPY . .

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

EXPOSE 8080

CMD ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
