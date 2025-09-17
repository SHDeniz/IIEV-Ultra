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

# Namespaces für CII (ZUGFeRD/Factur-X)
NSMAP_CII = {
    'rsm': 'urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100',
    'ram': 'urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100',
    'udt': 'urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100'
}

def map_cii_to_canonical(root: etree._Element) -> CanonicalInvoice:
    """
    Transformiert ein CII XML Root-Element in das CanonicalInvoice Modell.
    """
    logger.info("Starte Mapping von CII (ZUGFeRD/Factur-X)...")

    # 1. Header Informationen (ExchangedDocument)
    header = xp(root, './rsm:ExchangedDocument', NSMAP_CII)
    if header is None:
        raise MappingError("CII Strukturfehler: rsm:ExchangedDocument fehlt.")
        
    # In CII ist die Rechnungsnummer im ExchangedDocument/ID
    invoice_number = xp_text(header, './ram:ID', NSMAP_CII, mandatory=True)
    
    # Datum: Format 102 ist YYYYMMDD
    issue_date_str = xp_text(header, './ram:IssueDateTime/udt:DateTimeString[@format="102"]', NSMAP_CII, mandatory=True)
    try:
        issue_date = datetime.strptime(issue_date_str, "%Y%m%d").date()
    except ValueError:
        raise MappingError(f"Ungültiges Datumsformat (erwartet YYYYMMDD): {issue_date_str}")

    invoice_type_code = xp_text(header, './ram:TypeCode', NSMAP_CII, default="380")

    # 2. Transaktionsdetails (SupplyChainTradeTransaction)
    transaction = xp(root, './rsm:SupplyChainTradeTransaction', NSMAP_CII)
    if transaction is None:
        raise MappingError("CII Strukturfehler: rsm:SupplyChainTradeTransaction fehlt.")

    # 3. Vereinbarungen und Abrechnung (Header Level)
    agreement = xp(transaction, './ram:ApplicableHeaderTradeAgreement', NSMAP_CII)
    settlement = xp(transaction, './ram:ApplicableHeaderTradeSettlement', NSMAP_CII)
    
    if agreement is None or settlement is None:
        raise MappingError("CII Strukturfehler: TradeAgreement oder TradeSettlement fehlt.")

    # Währung ist im Settlement definiert
    currency_code_str = xp_text(settlement, './ram:InvoiceCurrencyCode', NSMAP_CII, mandatory=True)
    try:
        currency_code = CurrencyCode(currency_code_str)
    except ValueError:
        # Strikte Validierung: Wenn Währungscode nicht im Enum ist, Fehler werfen.
        raise MappingError(f"Ungültiger oder nicht unterstützter Währungscode: {currency_code_str}")

    # 4. Parteien (Seller und Buyer)
    seller = _map_party(agreement, 'Seller')
    buyer = _map_party(agreement, 'Buyer')

    # 5. Summen und Steuern
    monetary_summation = xp(settlement, './ram:SpecifiedTradeSettlementHeaderMonetarySummation', NSMAP_CII)
    if monetary_summation is None:
        raise MappingError("CII Strukturfehler: SpecifiedTradeSettlementHeaderMonetarySummation fehlt.")

    line_extension_amount = xp_decimal(monetary_summation, './ram:LineTotalAmount', NSMAP_CII, mandatory=True)
    tax_exclusive_amount = xp_decimal(monetary_summation, './ram:TaxBasisTotalAmount', NSMAP_CII, mandatory=True)
    # GrandTotalAmount ist Brutto (Tax Inclusive)
    tax_inclusive_amount = xp_decimal(monetary_summation, './ram:GrandTotalAmount', NSMAP_CII, mandatory=True)
    payable_amount = xp_decimal(monetary_summation, './ram:DuePayableAmount', NSMAP_CII, mandatory=True)

    # Optionale Rabatte/Zuschläge auf Kopfebene
    allowance_total_amount = xp_decimal(monetary_summation, './ram:AllowanceTotalAmount', NSMAP_CII, default=Decimal('0.00'))
    charge_total_amount = xp_decimal(monetary_summation, './ram:ChargeTotalAmount', NSMAP_CII, default=Decimal('0.00'))
    
    # Steueraufschlüsselung
    tax_breakdown = _map_tax_breakdown(settlement)

    # 6. Positionsdaten
    lines = _map_line_items(transaction)
    
    # 7. Referenzen
    po_ref_id = xp_text(agreement, './ram:BuyerOrderReferencedDocument/ram:IssuerAssignedID', NSMAP_CII)
    po_reference = DocumentReference(document_id=po_ref_id) if po_ref_id else None
    
    # 8. Zahlungsinformationen
    payment_details = _map_payment_details(settlement)

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
        # Fängt Pydantic Validierungsfehler ab
        logger.error(f"Fehler bei der Erstellung des CanonicalInvoice Objekts aus CII Daten: {e}")
        raise MappingError(f"Validierungsfehler beim Zusammenbau der Daten: {e}")

    logger.info("CII Mapping erfolgreich abgeschlossen.")
    return invoice

