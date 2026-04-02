FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create persistent data directory for SQLite
RUN mkdir -p /data

# Expose the port (Railway injects $PORT at runtime)
EXPOSE 8000

# Use shell form so $PORT is expanded at runtime
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
