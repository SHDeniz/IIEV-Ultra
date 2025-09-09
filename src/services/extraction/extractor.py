import logging
from typing import Tuple, Optional
from ...db.models import InvoiceFormat
from . import xml_util, pdf_util

logger = logging.getLogger(__name__)

def extract_invoice_data(raw_bytes: bytes) -> Tuple[InvoiceFormat, Optional[bytes]]:
    """
    Analysiert rohe Dateibytes, bestimmt das Rechnungsformat und extrahiert die strukturierten Daten (XML).
    """
    
    # 1. Versuche als XML zu parsen (XRechnung)
    detected_format, xml_root = xml_util.analyze_xml(raw_bytes)

    if detected_format in [InvoiceFormat.XRECHNUNG_CII, InvoiceFormat.XRECHNUNG_UBL, InvoiceFormat.PLAIN_XML]:
        logger.info(f"Erkanntes Format: {detected_format.value} (Reines XML)")
        return detected_format, raw_bytes

    # 2. Wenn kein valides XML, versuche als PDF zu parsen (ZUGFeRD/Factur-X)
    logger.debug("Datei nicht als reines XML erkannt. Versuche PDF-Extraktion...")
    detected_format, xml_bytes = pdf_util.extract_xml_from_pdf(raw_bytes)

    if detected_format in [InvoiceFormat.ZUGFERD_CII, InvoiceFormat.FACTURX_CII]:
        logger.info(f"Erkanntes Format: {detected_format.value} (Hybrid PDF)")
        
        # WICHTIG: Überprüfen, ob die extrahierten Bytes tatsächlich valides XML sind
        extracted_format_xml_check, _ = xml_util.analyze_xml(xml_bytes)
        if extracted_format_xml_check is None:
            logger.error("Extrahierte Daten aus PDF sind kein valides XML. Markiere als OTHER_PDF.")
            # Es ist ein PDF, aber der Inhalt ist unbrauchbar für die Automatisierung.
            return InvoiceFormat.OTHER_PDF, None
            
        return detected_format, xml_bytes

    # 3. Fallback
    if detected_format == InvoiceFormat.OTHER_PDF:
        logger.info("Erkanntes Format: OTHER_PDF (Keine strukturierten Daten gefunden)")
        return detected_format, None

    logger.warning("Konnte Dateiformat nicht bestimmen.")
    return InvoiceFormat.UNKNOWN, None