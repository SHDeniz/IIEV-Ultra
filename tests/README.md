# IIEV-Ultra Test Suite

## Übersicht

Diese Test-Suite validiert die Kernlogik der IIEV-Ultra Anwendung, insbesondere:
- **Extraktion**: Format-Erkennung und XML-Extraktion aus verschiedenen Formaten
- **Mapping**: Transformation von XML-Daten in das kanonische Datenmodell
- **Workflow**: End-to-End Verarbeitung von Rechnungen
- **E-Mail Ingestion**: Automatische Verarbeitung von E-Mail-Anhängen

## Test-Struktur

```
tests/
├── conftest.py              # Gemeinsame Fixtures und Mock-Daten
├── unit/                    # Unit-Tests für isolierte Komponenten
│   ├── extraction/
│   │   └── test_extractor.py
│   └── mapping/
│       └── test_mapper.py
└── integration/             # Integrationstests
    └── tasks/
        └── test_processor.py
```

## Installation der Abhängigkeiten

```bash
pip install pytest pytest-mock imap-tools reportlab
```

Oder mit Poetry:
```bash
poetry install --with dev
```

## Tests ausführen

### Alle Tests
```bash
pytest
```

### Nur Unit-Tests
```bash
pytest tests/unit -v
```

### Nur Integrationstests
```bash
pytest tests/integration -v
```

### Mit Coverage Report
```bash
pytest --cov=src tests/
```

### Einzelnen Test ausführen
```bash
pytest tests/unit/extraction/test_extractor.py::test_extractor_ubl -v
```

## Mock-Daten

Die `conftest.py` enthält:
- **MINIMAL_UBL_XML**: Minimales aber valides UBL 2.1 Beispiel
- **MINIMAL_CII_XML**: Minimales aber valides CII (UN/CEFACT) Beispiel
- **Mock ZUGFeRD PDFs**: Mit ReportLab generierte PDFs mit eingebettetem XML
- **Mock DB Session**: Simulierte Datenbank-Interaktionen
- **Mock Storage Service**: Simulierter Azure Blob Storage

## E-Mail Ingestion Testing

Für die E-Mail Ingestion Tests:

1. Setzen Sie die Umgebungsvariablen in `.env`:
```env
EMAIL_INGESTION_ENABLED=true
IMAP_HOST=imap.gmail.com
IMAP_USERNAME=test@example.com
IMAP_PASSWORD=app-specific-password
```

2. Führen Sie den E-Mail Monitoring Task manuell aus:
```python
from src.tasks.processor import email_monitoring_task
result = email_monitoring_task()
print(result)
```

## Erwartete Test-Ergebnisse

### Phase 2: Extraktion Tests ✅
- `test_extractor_ubl`: UBL Format-Erkennung
- `test_extractor_cii`: CII Format-Erkennung  
- `test_extractor_zugferd`: ZUGFeRD PDF-Extraktion
- `test_extractor_simple_pdf`: Einfache PDF-Klassifizierung

### Phase 3: Mapping Tests ✅
- `test_map_ubl_success`: Erfolgreiche UBL-Transformation
- `test_map_ubl_missing_mandatory_field`: Fehlerbehandlung bei fehlenden Pflichtfeldern
- `test_map_cii_success`: Erfolgreiche CII-Transformation
- `test_map_cii_invalid_date_format`: Fehlerbehandlung bei ungültigen Datumsformaten

### Phase 4: Integration Tests ✅
- `test_process_happy_path_ubl`: Vollständiger Workflow für UBL
- `test_process_mapping_error`: Fehlerbehandlung im Workflow
- `test_process_unstructured_pdf`: Verarbeitung von unstrukturierten PDFs
- `test_process_idempotency`: Idempotenz-Check

## Bekannte Einschränkungen

- **KoSIT Validator**: Tests für Sprint 3 (Validierung) sind noch nicht implementiert
- **ERP Integration**: Tests für Sprint 4 (ERP-Abgleich) sind noch nicht implementiert
- **Performance Tests**: Lasttests für große Dateien fehlen noch

## Nächste Schritte

1. **Sprint 3**: KoSIT Validator Integration Tests
2. **Sprint 4**: ERP Mock-Daten und Abgleich-Tests
3. **Sprint 5**: Business Rules Engine Tests
4. **Performance**: Lasttests mit großen XML-Dateien
