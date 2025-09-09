import logging
from lxml import etree
from typing import Dict, Optional, List
from decimal import Decimal
from datetime import datetime

from ...schemas.canonical_model import (
    CanonicalInvoice, Party, Address, InvoiceLine, TaxBreakdown, 
    CountryCode, CurrencyCode, TaxCategory, DocumentReference, BankDetails
)
from .xpath_util import xp, xps, xp_text, xp_decimal, MappingError

logger = logging.getLogger(__name__)

# Namespaces für UBL (Common Components)
NSMAP_UBL = {
    'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
    'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
    # Root Namespaces werden nicht benötigt, wenn wir cbc/cac Präfixe verwenden
}

def map_ubl_to_canonical(root: etree._Element) -> CanonicalInvoice:
    """
    Transformiert ein UBL XML Root-Element in das CanonicalInvoice Modell.
    """
    logger.info("Starte Mapping von UBL (XRechnung UBL/Peppol)...")
    
    # Dynamische Erkennung des Dokumententyps (Invoice oder CreditNote)
    root_tag = etree.QName(root.tag).localname
    if root_tag not in ['Invoice', 'CreditNote']:
        raise MappingError(f"Unerwartetes UBL Root-Element: {root_tag}")
    
    # 1. Header Informationen
    invoice_number = xp_text(root, './cbc:ID', NSMAP_UBL, mandatory=True)
    issue_date_str = xp_text(root, './cbc:IssueDate', NSMAP_UBL, mandatory=True)
    
    # UBL Format ist YYYY-MM-DD
    try:
        issue_date = datetime.strptime(issue_date_str, "%Y-%m-%d").date()
    except ValueError:
        raise MappingError(f"Ungültiges Datumsformat (erwartet YYYY-MM-DD): {issue_date_str}")

    # Type Code dynamisch basierend auf Root-Tag
    type_code_tag = 'InvoiceTypeCode' if root_tag == 'Invoice' else 'CreditNoteTypeCode'
    default_type = "380" if root_tag == 'Invoice' else "381"
    invoice_type_code = xp_text(root, f'./cbc:{type_code_tag}', NSMAP_UBL, default=default_type)

    currency_code_str = xp_text(root, './cbc:DocumentCurrencyCode', NSMAP_UBL, mandatory=True)
    try:
        currency_code = CurrencyCode(currency_code_str)
    except ValueError:
        raise MappingError(f"Ungültiger oder nicht unterstützter Währungscode: {currency_code_str}")

    # 2. Parteien (Supplier und Customer)
    seller = _map_party(root, 'AccountingSupplierParty')
    buyer = _map_party(root, 'AccountingCustomerParty')

    # 3. Summen (LegalMonetaryTotal oder RequestedMonetaryTotal)
    monetary_total_tag = 'LegalMonetaryTotal' if root_tag == 'Invoice' else 'RequestedMonetaryTotal'
    monetary_total = xp(root, f'./cac:{monetary_total_tag}', NSMAP_UBL)
    if monetary_total is None:
        raise MappingError(f"UBL Strukturfehler: cac:{monetary_total_tag} fehlt.")

    line_extension_amount = xp_decimal(monetary_total, './cbc:LineExtensionAmount', NSMAP_UBL, mandatory=True)
    tax_exclusive_amount = xp_decimal(monetary_total, './cbc:TaxExclusiveAmount', NSMAP_UBL, mandatory=True)
    tax_inclusive_amount = xp_decimal(monetary_total, './cbc:TaxInclusiveAmount', NSMAP_UBL, mandatory=True)
    payable_amount = xp_decimal(monetary_total, './cbc:PayableAmount', NSMAP_UBL, mandatory=True)

    # Optionale Rabatte/Zuschläge
    allowance_total_amount = xp_decimal(monetary_total, './cbc:AllowanceTotalAmount', NSMAP_UBL, default=Decimal('0.00'))
    charge_total_amount = xp_decimal(monetary_total, './cbc:ChargeTotalAmount', NSMAP_UBL, default=Decimal('0.00'))

    # 4. Steueraufschlüsselung (TaxTotal)
    # Wir übergeben monetary_total für den Check auf Steuerpflichtigkeit
    tax_breakdown = _map_tax_breakdown(root, monetary_total)

    # 5. Positionsdaten
    line_tag = 'InvoiceLine' if root_tag == 'Invoice' else 'CreditNoteLine'
    lines = _map_line_items(root, line_tag)

    # 6. Referenzen
    po_ref = xp(root, './cac:OrderReference', NSMAP_UBL)
    po_ref_id = xp_text(po_ref, './cbc:ID', NSMAP_UBL)
    po_reference = DocumentReference(document_id=po_ref_id) if po_ref_id else None

    # 7. Zahlungsinformationen
    payment_details = _map_payment_details(root)

    # Zusammenbau des Canonical Models
    try:
        invoice = CanonicalInvoice(
            invoice_number=invoice_number,
            issue_date=issue_date,
            invoice_type_code=invoice_type_code,
            currency_code=currency_code,
            seller=seller,
            buyer=buyer,
            lines=lines,
            line_extension_amount=line_extension_amount,
            allowance_total_amount=allowance_total_amount,
            charge_total_amount=charge_total_amount,
            tax_exclusive_amount=tax_exclusive_amount,
            tax_inclusive_amount=tax_inclusive_amount,
            payable_amount=payable_amount,
            tax_breakdown=tax_breakdown,
            purchase_order_reference=po_reference,
            payment_details=payment_details
        )
    except Exception as e:
        logger.error(f"Fehler bei der Erstellung des CanonicalInvoice Objekts aus UBL Daten: {e}")
        raise MappingError(f"Validierungsfehler beim Zusammenbau der Daten: {e}")

    logger.info("UBL Mapping erfolgreich abgeschlossen.")
    return invoice

