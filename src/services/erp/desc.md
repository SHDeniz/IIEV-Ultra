Absolut. Die Integration mit Ihrem ERP-System, die sogenannte "Business Validierung", ist der Schritt, der die Automatisierung erst wirklich wertvoll macht. Hier verbinden wir die technische Korrektheit der Rechnung mit Ihrem spezifischen Geschäftskontext.

Lassen Sie uns im Detail durchgehen, wie dieser Abgleich technisch und prozessual in Ihrem IIEV-Ultra System funktionieren wird.

### 1. Der Zeitpunkt im Workflow

Die ERP-Validierung (Sprint 4 & 5) ist der letzte Schritt im Verarbeitungsprozess. Wenn eine Rechnung diesen Punkt erreicht, hat sie bereits alle vorherigen Hürden erfolgreich genommen:

1.  Extraktion und Format-Erkennung (Sprint 1/2)
2.  Technische Validierung (XSD, Sprint 3)
3.  Semantische Validierung (KoSIT, Sprint 3)
4.  Mapping ins `CanonicalInvoice` Modell (Sprint 2)
5.  Mathematische Validierung (Calculation, Sprint 3)

**Input für diesen Schritt:** Das vollständig validierte und normalisierte `CanonicalInvoice` Objekt.

### 2. Die Architektur: Entkopplung durch das Adapter-Pattern

Um das System flexibel zu halten und nicht fest mit Ihrem aktuellen ERP zu verdrahten, verwenden wir das **Adapter-Pattern**.

*   **Das Interface (`IERPAdapter`):** In `src/services/erp/interface.py` definieren wir einen "Vertrag", der beschreibt, *was* wir vom ERP wissen wollen.
    *   Beispiele: `find_vendor_id(vat_id)`, `is_duplicate(vendor_id, invoice_number)`, `validate_bank_details(vendor_id, iban)`.
*   **Die Implementierung (`MSSQL_ERPAdapter`):** In `src/services/erp/mssql_adapter.py` implementieren wir die konkrete Logik, die weiß, *wie* diese Informationen aus Ihrer Azure MSSQL Datenbank abgerufen werden (Tabellennamen, Spalten, SQL-Abfragen).

Wenn Sie in Zukunft Ihr ERP wechseln, müssen Sie nur einen neuen Adapter schreiben, ohne die Kernlogik des IIEV-Systems zu ändern.

### 3. Die Konnektivität: Python (Docker) zu Azure MSSQL

Die Verbindung von einem Python-Dienst in einem Linux-Container zu einem Microsoft SQL Server ist technisch spezifisch konfiguriert:

1.  **SQLAlchemy:** Die Python-Bibliothek, die wir für Datenbankoperationen nutzen.
2.  **`pyodbc`:** Die Brücke zwischen SQLAlchemy und dem ODBC-Standard.
3.  **Microsoft ODBC Driver:** Der eigentliche Treiber, der bereits in Ihrem `Dockerfile` installiert ist und die Kommunikation mit Azure MSSQL ermöglicht.

#### Sicherheit (Kritisch)

*   **Read-Only Zugriff:** Der Datenbankbenutzer, den das IIEV-System verwendet, darf **ausschließlich Leserechte** haben. Das System wird niemals Daten im ERP verändern.
*   **SQL Injection Schutz:** Wir verwenden parameterisierte Abfragen (über SQLAlchemy). Dies verhindert, dass potenziell schädlicher Code, der in Rechnungsfeldern enthalten sein könnte, auf Ihrer Datenbank ausgeführt wird.

### 4. Die Validierungsschritte im Detail

Der Celery Worker (`processor.py`) wird den `MSSQL_ERPAdapter` nutzen, um die folgenden Prüfungen durchzuführen:

#### Schritt 4.1: Kreditor-Lookup (Vendor Identification)

*   **Ziel:** Identifizieren des Lieferanten in Ihrem ERP (Ermittlung der internen `KreditorID`).
*   **Ablauf:**
    1.  Der Adapter nimmt die USt-IdNr. (VAT ID) aus dem `CanonicalInvoice.seller` Objekt.
    2.  Er führt eine SQL-Abfrage gegen Ihre Kreditorenstammdaten aus.
        *   *Beispiel-SQL:* `SELECT KreditorID FROM dbo.KreditorenStamm WHERE UStIdNr = 'DE123456789';`
    3.  **Fallback:** Wenn keine USt-IdNr. vorhanden ist, kann die Steuernummer oder (mit Vorsicht) die IBAN als sekundärer Identifikator verwendet werden.
