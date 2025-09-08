# IIEV-Ultra Dockerfile
# Muss JRE (für KoSIT Validator) und MS ODBC Driver (für MSSQL) installieren

FROM python:3.10-slim

# Umgebungsvariablen
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DEBIAN_FRONTEND=noninteractive

# System-Updates und grundlegende Tools
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    wget \
    unzip \
    gcc \
    g++ \
    unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

# 1. Java Runtime Environment (für KoSIT Validator) installieren
RUN apt-get update && apt-get install -y default-jre \
    && rm -rf /var/lib/apt/lists/*

# 2. Microsoft ODBC Driver 17 für SQL Server installieren
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql17 \
    && rm -rf /var/lib/apt/lists/*

# Arbeitsverzeichnis erstellen
WORKDIR /app

# Assets Verzeichnis kopieren (XSD, Schematron, KoSIT JAR)
COPY ./assets /app/assets

# Python Dependencies installieren
COPY pyproject.toml poetry.lock* /app/
RUN pip install poetry \
    && poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi

# Anwendungscode kopieren
COPY ./src /app/src
COPY ./alembic.ini /app/
COPY ./alembic /app/alembic

# Nicht-root User erstellen für Sicherheit
RUN groupadd -r appuser && useradd -r -g appuser appuser
RUN chown -R appuser:appuser /app
USER appuser

# Port freigeben
EXPOSE 8000

# Health Check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Standardkommando
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
