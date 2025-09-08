# IIEV-Ultra: Invoice Ingestion and Validation Engine

## Projektübersicht

IIEV-Ultra ist eine hochmoderne Rechnungsverarbeitungsengine für die automatische Validierung und Integration von elektronischen Rechnungen (XRechnung, ZUGFeRD, Factur-X) in Azure-basierte ERP-Systeme.

## Architektur

- **Backend**: Python, FastAPI, Celery
- **Cloud**: Microsoft Azure (Blob Storage, Service Bus, SQL)
- **Validation**: KoSIT Validator, XSD, Schematron
- **Database**: Azure SQL (Metadaten), MSSQL (ERP Integration)
- **Container**: Docker, Azure Container Apps

## Projektstruktur

```
iive-project/
├── assets/                     # Externe Ressourcen (XSD, Schematron, KoSIT JAR)
├── docker/
│   └── Dockerfile              # Container mit JRE und MS ODBC Treiber
├── src/
│   ├── api/                    # FastAPI Endpunkte
│   ├── core/                   # Konfiguration und Azure Clients
│   ├── db/                     # SQLAlchemy Modelle
│   ├── schemas/                # Pydantic Datenmodelle
│   ├── services/               # Business Logic Services
│   │   ├── erp/                # ERP Integration
│   │   ├── extraction/         # Format Erkennung
│   │   └── validation/         # Validierungslogik
│   ├── tasks/                  # Celery Tasks
│   └── main.py
├── tests/
├── docs/                       # Projektdokumentation
└── docker-compose.yml
```

## Entwicklungsplan

Das Projekt wird in 6 Sprints (12 Wochen) entwickelt:

1. **Sprint 0**: Foundation & Infrastruktur Setup
2. **Sprint 1**: Ingestion Service und Asynchroner Workflow  
3. **Sprint 2**: Format & Extraction Service
4. **Sprint 3**: Core Validation - Technisch & Semantisch
5. **Sprint 4**: Data Mapping, Calculation & Compliance
6. **Sprint 5**: ERP Connector & Business Validierung
7. **Sprint 6**: Testing, Error Handling und Deployment

## Aktuelle Phase

🚧 **Sprint 0: Foundation Setup** - Projektstruktur und Grundlagen werden erstellt.

Siehe [CHANGELOG.md](./CHANGELOG.md) für detaillierte Entwicklungsfortschritte.
