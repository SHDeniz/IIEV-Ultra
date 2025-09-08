# IIEV-Ultra Assets

Dieses Verzeichnis enthält externe Ressourcen, die für die Rechnungsvalidierung benötigt werden.

## Erforderliche Assets

### 1. KoSIT Validator

**Datei**: `validator.jar`
**Quelle**: https://github.com/itplr-kosit/validator
**Version**: Aktuelle Stable Version
**Beschreibung**: Java-basierter Validator für XRechnung/ZUGFeRD

```bash
# Download Beispiel
wget https://github.com/itplr-kosit/validator/releases/latest/download/validator-1.5.0-standalone.jar -O validator.jar
```

### 2. KoSIT Szenarien-Konfiguration

**Datei**: `scenarios.xml`
**Quelle**: https://github.com/itplr-kosit/validator-configuration-xrechnung
**Beschreibung**: Konfiguration der Validierungsregeln und Szenarien

### 3. XSD Schemas

**Verzeichnis**: `xsd/`
**Struktur**:
```
xsd/
├── ubl/          # UBL 2.1 Schemas
│   ├── common/
│   └── maindoc/
└── cii/          # UN/CEFACT CII Schemas
    └── data/
```

**Quellen**:
- UBL: https://docs.oasis-open.org/ubl/UBL-2.1.html
- CII: https://unece.org/trade/uncefact/xml-schemas

### 4. Schematron Regeln

**Verzeichnis**: `schematron/`
**Inhalt**: EN 16931 Schematron-Regeln für XRechnung
**Quelle**: https://github.com/itplr-kosit/validator-configuration-xrechnung

## Setup-Anleitung

### Automatischer Download (empfohlen)

```bash
# Setup-Script ausführen (wird noch erstellt)
./scripts/setup_assets.sh
```

### Manueller Download

1. **KoSIT Validator**:
   ```bash
   cd assets/
   wget https://github.com/itplr-kosit/validator/releases/latest/download/validator-1.5.0-standalone.jar -O validator.jar
   ```

2. **XRechnung Konfiguration**:
   ```bash
   git clone https://github.com/itplr-kosit/validator-configuration-xrechnung.git temp_config
   cp temp_config/scenarios.xml .
   cp -r temp_config/resources/xrechnung/ ./
   rm -rf temp_config
   ```

3. **XSD Schemas**:
   ```bash
   mkdir -p xsd/ubl xsd/cii
   # UBL Schemas herunterladen...
   # CII Schemas herunterladen...
   ```

## Wartung

### Regelmäßige Updates

Die Assets sollten regelmäßig aktualisiert werden:

- **KoSIT Validator**: Alle 6 Monate oder bei kritischen Updates
- **XRechnung Regeln**: Bei neuen XRechnung-Versionen (ca. 2x/Jahr)
- **XSD Schemas**: Bei Standard-Updates

### Versionsverfolgung

Aktuelle Versionen werden in `versions.json` dokumentiert:

```json
{
  "kosit_validator": "1.5.0",
  "xrechnung_rules": "2.3.1",
  "ubl_version": "2.1",
  "cii_version": "D16B",
  "last_updated": "2024-12-19"
}
```

## Docker Integration

Die Assets werden beim Docker-Build in den Container kopiert:

```dockerfile
# Assets kopieren (siehe docker/Dockerfile)
COPY ./assets /app/assets
```

## Lizenzhinweise

- **KoSIT Validator**: Apache 2.0
- **XRechnung Regeln**: Apache 2.0
- **UBL/CII Schemas**: Respective Standards-Lizenzen

## Troubleshooting

### Validator startet nicht
- Java Runtime (JRE) installiert?
- JAR-Datei vollständig heruntergeladen?
- Berechtigungen korrekt?

### Validierung schlägt fehl
- Scenarios.xml korrekt?
- XSD Schemas vollständig?
- Schematron-Regeln aktuell?

### Performance-Probleme
- Java Heap Size erhöhen: `-Xmx2g`
- Validator-Timeout anpassen: `KOSIT_TIMEOUT_SECONDS`