# --- Helper Functions für UBL ---

def _map_party(root: etree._Element, party_role: str) -> Party:
    """Mappt AccountingSupplierParty oder AccountingCustomerParty."""
    base_path = f'./cac:{party_role}/cac:Party'
    party_element = xp(root, base_path, NSMAP_UBL)
    if party_element is None:
        raise MappingError(f"UBL Strukturfehler: {party_role}/Party fehlt.")

    # Name kann in PartyName oder PartyLegalEntity/RegistrationName stehen
    name = xp_text(party_element, './cac:PartyName/cbc:Name', NSMAP_UBL)
    if not name:
        name = xp_text(party_element, './cac:PartyLegalEntity/cbc:RegistrationName', NSMAP_UBL, mandatory=True)

    # Steuer IDs
    # UBL erlaubt mehrere TaxScheme, wir suchen nach VAT
    vat_id = xp_text(party_element, './cac:PartyTaxScheme[cac:TaxScheme/cbc:ID="VAT"]/cbc:CompanyID', NSMAP_UBL)
    
    # Steuernummer (Heuristik für Deutschland: oft in PartyLegalEntity/CompanyID, wenn nicht VAT)
    tax_id = None
    legal_entity_id = xp_text(party_element, './cac:PartyLegalEntity/cbc:CompanyID', NSMAP_UBL)
    if legal_entity_id and legal_entity_id != vat_id:
        tax_id = legal_entity_id


    # Adresse
    address_element = xp(party_element, './cac:PostalAddress', NSMAP_UBL)
    if address_element is None:
        raise MappingError(f"Adresse für {party_role} fehlt.")
    
    country_code_str = xp_text(address_element, './cac:Country/cbc:IdentificationCode', NSMAP_UBL, mandatory=True)

    # Strikte Validierung gegen Enum
    try:
        country_code = CountryCode(country_code_str)
    except ValueError:
        raise MappingError(f"Ländercode '{country_code_str}' wird vom System (aktuell) nicht unterstützt.")

    address = Address(
        street_name=xp_text(address_element, './cbc:StreetName', NSMAP_UBL),
        additional_street_name=xp_text(address_element, './cbc:AdditionalStreetName', NSMAP_UBL),
        city_name=xp_text(address_element, './cbc:CityName', NSMAP_UBL, mandatory=True),
        postal_zone=xp_text(address_element, './cbc:PostalZone', NSMAP_UBL, mandatory=True),
        country_code=country_code
    )

    return Party(
        name=name,
        vat_id=vat_id,
        tax_id=tax_id,
        address=address
    )

