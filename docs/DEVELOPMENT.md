# IIEV-Ultra Entwicklungsdokumentation

## Setup Lokale Entwicklungsumgebung

### Voraussetzungen

- Python 3.10+
- Docker & Docker Compose
- Git

### 1. Repository klonen

```bash
git clone <repository-url>
cd IIEV-Ultra
```

### 2. Environment Setup

```bash
# Environment-Datei erstellen
cp env.example .env

# Python Virtual Environment erstellen
python -m venv venv
source venv/bin/activate  # Linux/Mac
# oder
venv\Scripts\activate     # Windows

# Dependencies installieren
pip install poetry
poetry install
```

### 3. Docker Services starten

```bash
# Alle Services starten (DB, Redis, Azurite, etc.)
docker-compose up -d

# Logs verfolgen
docker-compose logs -f
```

### 4. Datenbank Setup

```bash
# Datenbank-Migrationen ausführen
alembic upgrade head
```

### 5. Anwendung starten

```bash
# FastAPI Server starten
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Celery Worker starten (separates Terminal)
celery -A src.tasks.worker worker --loglevel=info

# Celery Beat starten (separates Terminal, optional)
celery -A src.tasks.worker beat --loglevel=info
```

### 6. Services testen

- **API Dokumentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **Celery Flower**: http://localhost:5555 (falls gestartet)

## Entwicklungs-Workflow

### Code-Qualität

```bash
# Code formatieren
black src/

# Linting
flake8 src/

# Type Checking
mypy src/

# Tests ausführen
pytest
```

### Datenbank-Änderungen

```bash
# Neue Migration erstellen
alembic revision --autogenerate -m "Beschreibung der Änderung"

# Migration anwenden
alembic upgrade head

# Migration rückgängig machen
alembic downgrade -1
```

### Docker Development

```bash
# Anwendung im Container bauen
docker build -f docker/Dockerfile -t iiev-ultra .

# Container starten
docker run -p 8000:8000 iiev-ultra

# Services neu starten
docker-compose restart

# Services komplett neu bauen
docker-compose up --build
```

## Testing

### Unit Tests

```bash
# Alle Tests
pytest

# Spezifische Tests
pytest tests/test_upload.py

# Mit Coverage
pytest --cov=src --cov-report=html
```

### Integration Tests

```bash
# Mit Docker-Services
pytest tests/integration/
```

### API Tests

```bash
# Manuell mit curl
curl -X POST http://localhost:8000/api/v1/upload \
  -F "file=@test_invoice.pdf"

# Mit httpie
http --form POST localhost:8000/api/v1/upload file@test_invoice.pdf
```

## Debugging

### Logs

```bash
# Application Logs
docker-compose logs app

# Worker Logs
docker-compose logs worker

# Alle Services
docker-compose logs
```

### Database Debugging

```bash
# Metadaten-DB Console (MSSQL)
docker-compose exec metadata-db /opt/mssql-tools/bin/sqlcmd -S localhost -U sa -P 'IIEVMeta123!'

# MSSQL Console
docker-compose exec erp-db /opt/mssql-tools/bin/sqlcmd -S localhost -U sa -P 'IIEVDev123!'
```

### Azure Storage (Azurite)

- **Storage Explorer**: Verwende Azure Storage Explorer mit Azurite Connection String
- **Blob Endpoint**: http://localhost:10000/devstoreaccount1

## Troubleshooting

### Häufige Probleme

1. **Port bereits in Verwendung**
   ```bash
   # Ports prüfen
   netstat -tulpn | grep :8000
   
   # Docker Services stoppen
   docker-compose down
   ```

2. **Datenbank-Verbindungsfehler**
   ```bash
   # Services neu starten
   docker-compose restart db
   
   # Logs prüfen
   docker-compose logs db
   ```

3. **Assets fehlen**
   ```bash
   # KoSIT Validator und XSD Schemas manuell herunterladen
   # Siehe assets/README.md für Details
   ```

4. **Permission Errors (Linux)**
   ```bash
   # Docker ohne sudo
   sudo usermod -aG docker $USER
   
   # Neu anmelden erforderlich
   ```

### Performance Tuning

- **Celery Worker**: Anzahl Worker anpassen basierend auf CPU-Cores
- **Database**: Connection Pool Size optimieren
- **Docker**: Memory Limits setzen

## Produktions-Deployment

Siehe separate Dokumentation:
- `docs/DEPLOYMENT.md` - Azure Deployment
- `docs/MONITORING.md` - Monitoring & Alerting
- `docs/SECURITY.md` - Sicherheitsrichtlinien
