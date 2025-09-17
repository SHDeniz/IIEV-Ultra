import logging
from typing import List, Optional
from decimal import Decimal

from ...schemas.canonical_model import CanonicalInvoice
from ...schemas.validation_report import ValidationError, ValidationCategory, ValidationSeverity
from ..erp.interface import IERPAdapter, ERPPurchaseOrder

logger = logging.getLogger(__name__)

# Toleranz für Betragsvergleiche (Bestellabgleich)
AMOUNT_TOLERANCE = Decimal("0.02")

def validate_business_rules(invoice: CanonicalInvoice, erp_adapter: IERPAdapter) -> List[ValidationError]:
    """
    Orchestriert die Business Validierung gegen das ERP System.
    """
    logger.info(f"Starte Business Validierung (ERP) für Rechnung {invoice.invoice_number}...")
    errors: List[ValidationError] = []
    
    # --------------------------------------------------------------------
    # 4.1 Kreditor-Lookup
    # --------------------------------------------------------------------
    vendor_vat_id = invoice.seller.vat_id
    if not vendor_vat_id:
        # Sollte bereits durch KoSIT abgefangen sein, aber als Sicherheitsnetz.
        errors.append(_create_business_error("ERP_VENDOR_ID_MISSING", "Keine USt-IdNr. vorhanden.", ValidationSeverity.ERROR))
        return errors

    erp_vendor = erp_adapter.find_vendor_by_vat_id(vendor_vat_id)
    
    if not erp_vendor:
        errors.append(_create_business_error("ERP_VENDOR_NOT_FOUND", f"Kreditor mit USt-IdNr. {vendor_vat_id} nicht im ERP gefunden.", ValidationSeverity.ERROR))
        return errors # Kann nicht fortfahren

    if not erp_vendor.is_active:
        errors.append(_create_business_error("ERP_VENDOR_INACTIVE", f"Kreditor {erp_vendor.vendor_id} ist inaktiv.", ValidationSeverity.WARNING))

    vendor_id = erp_vendor.vendor_id

    # --------------------------------------------------------------------
    # 4.2 Dublettenprüfung
    # --------------------------------------------------------------------
    if erp_adapter.is_duplicate_invoice(vendor_id, invoice.invoice_number):
        errors.append(_create_business_error("ERP_DUPLICATE_INVOICE", f"Rechnung {invoice.invoice_number} existiert bereits.", ValidationSeverity.FATAL))
        return errors # Stopp bei Dublette

    # --------------------------------------------------------------------
    # 4.3 Bankdaten-Validierung (Fraud Prevention)
    # --------------------------------------------------------------------
    if invoice.payment_details:
        erp_bank_details = erp_adapter.get_vendor_bank_details(vendor_id)
        validated_ibans = {details.iban for details in erp_bank_details}
        
        for payment in invoice.payment_details:
            if payment.iban not in validated_ibans:
                errors.append(_create_business_error(
                    "ERP_BANK_DETAILS_MISMATCH",
                    f"IBAN {payment.iban} ist nicht in den Stammdaten hinterlegt.",
                    ValidationSeverity.ERROR # Erfordert manuelle Prüfung
                ))

    # --------------------------------------------------------------------
    # 4.4 & 4.5 Bestellabgleich
    # --------------------------------------------------------------------
    if invoice.purchase_order_reference:
        po_number = invoice.purchase_order_reference.document_id
        erp_po = erp_adapter.get_purchase_order_details(po_number, vendor_id)
        
        if not erp_po:
            errors.append(_create_business_error(
                "ERP_PO_NOT_FOUND_OR_INVALID",
                f"Bestellung {po_number} nicht gefunden oder ungültig für Kreditor.",
                ValidationSeverity.ERROR
            ))
        else:
            # Bestellung gefunden, detaillierte Prüfung starten
            errors.extend(_validate_po_details(invoice, erp_po))

    if not errors:
        logger.info("✅ Business Validierung (ERP) erfolgreich.")
        
    return errors

def _validate_po_details(invoice: CanonicalInvoice, erp_po: ERPPurchaseOrder) -> List[ValidationError]:
    """Führt die detaillierten Prüfungen durch (Status, Beträge, Positionen - 3-Way-Match)."""
    errors: List[ValidationError] = []

    # 4.4 Statusprüfung
    if not erp_po.is_open_for_invoicing:
        errors.append(_create_business_error("ERP_PO_CLOSED", f"Bestellung {erp_po.po_number} ist geschlossen.", ValidationSeverity.ERROR))
        return errors

    # 4.5 Betragsabgleich (Netto)
    # Vergleich Rechnungsnetto (TaxExclusive) mit Bestellnetto
    if abs(invoice.tax_exclusive_amount - erp_po.total_net_amount) > AMOUNT_TOLERANCE:
        # WARNING, falls Teilrechnungen erlaubt sind. ERROR, falls exakter Match erforderlich.
        errors.append(_create_business_error(
            "ERP_PO_AMOUNT_MISMATCH",
            f"Rechnungsnetto ({invoice.tax_exclusive_amount}) weicht vom Bestellnetto ({erp_po.total_net_amount}) ab.",
            ValidationSeverity.WARNING
        ))

    # 4.5 Positionsabgleich (HAN Matching und Mengen)
    invoice_lines_matched = 0
    for inv_line in invoice.lines:
        # WICHTIG: Annahme, dass die HAN/EAN/GTIN im Feld 'item_identifier' im Canonical Model steht.
        # Wenn dieses Feld nicht existiert, muss das Modell und der Mapper angepasst werden!
        if not hasattr(inv_line, 'item_identifier') or not inv_line.item_identifier:
             errors.append(_create_business_error(
                "ERP_PO_LINE_MISSING_HAN",
                f"Position {inv_line.line_id} hat keine HAN/EAN/GTIN. Abgleich nicht möglich.",
                ValidationSeverity.WARNING, location=f"Line {inv_line.line_id}"
            ))
             continue

        han = inv_line.item_identifier
        
        if han not in erp_po.lines:
            errors.append(_create_business_error(
                "ERP_PO_LINE_ITEM_NOT_FOUND",
                f"Position {inv_line.line_id} (HAN: {han}) nicht in Bestellung gefunden.",
                ValidationSeverity.ERROR, location=f"Line {inv_line.line_id}"
            ))
            continue
        
        # Artikel gefunden, Mengenprüfung
        po_line = erp_po.lines[han]
        if inv_line.quantity > po_line.quantity_open:
            errors.append(_create_business_error(
                "ERP_PO_LINE_QUANTITY_EXCEEDED",
                f"Position {inv_line.line_id} (HAN: {han}): Menge ({inv_line.quantity}) übersteigt offene Bestellmenge ({po_line.quantity_open}).",
                ValidationSeverity.ERROR, location=f"Line {inv_line.line_id}"
            ))
            continue
        
        invoice_lines_matched += 1

    if invoice_lines_matched == 0 and len(invoice.lines) > 0:
         errors.append(_create_business_error(
            "ERP_PO_NO_LINES_MATCHED",
            f"Keine Position konnte automatisch der Bestellung zugeordnet werden.",
            ValidationSeverity.ERROR
        ))

    return errors

def _create_business_error(code: str, message: str, severity: ValidationSeverity, location: Optional[str] = None) -> ValidationError:
    """Hilfsfunktion zur Erstellung standardisierter Business-Fehler."""
    return ValidationError(
        category=ValidationCategory.BUSINESS,
        severity=severity,
        code=code,
        message=message,
        location=location
    )