def _map_tax_breakdown(root: etree._Element, monetary_total: etree._Element) -> List[TaxBreakdown]:
    """Mappt die Steueraufschlüsselung (TaxTotal/TaxSubtotal)."""
    # UBL hat oft mehrere TaxTotal Elemente. Wir suchen dasjenige, das TaxSubtotal enthält.
    tax_total = xp(root, './cac:TaxTotal[cac:TaxSubtotal]', NSMAP_UBL)
    
    if tax_total is None:
        # Prüfen, ob Steuern anfallen, basierend auf den Gesamtsummen.
        tax_inclusive = xp_decimal(monetary_total, './cbc:TaxInclusiveAmount', NSMAP_UBL, mandatory=True)
        tax_exclusive = xp_decimal(monetary_total, './cbc:TaxExclusiveAmount', NSMAP_UBL, mandatory=True)
        
        if tax_inclusive > tax_exclusive:
             # Wenn Steuern anfallen, aber keine Aufschlüsselung existiert, ist das ein Fehler.
             raise MappingError("UBL Strukturfehler: cac:TaxTotal mit cac:TaxSubtotal fehlt, obwohl Steuern berechnet wurden.")
        
        # Wenn keine Steuern anfallen (z.B. innergemeinschaftlich), ist die Liste leer.
        return []

    subtotal_elements = xps(tax_total, './cac:TaxSubtotal', NSMAP_UBL)
    breakdown = []

    for sub_el in subtotal_elements:
        taxable_amount = xp_decimal(sub_el, './cbc:TaxableAmount', NSMAP_UBL, mandatory=True)
        tax_amount = xp_decimal(sub_el, './cbc:TaxAmount', NSMAP_UBL, mandatory=True)

        # Kategorie und Rate
        tax_category_el = xp(sub_el, './cac:TaxCategory', NSMAP_UBL)

        # Wichtig: Nur VAT berücksichtigen
        if xp_text(tax_category_el, './cac:TaxScheme/cbc:ID', NSMAP_UBL) != 'VAT':
            continue

        category_code_str = xp_text(tax_category_el, './cbc:ID', NSMAP_UBL, mandatory=True)
        try:
            tax_category = TaxCategory(category_code_str)
        except ValueError:
            raise MappingError(f"Ungültige Steuerkategorie: {category_code_str}")

        tax_rate = xp_decimal(tax_category_el, './cbc:Percent', NSMAP_UBL)
        
        if tax_rate is None:
            # Bei Steuerbefreiungen (Z, E, AE) ist die Rate oft 0 oder nicht angegeben
            if tax_category in [TaxCategory.ZERO_RATE, TaxCategory.EXEMPT, TaxCategory.REVERSE_CHARGE]:
                 tax_rate = Decimal('0.00')
            else:
                raise MappingError(f"Steuersatz (Percent) fehlt für Steuerkategorie {tax_category.value}.")


        breakdown.append(TaxBreakdown(
            tax_category=tax_category,
            tax_rate=tax_rate,
            taxable_amount=taxable_amount,
            tax_amount=tax_amount
        ))
    
    return breakdown

