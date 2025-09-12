# Sprint 4 Vorbereitung: ERP Integration & Business Validierung

## 🎯 Ziel von Sprint 4-5

Das IIEV-Ultra System kann bereits **technisch und semantisch korrekte E-Rechnungen** identifizieren. 

**Sprint 4-5 Ziel**: Integration mit der **Azure MSSQL ERP-Datenbank**, um zu prüfen, ob die Rechnung auch im **spezifischen Geschäftskontext gültig** ist.

## 🏆 Was das System nach Sprint 4-5 zusätzlich kann:

10. ✅ **Dubletten erkennen** (Rechnungsnummer bereits im Journal?)
11. ✅ **Kreditoren validieren** (Absender im ERP-System bekannt?)
12. ✅ **Bankdaten abgleichen** (IBAN stimmt mit Stammdaten überein?)
13. ✅ **Bestellungen prüfen** (PO-Nummer gültig und offen?)
14. ✅ **Geschäftsregeln anwenden** (Kreditorspezifische Validierung)

## 🔧 Technische Implementierung

### 1. ERP Adapter Interface

```python
# src/services/erp/interface.py
from abc import ABC, abstractmethod
from typing import Optional

class IERPAdapter(ABC):
    """Interface für ERP-System Integration"""
    
    @abstractmethod
    def find_vendor_id(self, vat_id: str) -> Optional[str]:
        """Finde KreditorID anhand USt-IdNr."""
        pass
    
    @abstractmethod  
    def is_duplicate(self, vendor_id: str, invoice_number: str) -> bool:
        """Prüfe ob Rechnungsnummer bereits existiert"""
        pass
    
    @abstractmethod
    def validate_bank_details(self, vendor_id: str, iban: str) -> bool:
        """Prüfe IBAN gegen Kreditor-Stammdaten"""
        pass
    
    @abstractmethod
    def validate_po(self, po_number: str) -> Optional[dict]:
        """Validiere Bestellnummer und Status"""
        pass
```

### 2. MSSQL ERP Adapter

```python
# src/services/erp/mssql_adapter.py  
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Optional
import logging

class MSSQL_ERPAdapter(IERPAdapter):
    """MSSQL ERP-Datenbank Adapter"""
    
    def __init__(self, erp_session: Session):
        self.session = erp_session
        self.logger = logging.getLogger(__name__)
    
    def find_vendor_id(self, vat_id: str) -> Optional[str]:
        """Kreditor-Lookup anhand USt-IdNr."""
        query = text("""
            SELECT KreditorID FROM dbo.KreditorenStamm 
            WHERE UStIdNr = :vat_id AND Status = 'Aktiv'
        """)
        result = self.session.execute(query, {"vat_id": vat_id}).fetchone()
        return result[0] if result else None
    
    def is_duplicate(self, vendor_id: str, invoice_number: str) -> bool:
        """Dublettenprüfung im Rechnungsjournal"""
        query = text("""
            SELECT COUNT(*) FROM dbo.RechnungsJournal
            WHERE KreditorID = :vendor_id 
            AND ExterneRechnungsNr = :invoice_number
        """)
        count = self.session.execute(query, {
            "vendor_id": vendor_id, 
            "invoice_number": invoice_number
        }).scalar()
        return count > 0
    
    def validate_bank_details(self, vendor_id: str, iban: str) -> bool:
        """IBAN-Abgleich mit Kreditor-Stammdaten"""
        query = text("""
            SELECT COUNT(*) FROM dbo.KreditorenBankdaten
            WHERE KreditorID = :vendor_id AND IBAN = :iban
        """)
        count = self.session.execute(query, {
            "vendor_id": vendor_id,
            "iban": iban
        }).scalar()
        return count > 0
    
    def validate_po(self, po_number: str) -> Optional[dict]:
        """Bestellvalidierung"""
        query = text("""
            SELECT BestellNr, Status, Wert, Waehrung 
            FROM dbo.Bestellungen
            WHERE BestellNr = :po_number AND Status IN ('Offen', 'Teilgeliefert')
        """)
        result = self.session.execute(query, {"po_number": po_number}).fetchone()
        
        if result:
            return {
                "po_number": result[0],
                "status": result[1], 
                "value": result[2],
                "currency": result[3]
            }
        return None
```

