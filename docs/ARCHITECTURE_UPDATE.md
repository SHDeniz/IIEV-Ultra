# IIEV-Ultra Architektur-Update: Sprint 1 & 2 Integration

## 🎯 Überblick der Implementierung

Nach der erfolgreichen Integration von Sprint 1 (Ingestion) und Sprint 2 (Format & Extraction) verfügt IIEV-Ultra über einen vollständigen End-to-End Workflow für die Rechnungsverarbeitung.

## 🏗️ Architektur-Diagramm (Aktualisiert)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           IIEV-Ultra Architecture v2.0                         │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Upload API    │    │  Email Monitor  │    │  Manual Upload  │
│   (FastAPI)     │    │   (Celery Beat) │    │   (Web UI)      │
│                 │    │                 │    │                 │
│ • File Upload   │    │ • IMAP/POP3     │    │ • Drag & Drop   │
│ • Validation    │    │ • Auto-Process  │    │ • Batch Upload  │
│ • Async Storage │    │ • Error Handling│    │ • Status Track  │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌─────────────▼─────────────┐
                    │      Celery Worker        │
                    │   (Sync Processing)       │
                    │                           │
                    │ ┌─────────────────────────┤
                    │ │  1. Format Detection    │
                    │ │     • PDF Analysis      │
                    │ │     • XML Recognition   │
                    │ │     • ZUGFeRD Extract   │
                    │ ├─────────────────────────┤
                    │ │  2. XML Processing      │
                    │ │     • CII Mapping       │
                    │ │     • UBL Mapping       │
                    │ │     • Canonical Model   │
                    │ ├─────────────────────────┤
                    │ │  3. Validation (TODO)   │
                    │ │     • XSD Schema        │
                    │ │     • KoSIT Schematron  │
                    │ │     • Business Rules    │
                    │ └─────────────────────────┤
                    └─────────────┬─────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        │                         │                         │
┌───────▼───────┐    ┌───────────▼────────────┐    ┌───────▼────────┐
│ Sync Storage  │    │   Metadata Database    │    │   ERP Database │
│   Service     │    │      (MSSQL)           │    │    (MSSQL)     │
│               │    │                        │    │                │
│ • Raw Files   │    │ • Transaction Status   │    │ • Vendor Data  │
│ • Processed   │    │ • Validation Reports   │    │ • PO Numbers   │
│ • Sync Ops    │    │ • Processing Logs      │    │ • Duplicates   │
└───────────────┘    └────────────────────────┘    └────────────────┘
```

## 🔧 Neue Komponenten (Sprint 1 & 2)

### 1. SyncStorageService (`storage_service_sync.py`)

**Problem gelöst**: Async/Sync Inkompatibilität zwischen FastAPI und Celery

```python
class SyncStorageService:
    """Synchroner Storage Service für Celery Tasks"""
    
    def download_blob_by_uri(self, uri: str) -> bytes
    def upload_processed_xml(self, transaction_id: str, xml_content: bytes, format_type: str) -> str
    def _get_blob_client_from_uri(self, uri: str) -> BlobClient
```

**Vorteile**:
- ✅ Native Synchrone Operationen für Celery
- ✅ Keine `asyncio.run()` Wrapper erforderlich
- ✅ Bessere Performance und Stabilität
- ✅ Separate Instanz vom FastAPI Service

### 2. Format Detection & Extraction

#### PDF Utilities (`pdf_util.py`)
```python
def extract_xml_from_pdf(pdf_bytes: bytes) -> Tuple[Optional[InvoiceFormat], Optional[bytes]]
```

**Features**:
- ✅ ZUGFeRD/Factur-X XML-Extraktion aus PDF/A-3
- ✅ Standardisierte Dateinamen-Erkennung
- ✅ Robuste PDF-Objektreferenz-Auflösung
- ✅ Format-spezifische Unterscheidung

#### XML Analysis (`xml_util.py`)
```python
def analyze_xml(xml_bytes: bytes) -> Tuple[Optional[InvoiceFormat], Optional[etree._Element]]
```

**Features**:
- ✅ Namespace-basierte Format-Erkennung
- ✅ EN 16931 Compliance-Checks
- ✅ XXE-Schutz durch sichere Parser-Konfiguration
- ✅ CII/UBL Unterscheidung

### 3. XPath Utilities (`xpath_util.py`)

**Robuste XML-Verarbeitung**:
```python
def xp_text(element, query, nsmap, default=None, mandatory=False) -> Optional[str]
def xp_decimal(element, query, nsmap, default=None, mandatory=False) -> Optional[Decimal]
class MappingError(ValueError): # Für Business-Logic Fehler
```

**Features**:
- ✅ Typsichere Decimal-Extraktion
- ✅ Mandatory/Optional Feld-Handling
- ✅ Namespace-aware XPath-Queries
- ✅ Spezifische Exception-Hierarchie

## 🔄 Workflow-Integration (processor.py)

### Neuer End-to-End Prozess

```python
@celery_app.task(bind=True, base=CallbackTask, name="process_invoice_task",
                 autoretry_for=(DatabaseError, ConnectionError, IOError))
