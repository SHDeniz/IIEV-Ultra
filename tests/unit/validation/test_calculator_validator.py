# tests/unit/validation/test_calculation_validator.py
import pytest
from decimal import Decimal
from src.services.validation.calculation_validator import validate_calculations
from src.schemas.validation_report import ValidationSeverity

# Wir nutzen die base_canonical_invoice Fixture aus conftest.py

def test_calculation_valid(base_canonical_invoice):
    """Testet eine mathematisch korrekte Rechnung."""
    errors = validate_calculations(base_canonical_invoice)
    assert len(errors) == 0

def test_calculation_line_total_mismatch(base_canonical_invoice):
    """Testet, ob die Summe der Positionen (100.00) mit LineExtensionAmount (90.00) abgeglichen wird."""
    # Pydantic V2: Verwende model_copy(update=...) für unveränderliche Updates
    invoice = base_canonical_invoice.model_copy(update={"line_extension_amount": Decimal("90.00")})
    
    errors = validate_calculations(invoice)
    assert len(errors) > 0
    assert any(e.code == "CALC_LINE_TOTAL_MISMATCH" for e in errors)

def test_calculation_tax_breakdown_mismatch(base_canonical_invoice):
    """Testet, ob die Steuerberechnung in der Aufschlüsselung korrekt ist (100 * 19% != 18)."""
    # Modifiziere den ersten TaxBreakdown Eintrag direkt
    base_canonical_invoice.tax_breakdown[0].tax_amount = Decimal("18.00")
    
    errors = validate_calculations(base_canonical_invoice)
    assert len(errors) > 0
    assert any(e.code == "CALC_TAX_BREAKDOWN_MISMATCH_19.00PCT" for e in errors)

def test_calculation_with_discounts(base_canonical_invoice):
    """Testet die Berechnung mit Rabatten auf Kopfebene."""
    # Basis: 100 Netto. Rabatt: 10. Neues Netto: 90. Steuer (19% von 90): 17.10. Brutto: 107.10.
    
    # Aktualisiere TaxBreakdown
    base_canonical_invoice.tax_breakdown[0].taxable_amount = Decimal("90.00")
    base_canonical_invoice.tax_breakdown[0].tax_amount = Decimal("17.10")

    invoice = base_canonical_invoice.model_copy(update={
        "allowance_total_amount": Decimal("10.00"),
        "tax_exclusive_amount": Decimal("90.00"),
        "tax_inclusive_amount": Decimal("107.10"),
        "payable_amount": Decimal("107.10")
    })

    errors = validate_calculations(invoice)
    assert len(errors) == 0