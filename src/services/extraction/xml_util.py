import logging
from lxml import etree
from typing import Tuple, Optional
from io import BytesIO
from ...db.models import InvoiceFormat

logger = logging.getLogger(__name__)

# Namespaces für EN 16931 konforme Formate
NS_CII = "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
NS_UBL_INVOICE = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
NS_UBL_CREDITNOTE = "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2"

def analyze_xml(xml_bytes: bytes) -> Tuple[Optional[InvoiceFormat], Optional[etree._Element]]:
    """
    Analysiert XML-Bytes, um das Rechnungsformat (CII oder UBL) zu bestimmen und das Root-Element zurückzugeben.
    """
    try:
        # XML parsen. Sicherheit: resolve_entities=False (Schutz vor XXE)
        parser = etree.XMLParser(resolve_entities=False)
        tree = etree.parse(BytesIO(xml_bytes), parser=parser)
        root = tree.getroot()

        # Bestimmung des Namespaces des Root-Elements.
        # Wir verwenden etree.QName, um den Namespace unabhängig vom Präfix zu extrahieren.
        root_namespace = etree.QName(root.tag).namespace

        if root_namespace == NS_CII:
            # Dies ist CII (Cross Industry Invoice)
            return InvoiceFormat.XRECHNUNG_CII, root
        
        if root_namespace == NS_UBL_INVOICE or root_namespace == NS_UBL_CREDITNOTE:
            # Dies ist UBL (Universal Business Language)
            return InvoiceFormat.XRECHNUNG_UBL, root

        logger.warning(f"XML erkannt, aber Root-Namespace ({root_namespace}) entspricht nicht EN 16931 (CII oder UBL).")
        return InvoiceFormat.PLAIN_XML, root

    except etree.XMLSyntaxError as e:
        logger.debug(f"Keine gültige XML-Syntax: {e}")
        return None, None
    except Exception as e:
        logger.error(f"Unerwarteter Fehler bei der XML-Analyse: {e}")
        return None, None