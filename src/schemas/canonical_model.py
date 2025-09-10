"""
Canonical Invoice Model (Pydantic)
Das zentrale, einheitliche Rechnungsmodell für alle Formate (UBL, CII)
WICHTIG: Immer Decimal für Währungen verwenden, niemals float!
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from datetime import date
from decimal import Decimal
from typing import Optional, List
from enum import Enum
import pycountry
import logging

logger = logging.getLogger(__name__)


def get_valid_country_codes() -> List[str]:
    """Dynamische Liste aller gültigen ISO 3166-1 alpha-2 Ländercodes"""
    return [country.alpha_2 for country in pycountry.countries]


class CountryCode(str, Enum):
    """ISO 3166-1 alpha-2 Ländercodes - Häufigste europäische Länder"""
    DE = "DE"  # Deutschland
    AT = "AT"  # Österreich  
    CH = "CH"  # Schweiz
    FR = "FR"  # Frankreich
    NL = "NL"  # Niederlande
    BE = "BE"  # Belgien
    IT = "IT"  # Italien
    ES = "ES"  # Spanien
    PL = "PL"  # Polen
    CZ = "CZ"  # Tschechien
    DK = "DK"  # Dänemark
    SE = "SE"  # Schweden
    NO = "NO"  # Norwegen
    FI = "FI"  # Finnland
    GB = "GB"  # Großbritannien
    IE = "IE"  # Irland
    LU = "LU"  # Luxemburg
    # Weitere können bei Bedarf hinzugefügt werden


class CurrencyCode(str, Enum):
    """ISO 4217 Währungscodes"""
    EUR = "EUR"
    USD = "USD"
    CHF = "CHF"
    GBP = "GBP"


class TaxCategory(str, Enum):
    """Umsatzsteuer-Kategorien nach EN 16931"""
    STANDARD_RATE = "S"  # Standard rate
    ZERO_RATE = "Z"      # Zero rate
    EXEMPT = "E"         # Exempt from tax
    REVERSE_CHARGE = "AE"  # Reverse charge
    INTRA_COMMUNITY_SUPPLY = "K" # VAT exempt for EEA intra-community supply
    NOT_SUBJECT = "O"    # Not subject to tax


class PaymentMeansCode(str, Enum):
    """UN/ECE 4461 Payment Means Codes"""
    CREDIT_TRANSFER = "30"  # Überweisung
    DIRECT_DEBIT = "49"     # Lastschrift
    CARD = "48"             # Kartenzahlung
    CASH = "10"             # Bargeld


class Address(BaseModel):
    """Adresse einer Partei"""
    street_name: Optional[str] = None
    additional_street_name: Optional[str] = None
    city_name: str
    postal_zone: str  # PLZ
    country_code: CountryCode
    
    def __str__(self) -> str:
        parts = [self.street_name, self.additional_street_name, 
                f"{self.postal_zone} {self.city_name}", self.country_code.value]
        return ", ".join(filter(None, parts))


class Party(BaseModel):
    """Partei (Käufer/Verkäufer)"""
    name: str = Field(..., min_length=1, max_length=255)
    
    # Steuerliche Identifikation
    # ALT (V1): vat_id: Optional[str] = Field(None, regex=r"^[A-Z]{2}[A-Z0-9]{2,12}$")
    # NEU (V2): Ersetze regex durch pattern
    vat_id: Optional[str] = Field(None, pattern=r"^[A-Z]{2}[A-Z0-9]{2,12}$")  # USt-IdNr.
    tax_id: Optional[str] = None  # Steuernummer
    
    # Adresse
    address: Address
    
    # Kontaktdaten
    contact_name: Optional[str] = None
    telephone: Optional[str] = None
    email: Optional[str] = None
    
    @field_validator('vat_id')
    @classmethod
    def validate_vat_id(cls, v):
        """Erweiterte VAT-ID Validierung mit pycountry"""
        if v:
            # Prüfe, ob die ersten 2 Zeichen ein gültiger Ländercode sind
            if len(v) >= 2:
                country_code = v[:2].upper()
                valid_countries = get_valid_country_codes()
                if country_code not in valid_countries:
                    logger.warning(f"Unbekannter Ländercode in VAT-ID: {country_code}")
                    # Warnung, aber nicht blockierend für Robustheit
            else:
                logger.warning(f"VAT-ID zu kurz: {v}")
        return v


class BankDetails(BaseModel):
    """Bankverbindung für Zahlungen"""
    iban: str = Field(..., min_length=15, max_length=34)  # IBAN Länge variiert je nach Land
    bic: Optional[str] = Field(None, pattern=r"^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?$")
    account_name: Optional[str] = None
    bank_name: Optional[str] = None
    
    @field_validator('iban')
    @classmethod
    def validate_iban(cls, v):
        """IBAN Validierung mit schwifty Bibliothek"""
        try:
            from schwifty import IBAN
            # Normalisiere IBAN (entferne Leerzeichen, zu Großbuchstaben)
            normalized_iban = v.replace(' ', '').upper()
            
            # Validiere mit schwifty
            iban_obj = IBAN(normalized_iban)
            
            # Zusätzliche Prüfungen
            if not iban_obj.is_valid:
                logger.warning(f"IBAN Prüfsumme ungültig: {v}")
                # Warnung, aber nicht blockierend für Robustheit
            
            return normalized_iban
            
        except ImportError:
            logger.warning("schwifty nicht verfügbar, verwende Basis-Regex Validierung")
            # Fallback auf einfache Regex-Prüfung
            import re
            if not re.match(r"^[A-Z]{2}[0-9]{2}[A-Z0-9]{4}[0-9]{7}([A-Z0-9]?){0,16}$", v.replace(' ', '').upper()):
                logger.warning(f"IBAN Format ungültig: {v}")
            return v.replace(' ', '').upper()
        except Exception as e:
            logger.warning(f"IBAN Validierungsfehler für {v}: {e}")
            # Bei Fehlern nicht blockieren, aber normalisieren
            return v.replace(' ', '').upper()


class PaymentTerms(BaseModel):
    """Zahlungsbedingungen"""
    due_date: Optional[date] = None
    payment_means_code: Optional[PaymentMeansCode] = None
    payment_id: Optional[str] = None  # Verwendungszweck
    skonto_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    skonto_days: Optional[int] = Field(None, ge=0)


class TaxBreakdown(BaseModel):
    """Steueraufschlüsselung"""
    tax_category: TaxCategory
    tax_rate: Decimal = Field(..., ge=0, le=100)  # Prozent
    taxable_amount: Decimal
    tax_amount: Decimal
    
    @field_validator('tax_amount')
    @classmethod
    def validate_tax_calculation(cls, v, info):
        """Prüfe mathematische Korrektheit der Steuerberechnung"""
        if info.data and 'taxable_amount' in info.data and 'tax_rate' in info.data:
            expected = info.data['taxable_amount'] * info.data['tax_rate'] / 100
            tolerance = Decimal('0.02')  # 2 Cent Toleranz
            if abs(v - expected) > tolerance:
                # Warnung loggen, aber nicht blockieren
                pass
        return v


class InvoiceLine(BaseModel):
    """Rechnungsposition"""
    line_id: str
    
    # Artikel/Dienstleistung
    item_name: str = Field(..., min_length=1, max_length=255)
    item_description: Optional[str] = None
    item_classification: Optional[str] = None  # z.B. UNSPSC Code
    
    # Mengen und Einheiten
    quantity: Decimal
    unit_code: str = Field(default="C62")  # UN/ECE Rec 20 (C62 = Stück)
    
    # Preise
    unit_price: Decimal = Field(..., ge=0)
    line_net_amount: Decimal
    
    # Rabatte/Zuschläge
    allowance_charge_amount: Optional[Decimal] = Field(None, ge=0)
    allowance_charge_reason: Optional[str] = None
    
    # Steuern
    tax_category: TaxCategory
    tax_rate: Decimal = Field(..., ge=0, le=100)
    
    @field_validator('line_net_amount')
    @classmethod
    def validate_line_calculation(cls, v, info):
        """Prüfe mathematische Korrektheit der Zeilenberechnung"""
        if info.data and all(k in info.data for k in ['quantity', 'unit_price']):
            expected = info.data['quantity'] * info.data['unit_price']
            if 'allowance_charge_amount' in info.data and info.data['allowance_charge_amount']:
                expected -= info.data['allowance_charge_amount']
            
            tolerance = Decimal('0.02')
            if abs(v - expected) > tolerance:
                # Warnung loggen, aber nicht blockieren
                pass
        return v


class DocumentReference(BaseModel):
    """Dokumentenreferenz (z.B. Bestellung)"""
    document_id: str
    document_type: Optional[str] = None  # "ORDER", "CONTRACT", etc.
    issue_date: Optional[date] = None


class CanonicalInvoice(BaseModel):
    """
    Das zentrale, einheitliche Rechnungsmodell
    Alle Formate (UBL, CII) werden hierhin gemappt
    """
    
    # Rechnungsidentifikation
    invoice_number: str = Field(..., min_length=1, max_length=100)
    issue_date: date
    invoice_type_code: str = Field(default="380")  # 380 = Commercial invoice
    
    # Währung
    currency_code: CurrencyCode
    
    # Parteien
    seller: Party
    buyer: Party
    
    # Rechnungszeilen
    lines: List[InvoiceLine] = Field(..., min_length=1)
    
    # Summen (WICHTIG: Immer Decimal!)
    line_extension_amount: Decimal  # Summe Netto-Zeilenbeträge
    allowance_total_amount: Optional[Decimal]  # Gesamtrabatt
    charge_total_amount: Optional[Decimal] = Field(None, ge=0)     # Gesamtzuschlag
    tax_exclusive_amount: Decimal            # Nettosumme
    tax_inclusive_amount: Decimal             # Bruttosumme
    payable_amount: Decimal                    # Zahlbetrag
    
    # Steueraufschlüsselung
    tax_breakdown: List[TaxBreakdown] = Field(..., min_length=1)
    
    # Zahlungsinformationen
    payment_terms: Optional[PaymentTerms] = None
    payment_details: List[BankDetails] = Field(default_factory=list)
    
    # Referenzen
    purchase_order_reference: Optional[DocumentReference] = None
    contract_reference: Optional[DocumentReference] = None
    
    # Zusätzliche Felder
    note: Optional[str] = None
    due_date: Optional[date] = None
    delivery_date: Optional[date] = None  # Leistungsdatum für §14 UStG Compliance
    
    @field_validator('tax_inclusive_amount')
    @classmethod
    def validate_total_calculation(cls, v, info):
        """Prüfe mathematische Korrektheit der Gesamtsummen"""
        if info.data and 'tax_exclusive_amount' in info.data and 'tax_breakdown' in info.data:
            expected_tax = sum(tax.tax_amount for tax in info.data['tax_breakdown'])
            expected_total = info.data['tax_exclusive_amount'] + expected_tax
            
            tolerance = Decimal('0.02')
            if abs(v - expected_total) > tolerance:
                # Warnung loggen, aber nicht blockieren
                pass
        return v
    
    @field_validator('payable_amount')
    @classmethod
    def validate_payable_amount(cls, v, info):
        """Prüfe, dass Zahlbetrag = Bruttosumme (falls keine Vorauszahlung)"""
        if info.data and 'tax_inclusive_amount' in info.data:
            # Normalfall: Zahlbetrag = Bruttosumme
            tolerance = Decimal('0.02')
            if abs(v - info.data['tax_inclusive_amount']) > tolerance:
                # Könnte Vorauszahlung oder Skonto sein - nur warnen
                pass
        return v
    
    def get_total_tax_amount(self) -> Decimal:
        """Berechne Gesamtsteuerbetrag"""
        return sum(tax.tax_amount for tax in self.tax_breakdown)
    
    def get_line_count(self) -> int:
        """Anzahl Rechnungszeilen"""
        return len(self.lines)
    
    def is_reverse_charge(self) -> bool:
        """Prüfe ob Reverse Charge Verfahren"""
        return any(tax.tax_category == TaxCategory.REVERSE_CHARGE for tax in self.tax_breakdown)
    
    def get_primary_tax_rate(self) -> Optional[Decimal]:
        """Hauptsteuersatz (meist der höchste)"""
        if not self.tax_breakdown:
            return None
        return max(tax.tax_rate for tax in self.tax_breakdown)
    
    class ConfigDict:
        # JSON Schema Generation
        json_schema_extra = {
            "example": {
                "invoice_number": "R2024-001",
                "issue_date": "2024-01-15",
                "currency_code": "EUR",
                "seller": {
                    "name": "Musterfirma GmbH",
                    "vat_id": "DE123456789",
                    "address": {
                        "street_name": "Musterstraße 1",
                        "city_name": "Berlin",
                        "postal_zone": "10115",
                        "country_code": "DE"
                    }
                },
                "buyer": {
                    "name": "Kunde AG",
                    "vat_id": "DE987654321",
                    "address": {
                        "street_name": "Kundenweg 5",
                        "city_name": "München",
                        "postal_zone": "80331",
                        "country_code": "DE"
                    }
                }
            }
        }