def process_invoice_task(self, transaction_id: str) -> Dict[str, Any]:
```

#### Schritt 1: Format Detection & Extraction
1. **Raw Data Download** (Sync Storage)
2. **Format Analysis** (PDF vs XML)
3. **XML Extraction** (bei ZUGFeRD/Factur-X)
4. **Format Classification** (CII vs UBL)

#### Schritt 2: XML Mapping
1. **Canonical Transformation** (CII/UBL → Canonical Model)
2. **Data Validation** (EN 16931 Compliance)
3. **Transaction Update** (Key Data Extraction)

#### Workflow-Steuerung
- ✅ **Nicht-strukturierte Daten** → `MANUAL_REVIEW`
- ✅ **Mapping-Fehler** → `INVALID` (nicht retriable)
- ✅ **Transiente Fehler** → Celery Retry mit Exponential Backoff
- ✅ **Erfolgreiche Verarbeitung** → `VALID` (bereit für Sprint 3)

## 🎯 Error-Handling Strategie

### Fehler-Kategorien

| Fehlertyp | Exception | Celery Action | Transaction Status | Beschreibung |
|-----------|-----------|---------------|-------------------|---------------|
| **Transient** | `IOError`, `DatabaseError`, `ConnectionError` | Retry (5x) | `RECEIVED` | Netzwerk, Storage, DB-Timeouts |
| **Business** | `MappingError` | No Retry | `INVALID` | Ungültige Rechnungsdaten |
| **System** | `Exception` | No Retry | `ERROR` | Unerwartete Systemfehler |
| **Non-Structured** | - | No Retry | `MANUAL_REVIEW` | Keine XML-Daten gefunden |

### Retry-Konfiguration
```python
autoretry_for=(DatabaseError, ConnectionError, IOError)
retry_backoff=True  # Exponential: 60s, 120s, 240s, 480s, 960s
max_retries=5
```

## 📊 Performance-Optimierungen

### 1. Synchrone Storage-Operationen
- **Vor**: `await storage.download()` → Async overhead in Celery
- **Nach**: `sync_storage.download()` → Native synchrone Operationen

### 2. Effiziente XML-Verarbeitung
- **lxml Parser**: Hochperformante C-basierte XML-Verarbeitung
- **Namespace-Caching**: Einmalige Namespace-Map Erstellung
- **Streaming**: Große XML-Dateien ohne vollständiges Laden in Memory

### 3. Smart Workflow-Routing
- **Early Exit**: Nicht-strukturierte Daten sofort zu Manual Review
- **Format-Specific Processing**: CII vs UBL optimierte Pfade
- **Lazy Loading**: Canonical Model nur bei erfolgreicher Extraktion

## 🔒 Security-Verbesserungen

### 1. XML Security
```python
parser = etree.XMLParser(resolve_entities=False)  # XXE-Schutz
```

### 2. PDF Security
- Robuste Objektreferenz-Auflösung ohne Code-Execution
- Sichere Dateinamen-Validierung
- Memory-effiziente Stream-Verarbeitung

### 3. Input Validation
- Strikte Format-Validierung vor Verarbeitung
- Mandatory Field Checks mit `MappingError`
- Decimal-Parsing mit Exception-Handling

## 🚀 Nächste Schritte (Sprint 3)

### Bereit für Integration:
1. **XSD Validation Service** → Nutzt bestehende XML-Parser
2. **KoSIT Validator Integration** → Nutzt `sync_storage` für temporäre Dateien
3. **Calculation Validator** → Nutzt `CanonicalInvoice` Model
4. **Business Rules Engine** → Nutzt ERP-Adapter Pattern

### Architektur-Vorteile für Sprint 3:
- ✅ **Canonical Model** bereits vollständig implementiert
- ✅ **Error Handling** robust und erweiterbar
- ✅ **Storage Services** für alle Use Cases verfügbar
- ✅ **Validation Report** Structure kompatibel

Die Architektur ist optimal vorbereitet für die Validierungs-Pipeline! 🎯
