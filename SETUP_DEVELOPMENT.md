# IIEV-Ultra Entwicklungsumgebung Setup

## 1. Voraussetzungen

- Python 3.10+
- Poetry (Installation: https://python-poetry.org/docs/#installation)
- Git

## 2. Projekt Setup

```bash
# Repository klonen (falls noch nicht geschehen)
git clone <your-repo-url>
cd IIEV-Ultra

# Poetry virtuelle Umgebung erstellen und Dependencies installieren
poetry install --with dev

# Virtuelle Umgebung aktivieren
poetry shell
```

## 3. Umgebungsvariablen konfigurieren

```bash
# .env Datei aus Beispiel erstellen
copy env.example .env

# .env Datei bearbeiten und Ihre spezifischen Werte eintragen
```

Für E-Mail Ingestion zusätzlich hinzufügen:
```env
# E-Mail Ingestion
EMAIL_INGESTION_ENABLED=true
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_USERNAME=ihre-email@gmail.com
IMAP_PASSWORD=ihr-app-spezifisches-passwort
IMAP_FOLDER_INBOX=INBOX
IMAP_FOLDER_ARCHIVE=INBOX/Archive
IMAP_FOLDER_ERROR=INBOX/Error
```

## 4. Tests ausführen

```bash
# Alle Tests
poetry run pytest

# Nur Unit Tests
poetry run pytest tests/unit -v

# Nur Integration Tests  
poetry run pytest tests/integration -v

# Mit Coverage Report
poetry run pytest --cov=src tests/

# Spezifischen Test ausführen
poetry run pytest tests/unit/extraction/test_extractor.py::test_extractor_ubl -v
```

## 5. Anwendung starten

### Development Server
```bash
poetry run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### Celery Worker
```bash
poetry run celery -A src.tasks.worker worker --loglevel=info
```

### Celery Beat (für periodische Tasks wie E-Mail Monitoring)
```bash
poetry run celery -A src.tasks.worker beat --loglevel=info
```

## 6. Entwickler-Tools

### Code Formatierung
```bash
poetry run black src/ tests/
```

### Linting
```bash
poetry run flake8 src/ tests/
```

### Type Checking
```bash
poetry run mypy src/
```

## 7. Docker Development (Alternative)

Falls Sie Docker bevorzugen:

```bash
# Docker Image bauen
docker build -f docker/Dockerfile -t iiev-ultra .

# Container mit Tests ausführen
docker run --rm -v ${PWD}:/app iiev-ultra pytest tests/

# Development Container mit Volume Mount
docker run -it --rm -v ${PWD}:/app -p 8000:8000 iiev-ultra bash
```

## 8. Nützliche Poetry Befehle

```bash
# Neue Dependency hinzufügen
poetry add requests

# Development Dependency hinzufügen
poetry add --group dev pytest-cov

# Dependency entfernen
poetry remove requests

# Virtuelle Umgebung Info anzeigen
poetry env info

# Dependencies aktualisieren
poetry update

# Lock-File ohne Installation aktualisieren
poetry lock --no-update
```

## 9. IDE Konfiguration

### VS Code
1. Installieren Sie die Python Extension
2. Wählen Sie den Poetry Interpreter: `Ctrl+Shift+P` → "Python: Select Interpreter"
3. Wählen Sie den Pfad der Poetry venv (wird automatisch erkannt)

### PyCharm
1. File → Settings → Project → Python Interpreter
2. Add Interpreter → Poetry Environment
3. Wählen Sie das Projekt-Verzeichnis

## 10. Troubleshooting

### Poetry nicht gefunden
```bash
# Windows (PowerShell)
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -

# Linux/Mac
curl -sSL https://install.python-poetry.org | python3 -
```

### Virtuelle Umgebung zurücksetzen
```bash
poetry env remove python
poetry install --with dev
```

### Dependencies Konflikte
```bash
poetry lock --no-update
poetry install --with dev
```

### Tests schlagen fehl
1. Überprüfen Sie die .env Konfiguration
2. Stellen Sie sicher, dass alle Dependencies installiert sind:
   ```bash
   poetry install --with dev
   ```
3. Überprüfen Sie die Datenbankverbindung (für Integration Tests)

## 11. Produktions-Deployment

Für Produktion ohne Development Dependencies:
```bash
poetry install --only main
```

Oder mit Docker:
```bash
docker build -f docker/Dockerfile -t iiev-ultra:prod .
```