# --- Helper Functions für CII ---

def _map_party(agreement: etree._Element, party_type: str) -> Party:
    """Mappt SellerTradeParty oder BuyerTradeParty."""
    base_path = f'./ram:{party_type}TradeParty'
    party_element = xp(agreement, base_path, NSMAP_CII)
    if party_element is None:
        raise MappingError(f"CII Strukturfehler: {party_type}TradeParty fehlt.")

    name = xp_text(party_element, './ram:Name', NSMAP_CII, mandatory=True)
    
    # Steuer IDs (CII erlaubt mehrere, wir nehmen die erste für VAT/TAX)
    # VA = VAT ID (USt-IdNr.), FC = Fiscal Code (Steuernummer)
    vat_id = xp_text(party_element, './ram:SpecifiedTaxRegistration[ram:ID/@schemeID="VA"]/ram:ID', NSMAP_CII)
    tax_id = xp_text(party_element, './ram:SpecifiedTaxRegistration[ram:ID/@schemeID="FC"]/ram:ID', NSMAP_CII)

    # Adresse
    address_element = xp(party_element, './ram:PostalTradeAddress', NSMAP_CII)
    if address_element is None:
        raise MappingError(f"Adresse für {party_type} fehlt.")
        
    country_code_str = xp_text(address_element, './ram:CountryID', NSMAP_CII, mandatory=True)
    
    # Strikte Validierung gegen das Enum im Canonical Model.
    try:
        country_code = CountryCode(country_code_str)
    except ValueError:
        # Wenn das System internationaler werden soll, müsste das Enum erweitert oder durch pycountry ersetzt werden.
        raise MappingError(f"Ländercode '{country_code_str}' wird vom System (aktuell) nicht unterstützt.")


    address = Address(
        street_name=xp_text(address_element, './ram:LineOne', NSMAP_CII),
        additional_street_name=xp_text(address_element, './ram:LineTwo', NSMAP_CII),
        city_name=xp_text(address_element, './ram:CityName', NSMAP_CII, mandatory=True),
        postal_zone=xp_text(address_element, './ram:PostcodeCode', NSMAP_CII, mandatory=True),
        country_code=country_code
    )

    return Party(
        name=name,
        vat_id=vat_id,
        tax_id=tax_id,
        address=address
    )

