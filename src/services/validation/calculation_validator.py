# src/services/validation/calculation_validator.py
import logging
from decimal import Decimal
from typing import List

from ...schemas.canonical_model import CanonicalInvoice, TaxCategory
from ...schemas.validation_report import ValidationError, ValidationCategory, ValidationSeverity

logger = logging.getLogger(__name__)

# Definiere die maximal zulässige Toleranz für Rundungsfehler
TOLERANCE = Decimal("0.02")

def validate_calculations(invoice: CanonicalInvoice) -> List[ValidationError]:
    """
    Prüft die mathematische Konsistenz der Rechnungssummen und Steuern.
    """
    logger.info(f"Starte mathematische Validierung für Rechnung {invoice.invoice_number}...")
    errors = []

    # 1. Prüfung der Positionssummen
    calculated_line_total = sum(line.line_net_amount for line in invoice.lines)
    
    if abs(calculated_line_total - invoice.line_extension_amount) > TOLERANCE:
        errors.append(_create_calc_error(
            "CALC_LINE_TOTAL_MISMATCH",
            f"Summe der Positionen ({calculated_line_total}) stimmt nicht mit dem Gesamtnetto der Positionen (LineExtensionAmount: {invoice.line_extension_amount}) überein.",
            invoice.line_extension_amount, calculated_line_total
        ))

    # 2. Prüfung des Gesamtnetto (TaxExclusiveAmount)
    # Berechnung: LineExtensionAmount - AllowanceTotal + ChargeTotal
    calculated_tax_exclusive = (
        invoice.line_extension_amount - invoice.allowance_total_amount + invoice.charge_total_amount
    )
    
    if abs(calculated_tax_exclusive - invoice.tax_exclusive_amount) > TOLERANCE:
        errors.append(_create_calc_error(
            "CALC_TAX_EXCLUSIVE_MISMATCH",
            f"Gesamtnetto (TaxExclusiveAmount: {invoice.tax_exclusive_amount}) stimmt nicht mit der Berechnung (Netto - Rabatte + Zuschläge: {calculated_tax_exclusive}) überein.",
            invoice.tax_exclusive_amount, calculated_tax_exclusive
        ))

    # 3. Prüfung der Steueraufschlüsselung (TaxBreakdown)
    calculated_total_tax = Decimal("0.00")

    for breakdown in invoice.tax_breakdown:
        # 3a. Interne Konsistenz der Steuergruppe (Taxable * Rate = TaxAmount)
        # Nur prüfen, wenn Rate > 0 und nicht Reverse Charge.
        if breakdown.tax_category != TaxCategory.REVERSE_CHARGE and breakdown.tax_rate > 0:
            # Berechnung auf 2 Nachkommastellen runden
            expected_tax_amount = (breakdown.taxable_amount * breakdown.tax_rate / 100).quantize(Decimal("0.01"))
            
            if abs(expected_tax_amount - breakdown.tax_amount) > TOLERANCE:
                errors.append(_create_calc_error(
                    f"CALC_TAX_BREAKDOWN_MISMATCH_{breakdown.tax_rate}PCT",
                    f"Steuerbetrag für {breakdown.tax_rate}% ({breakdown.tax_amount}) stimmt nicht mit der Berechnung (Basis * Rate: {expected_tax_amount}) überein.",
                    breakdown.tax_amount, expected_tax_amount
                ))
        
        # Summiere Gesamtsteuer (Für Bruttoberechnung)
        calculated_total_tax += breakdown.tax_amount

    # 4. Prüfung des Gesamtbrutto (TaxInclusiveAmount)
    # Berechnung: TaxExclusiveAmount + TotalTax
    calculated_tax_inclusive = invoice.tax_exclusive_amount + calculated_total_tax
    
    if abs(calculated_tax_inclusive - invoice.tax_inclusive_amount) > TOLERANCE:
        errors.append(_create_calc_error(
            "CALC_TAX_INCLUSIVE_MISMATCH",
            f"Gesamtbrutto (TaxInclusiveAmount: {invoice.tax_inclusive_amount}) stimmt nicht mit der Berechnung (Netto + Steuern: {calculated_tax_inclusive}) überein.",
            invoice.tax_inclusive_amount, calculated_tax_inclusive
        ))

    # 5. Prüfung des Zahlbetrags (PayableAmount)
    # Annahme: PayableAmount = TaxInclusiveAmount (keine Vorauszahlungen berücksichtigt)
    if abs(invoice.tax_inclusive_amount - invoice.payable_amount) > TOLERANCE:
         errors.append(_create_calc_error(
            "CALC_PAYABLE_AMOUNT_MISMATCH",
            f"Zahlbetrag (PayableAmount: {invoice.payable_amount}) stimmt nicht mit dem Gesamtbrutto ({invoice.tax_inclusive_amount}) überein.",
            invoice.payable_amount, invoice.tax_inclusive_amount, severity=ValidationSeverity.WARNING
        ))

    if not errors:
        logger.info("✅ Mathematische Validierung erfolgreich.")
        
    return errors

def _create_calc_error(code: str, message: str, expected: Decimal, actual: Decimal, severity=ValidationSeverity.ERROR) -> ValidationError:
    """Hilfsfunktion zur Erstellung detaillierter Rechenfehler."""
    return ValidationError(
        category=ValidationCategory.CALCULATION,
        severity=severity,
        code=code,
        message=message,
        expected_value=str(expected),
        actual_value=str(actual),
        description=f"Diskrepanz: {abs(expected - actual)}. Toleranz: {TOLERANCE}."
    )