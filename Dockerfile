FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first for better cache
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Download spaCy model in case it is not bundled
RUN python -m spacy download en_core_web_md

# Ensure entrypoint is executable
RUN chmod +x entrypoint.sh

EXPOSE 8501

ENTRYPOINT ["./entrypoint.sh"]