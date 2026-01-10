FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Make migration script executable
RUN chmod +x run_migrations.py

EXPOSE 8000

# Use a startup script that runs migrations then starts the server
CMD ["sh", "-c", "python run_migrations.py && uvicorn main:app --host 0.0.0.0 --port 8000"]


