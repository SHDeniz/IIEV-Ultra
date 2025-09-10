# Sprint 3 Readiness Assessment: Core Validation Engine

## 🎯 Sprint 3 Ziel: Core Validation Implementation

**Hauptziel**: Implementierung der XSD-Validierung, KoSIT Schematron-Validierung und mathematischen Prüfungen für eine vollständige EN 16931-konforme Rechnungsvalidierung.

## ✅ Erfüllte Voraussetzungen

### 1. Robuste Basis-Architektur
- ✅ **Canonical Model**: Vollständig implementiert und getestet (93 Tests)
- ✅ **XML-Processing**: Sichere lxml-basierte Verarbeitung mit XXE-Schutz
- ✅ **Error Handling**: Strukturierte `ValidationReport` mit kategorisierten Fehlern
- ✅ **Storage Services**: Sync/Async Services für alle Anwendungsfälle

### 2. Validierte Datenflüsse
- ✅ **Format Detection**: CII/UBL-Erkennung funktional
- ✅ **XML Mapping**: UBL/CII → Canonical Model erfolgreich getestet
- ✅ **End-to-End Pipeline**: Upload → Detection → Extraction → Mapping validiert
- ✅ **Workflow Integration**: Celery Tasks mit robustem Error Handling

### 3. Testing-Framework
- ✅ **93 Tests**: Alle kritischen Komponenten abgedeckt
- ✅ **Corpus Integration**: Offizielle ZUGFeRD/XRechnung Test-Daten
- ✅ **Mock-Infrastruktur**: Realistische Test-Szenarien
- ✅ **CI/CD Ready**: JUnit XML Reports und strukturierte Logs

### 4. Technische Stabilität
- ✅ **Pydantic V2**: Migration abgeschlossen, keine Breaking Changes
- ✅ **PDF Processing**: Moderne pypdf-Library mit kritischen Bugfixes
- ✅ **Dependency Management**: Saubere, moderne Dependencies
- ✅ **Performance**: Effiziente Verarbeitung (2.2s für 93 Tests)

## 🚀 Sprint 3 Implementierungsplan

### Phase 1: XSD Validation Service (Woche 1)

**Ziele**:
- Strukturelle XML-Validierung gegen offizielle EN 16931 Schemas
- Integration in bestehende Validation Pipeline
- Detaillierte Fehlerberichterstattung

**Implementierung**:
```python
# src/services/validation/xsd_validator.py
class XSDValidator:
    def validate_xml(self, xml_bytes: bytes, format_type: InvoiceFormat) -> ValidationStep
    def _load_schema(self, format_type: InvoiceFormat) -> etree.XMLSchema
    def _parse_xsd_errors(self, errors: List) -> List[ValidationError]
```

**Assets benötigt**:
- UBL 2.1 XSD Schemas
- CII D16B XSD Schemas  
- EN 16931 Extension Schemas

### Phase 2: KoSIT Validator Integration (Woche 1-2)

**Ziele**:
- Schematron-basierte Geschäftsregeln-Validierung
- Java-Tool Integration über subprocess
- SVRL Report Parsing

**Implementierung**:
```python
# src/services/validation/kosit_validator.py
class KoSITValidator:
    def validate_invoice(self, xml_bytes: bytes, format_type: InvoiceFormat) -> ValidationStep
    def _run_kosit_jar(self, xml_file: str) -> subprocess.CompletedProcess
    def _parse_svrl_report(self, svrl_xml: bytes) -> List[ValidationError]
```

**Assets benötigt**:
- KoSIT Validator JAR (aktuellste Version)
- Scenarios.xml Konfiguration
- Schematron Rules (XRechnung/ZUGFeRD)

### Phase 3: Mathematical Validation (Woche 2)

**Ziele**:
- Summen- und Steuerberechnung validieren
- Toleranz-basierte Rundungsfehler-Behandlung
- Canonical Model Integration

**Implementierung**:
```python
# src/services/validation/calculation_validator.py
class CalculationValidator:
    def validate_calculations(self, invoice: CanonicalInvoice) -> ValidationStep
    def _validate_line_calculations(self, lines: List[InvoiceLine]) -> List[ValidationError]
    def _validate_tax_calculations(self, breakdown: List[TaxBreakdown]) -> List[ValidationError]
```

### Phase 4: Integration & Testing (Woche 2)

**Ziele**:
- Validation Pipeline in processor.py integrieren
- End-to-End Tests für alle Validation-Stufen
- Performance-Optimierung

## 📋 Benötigte Assets und Vorbereitung