def _map_line_items(root: etree._Element, line_tag: str) -> List[InvoiceLine]:
    """Mappt die Rechnungspositionen (InvoiceLine oder CreditNoteLine)."""
    line_elements = xps(root, f'./cac:{line_tag}', NSMAP_UBL)
    lines = []

    for line_el in line_elements:
        # 1. Line ID und Mengen
        line_id = xp_text(line_el, './cbc:ID', NSMAP_UBL, mandatory=True)
        
        # Menge und Unit Code (InvoicedQuantity oder CreditedQuantity)
        quantity_tag = 'InvoicedQuantity' if line_tag == 'InvoiceLine' else 'CreditedQuantity'
        quantity = xp_decimal(line_el, f'./cbc:{quantity_tag}', NSMAP_UBL, mandatory=True)
        unit_code = xp_text(line_el, f'./cbc:{quantity_tag}/@unitCode', NSMAP_UBL, default="C62")

        # 2. Zeilensumme (Netto)
        line_net_amount = xp_decimal(line_el, './cbc:LineExtensionAmount', NSMAP_UBL, mandatory=True)

        # 3. Produktinformationen
        item = xp(line_el, './cac:Item', NSMAP_UBL)
        item_name = xp_text(item, './cbc:Name', NSMAP_UBL, mandatory=True)
        item_description = xp_text(item, './cbc:Description', NSMAP_UBL)

        # 4. Steuern (Item/TaxCategory)
        tax_category_el = xp(item, './cac:ClassifiedTaxCategory', NSMAP_UBL)
        category_code_str = xp_text(tax_category_el, './cbc:ID', NSMAP_UBL, mandatory=True)
        try:
            tax_category = TaxCategory(category_code_str)
        except ValueError:
            raise MappingError(f"Ungültige Steuerkategorie in Position {line_id}: {category_code_str}")
        
        tax_rate = xp_decimal(tax_category_el, './cbc:Percent', NSMAP_UBL, default=Decimal('0.00'))

        # 5. Preisdetails (Price) - Robustes Handling von BaseQuantity
        price_el = xp(line_el, './cac:Price', NSMAP_UBL)
        
        # WICHTIG: Berechnung Unit Price = PriceAmount / BaseQuantity. 
        unit_price_amount = xp_decimal(price_el, './cbc:PriceAmount', NSMAP_UBL, mandatory=True)
        # Wenn BaseQuantity fehlt, ist sie 1.0.
        basis_quantity = xp_decimal(price_el, './cbc:BaseQuantity', NSMAP_UBL, default=Decimal('1.0'))

        if basis_quantity == Decimal('0'):
             raise MappingError(f"BaseQuantity ist 0 für Position {line_id}, Division nicht möglich.")
             
        unit_price = unit_price_amount / basis_quantity
        
        # TODO: Implementierung von Rabatten/Zuschlägen auf Positionsebene (cac:AllowanceCharge)

        lines.append(InvoiceLine(
            line_id=line_id,
            item_name=item_name,
            item_description=item_description,
            quantity=quantity,
            unit_code=unit_code,
            unit_price=unit_price,
            line_net_amount=line_net_amount,
            tax_category=tax_category,
            tax_rate=tax_rate
        ))
    
    return lines

def _map_payment_details(root: etree._Element) -> List[BankDetails]:
    """Mappt Bankverbindungen (PaymentMeans)."""
    # Filtert nach Typen, die Bankdaten enthalten (z.B. Überweisung Code 30 oder 58)
    payment_means = xps(root, "./cac:PaymentMeans[cbc:PaymentMeansCode='30' or cbc:PaymentMeansCode='58']", NSMAP_UBL)
    details = []
    
    for means in payment_means:
        # Payee Financial Account (Empfängerkonto)
        account = xp(means, './cac:PayeeFinancialAccount', NSMAP_UBL)
        if account is not None:
            iban = xp_text(account, './cbc:ID', NSMAP_UBL) # In UBL ist ID oft die IBAN
            
            # BIC ist tiefer verschachtelt
            bic = xp_text(account, './cac:FinancialInstitutionBranch/cac:FinancialInstitution/cbc:ID', NSMAP_UBL)
            if not bic:
                # Fallback für XRechnung, wo BIC manchmal in FinancialInstitutionBranch/ID steht
                bic = xp_text(account, './cac:FinancialInstitutionBranch/cbc:ID', NSMAP_UBL)

            account_name = xp_text(account, './cbc:Name', NSMAP_UBL)
            
            if iban:
                details.append(BankDetails(
                    iban=iban,
                    bic=bic,
                    account_name=account_name
                ))
    return details