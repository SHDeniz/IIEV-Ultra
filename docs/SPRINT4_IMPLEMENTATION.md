# Sprint 4 & 5: ERP Integration - Implementierung

## Übersicht
Sprint 4 und 5 implementieren die Business-Validierung durch Integration mit dem Azure MSSQL ERP-System. Diese Dokumentation beschreibt die vollständige Implementierung des 3-Way-Match Prozesses.

## Status: ✅ VOLLSTÄNDIG IMPLEMENTIERT

Implementierungsdatum: September 2025

## Kernkomponenten

### 1. Adapter Pattern für ERP-Integration

#### Interface Definition (`src/services/erp/interface.py`)
```python
IERPAdapter (Abstract Base Class)
├── find_vendor_by_vat_id()      # Kreditor-Lookup
├── is_duplicate_invoice()        # Dublettenprüfung  
├── get_vendor_bank_details()     # Bankdatenabgleich
└── get_purchase_order_details()  # Bestellabgleich mit 3-Way-Match
```

#### Konkrete Implementierung (`src/services/erp/mssql_adapter.py`)
- **MSSQL_ERPAdapter**: Implementiert alle Interface-Methoden für Azure MSSQL
- **Sicherheit**: Verwendet parameterisierte Abfragen gegen SQL-Injection
- **Zugriff**: Read-Only Operationen auf ERP-Datenbank

### 2. Datenstrukturen

```python
ERPVendor
├── vendor_id: str        # Interne Kreditor-ID
├── vat_id: Optional[str] # USt-IdNr
└── is_active: bool       # Status

ERPPurchaseOrder
├── po_number: str                        # Bestellnummer
├── vendor_id: str                        # Kreditor-ID
├── total_net_amount: Decimal            # Netto-Gesamtbetrag
├── is_open_for_invoicing: bool          # Status
└── lines: Dict[str, ERPPurchaseOrderLine] # Positionen (Key: HAN/EAN/GTIN)

ERPPurchaseOrderLine  
├── han_ean_gtin: str        # Artikel-ID für Matching
├── quantity_ordered: Decimal # Bestellmenge
├── quantity_invoiced: Decimal # Bereits berechnete Menge
└── quantity_open: Decimal    # Offene Menge (computed)
```

## 3-Way-Match Implementierung

### Erweiterung des Canonical Models
Das `InvoiceLine` Model wurde um das kritische Feld erweitert:
```python
item_identifier: Optional[str] = None  # HAN/EAN/GTIN für 3-Way-Match
```

### Mapper-Erweiterungen

#### UBL Mapper (`src/services/mapping/ubl_mapper.py`)
Extrahiert Artikel-IDs in folgender Priorität:
1. `cac:StandardItemIdentification/cbc:ID` (GTIN/EAN)
2. `cac:SellersItemIdentification/cbc:ID` (HAN) 
3. `cac:BuyersItemIdentification/cbc:ID` (Fallback)

#### CII Mapper (`src/services/mapping/cii_mapper.py`)
Extrahiert Artikel-IDs in folgender Priorität:
1. `ram:GlobalID` (GTIN/EAN mit schemeID)
2. `ram:SellerAssignedID` (HAN)
3. `ram:BuyerAssignedID` (Fallback)

## Validierungsschritte

### 4.1 Kreditor-Lookup
- **Input**: USt-IdNr aus Rechnung
- **Prozess**: Suche in ERP-Kreditorenstamm
- **Output**: Interne KreditorID oder Fehler
- **Fehlerfall**: Status → MANUAL_REVIEW

### 4.2 Dublettenprüfung
- **Input**: KreditorID + Rechnungsnummer
- **Prozess**: Prüfung im Rechnungsjournal
- **Output**: Boolean (Dublette ja/nein)
- **Fehlerfall**: Status → INVALID (FATAL)

### 4.3 Bankdatenabgleich (Fraud Prevention)
- **Input**: IBAN aus Rechnung + KreditorID
- **Prozess**: Vergleich mit hinterlegten Bankverbindungen
- **Output**: Validierung erfolgreich/fehlgeschlagen
- **Fehlerfall**: Status → MANUAL_REVIEW (ERROR)

### 4.4 Bestellstatus-Prüfung
- **Input**: Bestellnummer + KreditorID
- **Prozess**: 
  - Existenzprüfung der Bestellung
  - Zugehörigkeitsprüfung zum Kreditor
  - Statusprüfung (offen/geschlossen)
- **Output**: ERPPurchaseOrder oder None
- **Fehlerfall**: Status → MANUAL_REVIEW (ERROR)

### 4.5 3-Way-Match (Betragsabgleich & Positionsabgleich)

#### Betragsabgleich (Kopfebene)
- **Toleranz**: ±0.02 EUR
- **Vergleich**: Rechnungsnetto vs. Bestellnetto
- **Fehlerfall**: WARNING (für Teilrechnungen) oder ERROR

#### Positionsabgleich (Detailebene)
```
Für jede Rechnungsposition:
1. Extrahiere item_identifier (HAN/EAN/GTIN)
2. Suche entsprechende Bestellposition
3. Prüfe Mengen:
   - Rechnungsmenge ≤ Offene Bestellmenge
4. Aggregiere Match-Ergebnisse
```