### 3. Integration in Celery Workflow

```python
# src/tasks/processor.py - Erweiterung
def process_invoice_task(self, transaction_id: str):
    # ... bestehende Schritte 1-4 ...
    
    # SCHRITT 5: Business Validierung (ERP)
    logger.info(f"🏢 Schritt 5: ERP Business Validation für {transaction_id}")
    
    with get_erp_session() as erp_db:
        erp_adapter = MSSQL_ERPAdapter(erp_db)
        
        # Kreditor-Lookup
        vendor_id = erp_adapter.find_vendor_id(canonical_invoice.seller.vat_id)
        if not vendor_id:
            # Unbekannter Kreditor
            transaction.status = TransactionStatus.INVALID
            validation_report.add_error("Kreditor nicht im ERP-System gefunden")
            return
        
        # Dublettenprüfung
        if erp_adapter.is_duplicate(vendor_id, canonical_invoice.invoice_number):
            transaction.status = TransactionStatus.INVALID
            validation_report.add_error("Rechnung bereits im System vorhanden")
            return
        
        # IBAN-Validierung
        if canonical_invoice.payment_details:
            iban = canonical_invoice.payment_details[0].iban
            if not erp_adapter.validate_bank_details(vendor_id, iban):
                validation_report.add_warning("IBAN stimmt nicht mit Stammdaten überein")
        
        # PO-Validierung (optional)
        if canonical_invoice.purchase_order_reference:
            po_info = erp_adapter.validate_po(canonical_invoice.purchase_order_reference.document_id)
            if not po_info:
                validation_report.add_warning("Bestellnummer nicht gefunden oder bereits abgeschlossen")
        
        # Update Transaction mit ERP-Daten
        transaction.erp_vendor_id = vendor_id
        transaction.is_duplicate = False
        transaction.status = TransactionStatus.VALID
```

## 📋 **KRITISCH: ERP Schema Informationen benötigt**

Für die Implementierung benötigen wir **detaillierte Informationen** über das Schema der ERP-Datenbank:

### 1. Kreditorenstamm (Vendors)
```sql
-- Beispiel - ANPASSEN AN TATSÄCHLICHES SCHEMA
SELECT 
    KreditorID,      -- Interne ID (Primary Key)
    Name,            -- Kreditorname  
    UStIdNr,         -- USt-IdNr. (für Lookup)
    Status           -- Status (Aktiv/Inaktiv)
FROM dbo.KreditorenStamm
WHERE UStIdNr = 'DE123456789'
```

**Benötigte Informationen:**
- Tabellenname: `?`
- Spaltenname KreditorID: `?`
- Spaltenname USt-IdNr.: `?`  
- Spaltenname Status: `?`
- Gültige Status-Werte: `?`

### 2. Bankverbindungen
```sql
-- Beispiel - ANPASSEN
SELECT 
    KreditorID,      -- Foreign Key zu Kreditorenstamm
    IBAN,            -- IBAN
    BIC              -- BIC (optional)
FROM dbo.KreditorenBankdaten  
WHERE KreditorID = 'K12345'
```

**Benötigte Informationen:**
- Tabellenname: `?`
- Foreign Key Spalte: `?`
- IBAN Spalte: `?`

### 3. Rechnungsjournal (für Dublettenprüfung)
```sql
-- Beispiel - ANPASSEN
SELECT 
    KreditorID,           -- Foreign Key
    ExterneRechnungsNr,   -- Rechnungsnummer vom Kreditor
    Buchungsdatum         -- Buchungsdatum
FROM dbo.RechnungsJournal
WHERE KreditorID = 'K12345' AND ExterneRechnungsNr = 'R2024-001'
```