def _map_tax_breakdown(settlement: etree._Element) -> List[TaxBreakdown]:
    """Mappt die Steueraufschlüsselung (ApplicableTradeTax)."""
    tax_elements = xps(settlement, './ram:ApplicableTradeTax', NSMAP_CII)
    breakdown = []

    for tax_el in tax_elements:
        # Wichtig: Nur VAT (Umsatzsteuer) berücksichtigen
        if xp_text(tax_el, './ram:TypeCode', NSMAP_CII) != 'VAT':
            continue

        taxable_amount = xp_decimal(tax_el, './ram:BasisAmount', NSMAP_CII, mandatory=True)
        tax_amount = xp_decimal(tax_el, './ram:CalculatedAmount', NSMAP_CII, mandatory=True)
        
        # Kategorie
        category_code_str = xp_text(tax_el, './ram:CategoryCode', NSMAP_CII, mandatory=True)
        try:
            tax_category = TaxCategory(category_code_str)
        except ValueError:
            raise MappingError(f"Ungültige Steuerkategorie: {category_code_str}")
            
        # Rate: Kann in RateApplicablePercent oder ApplicablePercent stehen (je nach ZUGFeRD Profil)
        rate_str = xp_text(tax_el, './ram:RateApplicablePercent', NSMAP_CII)
        if not rate_str:
             rate_str = xp_text(tax_el, './ram:ApplicablePercent', NSMAP_CII)
             
        if not rate_str:
             # Bei Steuerbefreiungen (Z, E) oder Reverse Charge (AE) ist die Rate oft 0 oder nicht angegeben
             if tax_category in [TaxCategory.ZERO_RATE, TaxCategory.EXEMPT, TaxCategory.REVERSE_CHARGE]:
                 tax_rate = Decimal('0.00')
             else:
                # Bei Standard-Steuer (S) muss eine Rate vorhanden sein.
                raise MappingError(f"Steuersatz (Percent) fehlt für Steuerkategorie {tax_category.value}.")
        else:
            tax_rate = Decimal(rate_str)

        breakdown.append(TaxBreakdown(
            tax_category=tax_category,
            tax_rate=tax_rate,
            taxable_amount=taxable_amount,
            tax_amount=tax_amount
        ))
    
    return breakdown