*   **Ergebnis:**
    *   **Erfolg:** Die interne `KreditorID` (z.B. `70001`) wird gefunden.
    *   **Fehlschlag:** Kreditor unbekannt. Status wird auf `MANUAL_REVIEW` gesetzt (Grund: "Kreditor unbekannt").

#### Schritt 4.2: Dublettenprüfung (Duplicate Check)

*   **Ziel:** Verhindern, dass eine Rechnung mehrfach verbucht oder bezahlt wird.
*   **Ablauf:**
    1.  Der Adapter nutzt die `KreditorID` (aus 4.1) und die `invoice_number` aus dem `CanonicalInvoice`.
    2.  Er fragt das Rechnungsjournal (Bewegungsdaten) des ERPs ab.
        *   *Beispiel-SQL:* `SELECT COUNT(*) FROM dbo.RechnungsJournal WHERE KreditorID = '70001' AND ExterneRechnungsNr = 'R-2025-001';`
*   **Ergebnis:**
    *   **Erfolg:** Anzahl ist 0. Die Rechnung ist neu.
    *   **Fehlschlag:** Anzahl ist > 0. Status wird auf `INVALID` gesetzt (Grund: "Dublette gefunden").

#### Schritt 4.3: Bankdaten-Validierung (Fraud Prevention)

*   **Ziel:** Schutz vor Betrug durch manipulierte Bankdaten (z.B. wenn ein Lieferantenkonto kompromittiert wurde).
*   **Ablauf:**
    1.  Der Adapter extrahiert die IBANs aus `CanonicalInvoice.payment_details`.
    2.  Er fragt die hinterlegten, validierten Bankverbindungen für die `KreditorID` im ERP ab.
        *   *Beispiel-SQL:* `SELECT IBAN FROM dbo.KreditorenBanken WHERE KreditorID = '70001';`
    3.  Er prüft, ob die IBAN der Rechnung in der Liste der hinterlegten IBANs vorhanden ist.
*   **Ergebnis:**
    *   **Erfolg:** IBAN stimmt überein.
    *   **Fehlschlag:** IBAN unbekannt oder abweichend. Status wird auf `MANUAL_REVIEW` gesetzt (Grund: "Unbekannte Bankverbindung" – Hohe Priorität!).

#### Schritt 4.4: Bestellbezugsprüfung (PO Check)

*   **Ziel:** Sicherstellen, dass die Rechnung sich auf eine gültige und offene Bestellung bezieht.
*   **Ablauf:**
    1.  Wenn im `CanonicalInvoice.purchase_order_reference` eine Bestellnummer vorhanden ist.
    2.  Der Adapter prüft die Existenz und den Status der Bestellung im ERP.
        *   *Beispiel-SQL:* `SELECT Status FROM dbo.Bestellungen WHERE BestellNr = 'PO-9000';`
*   **Ergebnis:**
    *   **Erfolg:** Bestellung existiert und ist offen für Rechnungsstellung.
    *   **Fehlschlag:** Bestellung nicht gefunden oder geschlossen. Status `MANUAL_REVIEW` (Grund: "Bestellbezug ungültig").

### 5. Ergebnis der ERP-Validierung

Am Ende dieser Schritte wird das `ValidationLevel` auf `BUSINESS` gesetzt. Das System trifft die finale Entscheidung über den Status der `InvoiceTransaction`:

1.  **Alle Prüfungen erfolgreich:** Wenn auch keine Warnungen aus vorherigen Schritten (z.B. KoSIT-Warnungen) vorliegen, wird der Status final auf `VALID` gesetzt. Die Rechnung ist nun bereit für die Kontierung und (Dunkel-)Buchung.
2.  **Mindestens eine Prüfung fehlgeschlagen:** Der Status wird entsprechend der definierten Logik auf `INVALID` oder `MANUAL_REVIEW` gesetzt. Der detaillierte Grund wird im `ValidationReport` protokolliert.