**Benötigte Informationen:**
- Tabellenname: `?`
- Spalte für Rechnungsnummer: `?`
- Spalte für KreditorID: `?`

### 4. Bestellungen (Optional - für PO-Matching)
```sql
-- Beispiel - ANPASSEN  
SELECT 
    BestellNr,       -- Bestellnummer
    Status,          -- Status (Offen/Teilgeliefert/Abgeschlossen)
    Wert,            -- Bestellwert
    Waehrung         -- Währung
FROM dbo.Bestellungen
WHERE BestellNr = 'PO2024-001' AND Status IN ('Offen', 'Teilgeliefert')
```

**Benötigte Informationen:**
- Tabellenname: `?`
- Spalte für Bestellnummer: `?`
- Spalte für Status: `?`
- Gültige Status-Werte: `?`

## 🧪 Testing Strategy für Sprint 4

### 1. ERP Mock-Daten erstellen
```python
# tests/fixtures/erp_test_data.py
MOCK_KREDITORENSTAMM = [
    {"KreditorID": "K001", "Name": "Testfirma GmbH", "UStIdNr": "DE123456789", "Status": "Aktiv"},
    {"KreditorID": "K002", "Name": "Beispiel AG", "UStIdNr": "DE987654321", "Status": "Aktiv"},
]

MOCK_BANKDATEN = [
    {"KreditorID": "K001", "IBAN": "DE89370400440532013000", "BIC": "COBADEFFXXX"},
]

MOCK_RECHNUNGSJOURNAL = [
    {"KreditorID": "K001", "ExterneRechnungsNr": "R2023-999", "Buchungsdatum": "2023-12-01"},
]
```

### 2. Integration Tests erweitern
```python
# tests/integration/test_erp_validation.py
def test_business_validation_happy_path():
    """Test: Bekannter Kreditor, keine Dublette, gültige IBAN"""
    
def test_business_validation_unknown_vendor():
    """Test: Unbekannter Kreditor → INVALID"""
    
def test_business_validation_duplicate_invoice():
    """Test: Dublette erkannt → INVALID"""
    
def test_business_validation_iban_mismatch():
    """Test: IBAN stimmt nicht überein → WARNING"""
```

## ⏰ Timeline Sprint 4

### Woche 1: Setup & Schema-Mapping
- [ ] ERP-Schema Informationen sammeln
- [ ] `mssql_adapter.py` Grundgerüst implementieren
- [ ] Mock-Daten für Tests erstellen

### Woche 2: Business Logic Implementation  
- [ ] Kreditor-Lookup implementieren
- [ ] Dublettenprüfung implementieren
- [ ] IBAN-Validierung implementieren
- [ ] PO-Matching implementieren (optional)

### Woche 3: Integration & Testing
- [ ] Integration in Celery Workflow
- [ ] Unit Tests für ERP Adapter
- [ ] Integration Tests für Business Validation
- [ ] End-to-End Tests mit Mock-ERP

## 🚦 Ready Criteria für Sprint 4 Start

**BLOCKER**: Wir benötigen die **ERP-Schema Informationen** vor Sprint 4 Start!

**Bereit wenn:**
- ✅ System ist produktionsreif (Sprint 0-3 abgeschlossen) 
- ✅ 103 Tests bestanden
- ❌ **ERP-Schema Details bereitgestellt** ← **KRITISCH**
- ❌ **ERP-Datenbankzugriff konfiguriert** ← **KRITISCH**

## 🎯 Erfolgs-Kriterien Sprint 4

**Das System kann nach Sprint 4:**
- ✅ Kreditoren anhand USt-IdNr. im ERP finden
- ✅ Dubletten zuverlässig erkennen  
- ✅ IBAN-Stammdaten abgleichen
- ✅ Bestellnummern validieren (optional)
- ✅ Business-Validierung in < 200ms durchführen
- ✅ Graceful Degradation bei ERP-Ausfällen

**Das System ist dann bereit für den produktiven Einsatz! 🚀**
