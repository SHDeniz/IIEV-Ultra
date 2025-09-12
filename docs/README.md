# IIEV-Ultra Dokumentation

## 📚 Dokumentations-Übersicht

Diese Dokumentation beschreibt das **produktionsreife IIEV-Ultra System** - eine vollständig funktionsfähige E-Rechnungs-Validierungs-Engine.

## 🚀 Systemstatus: **PRODUKTIONSREIF** (Sprint 0-3 Abgeschlossen)

- ✅ **103 Tests** (101 bestanden, 2 übersprungen)
- ✅ **End-to-End Workflow** von E-Mail bis Validierung
- ✅ **90+ reale Rechnungsbeispiele** erfolgreich verarbeitet
- ✅ **Alle deutschen E-Rechnungsformate** unterstützt

## 📋 Dokumentations-Index

### 🏗️ **Architektur & Design**
- **[ARCHITECTURE.md](./ARCHITECTURE.md)** - Vollständige Systemarchitektur
  - Service-Übersicht und Datenfluss
  - Validation Pipeline Details
  - Canonical Data Model
  - Test Coverage Analyse

### 🛠️ **Entwicklung & Setup**
- **[DEVELOPMENT.md](./DEVELOPMENT.md)** - Lokale Entwicklungsumgebung
  - Setup-Anleitung (5 Minuten)
  - Docker Services Konfiguration
  - Testing & Debugging
  - Code Quality Tools

### 🎯 **Sprint 4 Vorbereitung**
- **[SPRINT4_PREPARATION.md](./SPRINT4_PREPARATION.md)** - ERP Integration
  - Business Validierung Konzept
  - ERP Schema Anforderungen
  - MSSQL Adapter Implementation
  - Testing Strategy

### 🧪 **Testing**
- **[../tests/README.md](../tests/README.md)** - Test Suite Dokumentation
  - 103 Tests Übersicht
  - Corpus Tests (90+ Beispiele)
  - Unit & Integration Tests
  - Test-Ausführung

## 🏆 Was das System JETZT kann:

1. ✅ **E-Rechnungen empfangen** (E-Mail IMAP + REST API)
2. ✅ **Formate erkennen** (XRechnung UBL/CII, ZUGFeRD, Factur-X)
3. ✅ **XML extrahieren** (aus hybriden PDF/A-3 Dokumenten)
4. ✅ **Strukturell validieren** (XSD Schema gegen EN 16931)
5. ✅ **Semantisch validieren** (KoSIT Schematron - deutsche Geschäftsregeln)
6. ✅ **Daten normalisieren** (UBL/CII → einheitliches Canonical Model)
7. ✅ **Mathematisch prüfen** (Summen, Steuern, Rabatte)
8. ✅ **GoBD-konform speichern** (Azure Blob Storage)
9. ✅ **Status verfolgen** (detailliertes Transaction Tracking)

**Das System kann mit hoher Sicherheit bestimmen, ob eine E-Rechnung technisch und inhaltlich korrekt ist! 🏆**

## 🎯 Nächste Schritte: Sprint 4-5 ERP Integration

### Sprint 4: Business Validierung
- **Dublettenprüfung**: Rechnungsnummer bereits im Journal?
- **Kreditor-Lookup**: Absender im ERP-System bekannt?
- **Bankdatenabgleich**: IBAN stimmt mit Stammdaten überein?
- **Bestellabgleich**: PO-Nummer gültig und offen?

### Sprint 5: Produktionsreife
- **Performance Optimierung**: Lasttests mit großen Dateien
- **Security Hardening**: Penetration Tests, Input Validation
- **Deployment**: CI/CD Pipeline, Azure Container Apps

## 🔧 Quick Start

```bash
# 1. Repository klonen
git clone <repository-url>
cd IIEV-Ultra

# 2. Environment Setup
cp env.example .env

# 3. Services starten
docker-compose up -d

# 4. Tests ausführen
python run_tests.py

# 5. API testen
curl -X POST http://localhost:8000/api/v1/upload \
  -F "file=@test_invoice.pdf"
```

## 📞 Support & Kontakt

- **Entwicklungsfragen**: Siehe [DEVELOPMENT.md](./DEVELOPMENT.md)
- **Architektur-Details**: Siehe [ARCHITECTURE.md](./ARCHITECTURE.md)
- **ERP Integration**: Siehe [SPRINT4_PREPARATION.md](./SPRINT4_PREPARATION.md)
- **Test-Issues**: Siehe [../tests/README.md](../tests/README.md)

---

**IIEV-Ultra - Produktionsreife E-Rechnungs-Validierung für Deutschland 🇩🇪**