def _map_line_items(transaction: etree._Element) -> List[InvoiceLine]:
    """Mappt die Rechnungspositionen (IncludedSupplyChainTradeLineItem)."""
    line_elements = xps(transaction, './ram:IncludedSupplyChainTradeLineItem', NSMAP_CII)
    lines = []

    for line_el in line_elements:
        # 1. Line ID
        doc_context = xp(line_el, './ram:AssociatedDocumentLineDocument', NSMAP_CII)
        line_id = xp_text(doc_context, './ram:LineID', NSMAP_CII, mandatory=True)

        # 2. Produktinformationen
        product = xp(line_el, './ram:SpecifiedTradeProduct', NSMAP_CII)
        item_name = xp_text(product, './ram:Name', NSMAP_CII, mandatory=True)
        item_description = xp_text(product, './ram:Description', NSMAP_CII)
        
        # 2a. Artikel-Identifikation (EAN/GTIN/HAN für 3-Way-Match)
        # Priorität: 1. GlobalID (GTIN/EAN), 2. SellerAssignedID (HAN), 3. BuyerAssignedID
        item_identifier = None
        
        # Versuche GTIN/EAN zu extrahieren (GlobalID mit schemeID)
        global_id_element = xp(product, './ram:GlobalID', NSMAP_CII)
        if global_id_element is not None:
            item_identifier = global_id_element.text
            scheme_id = global_id_element.get('schemeID', '')
            logger.debug(f"Position {line_id}: GlobalID gefunden ({scheme_id}): {item_identifier}")
        
        # Fallback auf Verkäufer-Artikelnummer (HAN)
        if not item_identifier:
            seller_id = xp_text(product, './ram:SellerAssignedID', NSMAP_CII)
            if seller_id:
                item_identifier = seller_id
                logger.debug(f"Position {line_id}: SellerAssignedID (HAN) gefunden: {item_identifier}")
        
        # Optional: BuyerAssignedID als letzter Fallback
        if not item_identifier:
            buyer_id = xp_text(product, './ram:BuyerAssignedID', NSMAP_CII)
            if buyer_id:
                item_identifier = buyer_id
                logger.debug(f"Position {line_id}: BuyerAssignedID gefunden: {item_identifier}")

        # 3. Transaktionsdetails (Agreement, Delivery, Settlement)
        line_agreement = xp(line_el, './ram:SpecifiedLineTradeAgreement', NSMAP_CII)
        line_delivery = xp(line_el, './ram:SpecifiedLineTradeDelivery', NSMAP_CII)
        line_settlement = xp(line_el, './ram:SpecifiedLineTradeSettlement', NSMAP_CII)

        # Mengen
        quantity = xp_decimal(line_delivery, './ram:BilledQuantity', NSMAP_CII, mandatory=True)
        unit_code = xp_text(line_delivery, './ram:BilledQuantity/@unitCode', NSMAP_CII, default="C62")

        # Preise (Robustes Handling von BasisQuantity)
        # Wir verwenden hier NetPrice gemäß EN16931 Empfehlung.
        price_element = xp(line_agreement, './ram:NetPriceProductTradePrice', NSMAP_CII)
        
        if price_element is None:
             raise MappingError(f"NetPriceProductTradePrice fehlt für Position {line_id}.")

        # WICHTIG: Berechnung Unit Price = ChargeAmount / BasisQuantity. 
        unit_price_amount = xp_decimal(price_element, './ram:ChargeAmount', NSMAP_CII, mandatory=True)
        # Wenn BasisQuantity fehlt, ist sie 1.0.
        basis_quantity = xp_decimal(price_element, './ram:BasisQuantity', NSMAP_CII, default=Decimal('1.0'))
        
        if basis_quantity == Decimal('0'):
             raise MappingError(f"BasisQuantity ist 0 für Position {line_id}, Division nicht möglich.")
             
        unit_price = unit_price_amount / basis_quantity

        # Zeilensumme (Netto)
        monetary_sum = xp(line_settlement, './ram:SpecifiedTradeSettlementLineMonetarySummation', NSMAP_CII)
        line_net_amount = xp_decimal(monetary_sum, './ram:LineTotalAmount', NSMAP_CII, mandatory=True)

        # Steuern
        tax_el = xp(line_settlement, './ram:ApplicableTradeTax', NSMAP_CII)
        category_code_str = xp_text(tax_el, './ram:CategoryCode', NSMAP_CII, mandatory=True)
        try:
            tax_category = TaxCategory(category_code_str)
        except ValueError:
            raise MappingError(f"Ungültige Steuerkategorie in Position {line_id}: {category_code_str}")

        # Rate (analog zu Kopfebene)
        rate_str = xp_text(tax_el, './ram:RateApplicablePercent', NSMAP_CII)
        if not rate_str:
             rate_str = xp_text(tax_el, './ram:ApplicablePercent', NSMAP_CII)
             
        if not rate_str:
             # Annahme 0 bei fehlender Rate (z.B. bei Exempt/Zero/Reverse Charge)
             tax_rate = Decimal('0.00') 
        else:
            tax_rate = Decimal(rate_str)
            
        # TODO: Implementierung von Rabatten/Zuschlägen auf Positionsebene (allowance_charge_amount)

        lines.append(InvoiceLine(
            line_id=line_id,
            item_name=item_name,
            item_description=item_description,
            item_identifier=item_identifier,  # HAN/EAN/GTIN für ERP 3-Way-Match
            quantity=quantity,
            unit_code=unit_code,
            unit_price=unit_price,
            line_net_amount=line_net_amount,
            tax_category=tax_category,
            tax_rate=tax_rate
        ))
    
    return lines

def _map_payment_details(settlement: etree._Element) -> List[BankDetails]:
    """Mappt Bankverbindungen (SpecifiedTradeSettlementPaymentMeans)."""
    # Filtert nach Typen, die Bankdaten enthalten (z.B. Überweisung Code 30 oder 58)
    payment_means = xps(settlement, "./ram:SpecifiedTradeSettlementPaymentMeans[ram:TypeCode='30' or ram:TypeCode='58']", NSMAP_CII)
    details = []
    
    for means in payment_means:
        # Payee Financial Account (Empfängerkonto)
        account = xp(means, './ram:PayeePartyCreditorFinancialAccount', NSMAP_CII)
        if account is not None:
            iban = xp_text(account, './ram:IBANID', NSMAP_CII)
            # BIC ist in einem separaten Element
            bic = xp_text(means, './ram:PayeeSpecifiedCreditorFinancialInstitution/ram:BICID', NSMAP_CII)
            account_name = xp_text(account, './ram:AccountName', NSMAP_CII)
            
            if iban:
                details.append(BankDetails(
                    iban=iban,
                    bic=bic,
                    account_name=account_name
                ))
    return details