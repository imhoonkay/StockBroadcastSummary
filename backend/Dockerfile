FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    ffmpeg \
    nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir --upgrade yt-dlp

COPY . .

# Create storage directory for subtitles
RUN mkdir -p /app/storage/subtitles

EXPOSE 8099

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8099"]
