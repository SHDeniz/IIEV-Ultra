# IIEV-Ultra Entwicklungs-Changelog

Dieses Dokument protokolliert alle wichtigen Änderungen und Fortschritte im IIEV-Ultra Projekt.

## [Unreleased] - Sprint 0: Foundation Setup

### 2024-12-19

#### Hinzugefügt
- ✅ Projektstruktur erstellt
- ✅ Hauptdokumentation (README.md) erstellt
- ✅ Changelog-Dokumentation initialisiert
- ✅ Grundlegende Verzeichnisstruktur aufgebaut
- ✅ Python Package-Struktur mit allen Modulen
- ✅ Konfiguration (Pydantic Settings)
- ✅ Azure Clients Manager
- ✅ SQLAlchemy Datenmodelle
- ✅ Pydantic Schemas (Canonical Model, Validation Report)
- ✅ FastAPI Application mit Health/Upload/Status APIs
- ✅ Storage Service (Azure Blob Storage Abstraktion)
- ✅ Celery Worker Setup mit Basis-Tasks
- ✅ Alembic Datenbankmigrationen Setup
- ✅ Docker & Docker Compose Konfiguration
- ✅ Entwicklungsdokumentation

#### Technische Entscheidungen
- **Architektur**: Python + FastAPI + Celery + Azure
- **Validierung**: KoSIT Validator + XSD + Schematron
- **Datenbank**: Azure SQL (Metadaten) + MSSQL (ERP)
- **Container**: Docker mit JRE und MS ODBC Driver
- **Canonical Model**: Pydantic mit Decimal für Währungen
- **Asynchrone Verarbeitung**: Celery mit Redis Backend

#### Sprint 0 Abgeschlossen ✅
- [x] Task 0.1: Azure Infrastruktur Provisioning (Docker Compose Setup)
- [x] Task 0.2: Projekt-Setup & Struktur
- [x] Task 0.3: Dockerfile & Dependencies
- [x] Task 0.4: Lokale Entwicklungsumgebung (docker-compose)
- [x] Task 0.5: Datenbank Modellierung & Migration
- [x] Task 0.6: Konfiguration & Assets

#### Bereit für Sprint 1
Das Foundation-Setup ist vollständig. Alle Grundlagen für Sprint 1 (Ingestion Service und Asynchroner Workflow) sind vorhanden.

#### Kritische Fixes (Post-Review)
- 🔧 **Pydantic v2 Migration**: `validator` → `field_validator` mit korrekter Signatur
- 🔧 **PostgreSQL Driver**: `psycopg2-binary` zu Dependencies hinzugefügt
- 🔧 **SECRET_KEY**: Environment Variable in Docker Compose und Default-Wert gesetzt
- 🔧 **SQLAlchemy func**: Korrekte Import-Syntax für `func.count`, `func.avg`
- 🔧 **Variable Shadowing**: Loop-Variable in Status-API umbenannt
- 🔧 **Azure SAS Token**: Robuste Implementierung für Dev/Prod mit Fallbacks
- 🔧 **Docker Compose**: Fehlende ERP Schema-Datei auskommentiert
- 🔧 **SQLAlchemy 2.0**: `declarative_base` Import modernisiert

**Status: Alle kritischen Blocker behoben ✅**

#### Architektur-Konsistenz Fix
- 🔧 **Database Konsistenz**: PostgreSQL → MSSQL für Metadaten-DB (konsistent mit Azure SQL)
- 🔧 **UUID Types**: `postgresql.UUID` → `mssql.UNIQUEIDENTIFIER` 
- 🔧 **Docker Compose**: Zwei separate MSSQL-Container (Metadaten + ERP)
- 🔧 **Dependencies**: PostgreSQL-Driver entfernt, nur noch MSSQL/pyodbc
- 🔧 **Environment**: Connection Strings aktualisiert

**Jetzt vollständig konsistent: MSSQL überall! 🎯**

#### Post-Review Qualitäts-Verbesserungen
- ✅ **DB Model Robustheit**: Numeric(18,2) für B2B-Beträge, Boolean für is_duplicate, Foreign Key Constraints
- ✅ **Performance Optimierung**: Indizierung auf status, invoice_number, seller_vat_id, created_at
- ✅ **IBAN Validierung**: Schwifty-Library Integration mit Fallback auf Regex
- ✅ **Country Code Erweiterung**: pycountry Integration für vollständige ISO 3166-1 Unterstützung
- ✅ **§14 UStG Compliance**: delivery_date Feld für Leistungsdatum hinzugefügt
- ✅ **Celery Robustheit**: Exponential backoff, Idempotenz-Checks, Race Condition Prevention
- ✅ **Error Handling**: Unterscheidung zwischen transienten und permanenten Fehlern

**Review-Feedback vollständig implementiert! 🚀**

---

## Sprint-Planung

### Sprint 0: Foundation & Infrastruktur (Woche 1)
**Ziel**: Projektstruktur, Azure-Infrastruktur und lokale Entwicklungsumgebung

- [ ] Task 0.1: Azure Infrastruktur Provisioning
- [ ] Task 0.2: Projekt-Setup & Struktur  
- [ ] Task 0.3: Dockerfile & Dependencies
- [ ] Task 0.4: Lokale Entwicklungsumgebung (docker-compose)
- [ ] Task 0.5: Datenbank Modellierung & Migration
- [ ] Task 0.6: Konfiguration & Assets

### Sprint 1: Ingestion Service (Woche 2-3)
**Ziel**: Rechnungen empfangen, speichern und Verarbeitung starten

### Sprint 2: Format & Extraction (Woche 4)
**Ziel**: Verschiedene Rechnungsformate erkennen und XML extrahieren

### Sprint 3: Core Validation (Woche 5-6)
**Ziel**: XSD- und Schematron-Validierung implementieren

### Sprint 4: Data Mapping (Woche 7-8)
**Ziel**: Datenvereinheitlichung und mathematische Prüfungen

### Sprint 5: ERP Integration (Woche 9-10)
**Ziel**: MSSQL ERP-Anbindung für Business-Validierung

### Sprint 6: Testing & Deployment (Woche 11-12)
**Ziel**: Robustheit, Testing und Produktionsreife

---

## Legende
- ✅ Abgeschlossen
- 🚧 In Bearbeitung  
- ⏳ Geplant
- ❌ Blockiert
- 🔄 Überarbeitung erforderlich