### 1. KoSIT Assets Download
```bash
# Validator JAR
wget https://github.com/itplr-kosit/validator/releases/latest/download/validator-X.X.X-standalone.jar -O assets/validator.jar

# XRechnung Konfiguration
git clone https://github.com/itplr-kosit/validator-configuration-xrechnung.git
cp validator-configuration-xrechnung/scenarios.xml assets/
cp -r validator-configuration-xrechnung/resources/ assets/
```

### 2. XSD Schemas Organisation
```bash
mkdir -p assets/xsd/ubl/2.1/
mkdir -p assets/xsd/cii/D16B/
# Download und Organisation der offiziellen Schemas
```

### 3. Docker Image Vorbereitung
```dockerfile
# Stelle sicher, dass JRE verfügbar ist
RUN apt-get update && apt-get install -y default-jre

# Assets ins Image kopieren
COPY ./assets /app/assets
```

## 🔧 Architektur-Integration

### Validation Pipeline Extension

```python
# In src/tasks/processor.py - Schritt 3 Implementierung
def _run_validation_pipeline(self, xml_bytes: bytes, canonical_invoice: CanonicalInvoice, 
                           format_type: InvoiceFormat) -> ValidationReport:
    
    # 3.1 XSD Structure Validation
    xsd_step = self.xsd_validator.validate_xml(xml_bytes, format_type)
    validation_report.add_step(xsd_step)
    
    if not xsd_step.is_successful():
        return validation_report  # Stop bei strukturellen Fehlern
    
    # 3.2 KoSIT Semantic Validation  
    kosit_step = self.kosit_validator.validate_invoice(xml_bytes, format_type)
    validation_report.add_step(kosit_step)
    
    # 3.3 Mathematical Validation (auch bei KoSIT Warnings)
    calc_step = self.calculation_validator.validate_calculations(canonical_invoice)
    validation_report.add_step(calc_step)
    
    return validation_report
```

### Status-Logik Update

```python
# Finale Status-Bestimmung basierend auf Validation-Ergebnissen
if validation_report.has_fatal_errors():
    transaction.status = TransactionStatus.ERROR
elif validation_report.summary.total_errors > 0:
    transaction.status = TransactionStatus.INVALID  
elif validation_report.summary.total_warnings > 0:
    transaction.status = TransactionStatus.VALID  # Mit Warnungen
else:
    transaction.status = TransactionStatus.VALID  # Vollständig gültig
```

## 📊 Erfolgs-Metriken für Sprint 3

### Funktionale Ziele
- ✅ **XSD Validation**: 100% strukturelle Validierung gegen EN 16931
- ✅ **KoSIT Integration**: Schematron-Regeln erfolgreich angewendet
- ✅ **Mathematical Accuracy**: Korrekte Summen- und Steuervalidierung
- ✅ **Error Reporting**: Detaillierte, kategorisierte Fehlerberichte

### Performance-Ziele
- ⚡ **XSD Validation**: < 100ms pro Rechnung
- ⚡ **KoSIT Validation**: < 2s pro Rechnung
- ⚡ **Mathematical Validation**: < 50ms pro Rechnung
- ⚡ **End-to-End**: < 3s für komplette Validierung

### Testing-Ziele
- 🧪 **Test Coverage**: +30 neue Tests für Validation-Services
- 🧪 **Corpus Validation**: Alle offiziellen Test-Fälle bestehen
- 🧪 **Error Scenarios**: Negative Test-Fälle für alle Validator-Typen
- 🧪 **Integration Tests**: End-to-End Validation Pipeline

## 🎯 Definition of Done für Sprint 3

### Core Features
- [ ] XSD Validator implementiert und getestet
- [ ] KoSIT Validator integriert und funktional
- [ ] Mathematical Validator für alle Berechnungen
- [ ] Validation Pipeline in processor.py integriert
- [ ] Status-Logik für VALID/INVALID/ERROR implementiert

### Quality Assurance  
- [ ] Alle neuen Tests bestehen (Ziel: 120+ Tests)
- [ ] Offizielle Corpus-Tests erfolgreich
- [ ] Performance-Ziele erreicht
- [ ] Error Handling robust und getestet
- [ ] Dokumentation aktualisiert

### Infrastructure
- [ ] KoSIT Assets korrekt containerisiert
- [ ] XSD Schemas organisiert und verfügbar
- [ ] Docker Image funktional mit allen Dependencies
- [ ] CI/CD Pipeline erweitert für Validation-Tests

## 🚀 Ready to Start!

Mit der erfolgreichen Implementierung und Validierung der Basis-Komponenten ist IIEV-Ultra optimal für Sprint 3 vorbereitet. Die robuste Architektur, das umfassende Testing-Framework und die stabilen Datenflüsse bilden das ideale Fundament für die Core Validation Engine.

**Nächster Schritt**: KoSIT Assets beschaffen und mit der XSD Validator Implementierung beginnen! 🎯