**Fehlerfälle**:
- Fehlende HAN/EAN/GTIN → WARNING
- Position nicht in Bestellung → ERROR  
- Menge überschritten → ERROR
- Keine Position zugeordnet → ERROR

## Datenbankarchitektur

### Zwei-Datenbank-Design
```python
# Metadaten-DB (PostgreSQL/Azure SQL)
with get_metadata_session() as db_meta:
    # InvoiceTransaction, ProcessingLog, etc.
    
# ERP-DB (Azure MSSQL - Read-Only)
with get_erp_session() as db_erp:
    # Kreditorenstamm, Bestellungen, Rechnungsjournal
```

### ERP-Tabellen (Annahmen)
```sql
-- Kreditorenstamm
dbo.KreditorenStamm (KreditorID, UStIdNr, Status)

-- Bankverbindungen  
dbo.KreditorenBanken (KreditorID, IBAN)

-- Rechnungsjournal
dbo.RechnungsJournal (KreditorID, ExterneRechnungsNr)

-- Bestellungen
dbo.Bestellungen (BestellNr, KreditorID, GesamtbetragNetto, Status)

-- Bestellpositionen
dbo.BestellPositionen (BestellNr, ArtikelHAN, MengeBestellt, MengeBerechnet)
```

## Konfiguration

### Umgebungsvariablen
```env
# ERP Datenbank (Read-Only Zugriff)
ERP_DATABASE_URL=mssql+pyodbc://readonly_user:password@server:1433/ERP_DB?driver=ODBC+Driver+17+for+SQL+Server
```

### Sicherheitsanforderungen
- ✅ Read-Only Datenbankbenutzer
- ✅ Parameterisierte SQL-Abfragen  
- ✅ Keine Schreiboperationen auf ERP
- ✅ Transaktionale Isolation zwischen Metadaten- und ERP-DB

## Fehlerbehandlung & Logging

### Fehler-Kategorien
1. **FATAL**: Dubletten → Sofortiger Abbruch
2. **ERROR**: Strukturfehler → Status INVALID
3. **WARNING**: Tolerierbare Abweichungen → Status MANUAL_REVIEW
4. **INFO**: Hinweise → Kein Statuswechsel

### Retry-Mechanismus
- Automatische Wiederholung bei transienten Fehlern
- Backoff-Strategie: 5 Versuche mit exponentieller Verzögerung
- Fehlertypen mit Retry: `DatabaseError`, `ConnectionError`, `IOError`

## Performance-Optimierungen

### Caching-Strategie
- Kreditorenstammdaten: Potentiell cachebar (selten Änderungen)
- Bestelldaten: Kein Cache (Echtzeit-Abfragen erforderlich)

### Batch-Processing
- Positionsabgleich nutzt Dictionary-Lookup O(1)
- Aggregation bei doppelten HANs in Bestellungen

## Testing

### Unit Tests erforderlich
```python
# test_mssql_adapter.py
- test_find_vendor_by_vat_id()
- test_duplicate_check()
- test_bank_validation()
- test_purchase_order_retrieval()
- test_3way_match_logic()
```

### Integrationstests
```python
# test_business_validator_integration.py
- test_full_erp_validation_flow()
- test_partial_invoice_handling()
- test_fraud_prevention()
```

### Testdaten-Anforderungen
1. Valide Kreditorenstammdaten
2. Offene Bestellungen mit HAN/EAN/GTIN
3. Testrechnungen mit korrekten Artikel-IDs
4. Edge Cases: Teilrechnungen, Storno, etc.

## Deployment Checklist

- [ ] ERP_DATABASE_URL in Produktionsumgebung konfiguriert
- [ ] Read-Only Datenbankbenutzer eingerichtet
- [ ] Firewall-Regeln für DB-Zugriff konfiguriert
- [ ] SSL/TLS für Datenbankverbindung aktiviert
- [ ] Connection Pooling optimiert
- [ ] Monitoring für DB-Performance eingerichtet
- [ ] Alerting für Fehlerquoten konfiguriert

## Nächste Schritte

### Sprint 5 - Erweiterte Features
- [ ] Kontierungsvorschläge basierend auf historischen Daten
- [ ] Machine Learning für Anomalieerkennung
- [ ] Dashboard für Business Validierungs-Statistiken
- [ ] Erweiterte Berichtsfunktionen

### Sprint 6 - Optimierungen
- [ ] Performance-Tuning für große Bestellungen
- [ ] Caching-Layer für Stammdaten
- [ ] Parallele Validierung von Batch-Uploads
- [ ] API für externe ERP-Systeme

## Changelog

### Version 1.0.0 (September 2025)
- Initial implementation of ERP integration
- Full 3-Way-Match functionality  
- Fraud prevention through bank validation
- Duplicate check implementation
- Purchase order validation with line-level matching

## Referenzen

- [EN 16931](https://www.din.de/de/wdc-beuth:din21:278973199) - Europäische Norm für elektronische Rechnungen
- [XRechnung Spezifikation](https://www.xoev.de/xrechnung-16828) 
- [Azure SQL Best Practices](https://docs.microsoft.com/en-us/azure/azure-sql/database/security-best-practice)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
