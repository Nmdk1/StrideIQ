# Build from repository root:
#   docker build -f apps/api/Dockerfile .
# Bundles workout fluency registry for plan_framework variant resolution in production.
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies.
# WeasyPrint requires Pango + FreeType + font packages for PDF rendering.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    libfontconfig1 \
    libffi-dev \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY apps/api/requirements.txt .
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Application code
COPY apps/api/ .

# Variant registry (path walk in workout_variant_dispatch finds /app/_AI_CONTEXT_/...)
COPY _AI_CONTEXT_/KNOWLEDGE_BASE/workouts/variants/workout_registry.json \
    _AI_CONTEXT_/KNOWLEDGE_BASE/workouts/variants/workout_registry.json

# Make migration script executable
RUN chmod +x run_migrations.py

EXPOSE 8000

# Use a startup script that runs migrations then starts the server
CMD ["sh", "-c", "python run_migrations.py && uvicorn main:app --host 0.0.0.0 --port 8000"]


