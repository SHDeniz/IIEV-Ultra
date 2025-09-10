# src/services/extraction/pdf_util.py (Vollständig aktualisiert)

import logging
import io
from typing import Optional, Tuple
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from ...db.models import InvoiceFormat

logger = logging.getLogger(__name__)

# Standardisierte Anhangsnamen
ZUGFERD_FILENAMES = [
    "factur-x.xml",       # Factur-X und ZUGFeRD 2.1+
    "zugferd-invoice.xml", # ZUGFeRD 1.0/2.0
    "xrechnung.xml"
]

def extract_xml_from_pdf(pdf_bytes: bytes) -> Tuple[Optional[InvoiceFormat], Optional[bytes]]:
    """
    Analysiert eine PDF-Datei und extrahiert das eingebettete XML mittels pypdf.
    """
    # Schneller Check auf PDF-Header
    if not pdf_bytes.strip().startswith(b'%PDF-'):
        return InvoiceFormat.UNKNOWN, None

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        
        # WICHTIG: reader.attachments gibt in pypdf ein Dict[str, List[bytes]] zurück
        attachments = reader.attachments
        
        if not attachments:
            return InvoiceFormat.OTHER_PDF, None

        # Iteriere durch das Dictionary mit .items()
        # attachment_data ist typischerweise List[bytes]
        for filename, attachment_data in attachments.items():
            if filename in ZUGFERD_FILENAMES:
                
                # Robustes Handling der Datenstruktur
                xml_data: Optional[bytes] = None

                if isinstance(attachment_data, list) and len(attachment_data) > 0:
                    # KORREKTUR: Nimm das erste Element der Liste
                    xml_data = attachment_data[0]
                    if len(attachment_data) > 1:
                        logger.warning(f"Anhang {filename} hat mehr als einen Datenstream ({len(attachment_data)}). Verwende den ersten.")
                
                # Fallback für ältere pypdf Versionen oder einfache PDFs, wo es direkt bytes sein könnte
                elif isinstance(attachment_data, bytes):
                     xml_data = attachment_data

                # Sicherheitsprüfung des Typs
                if not isinstance(xml_data, bytes):
                    logger.error(f"Unerwarteter Datentyp für Anhang {filename}: {type(attachment_data)}. Kann nicht extrahieren.")
                    continue

                logger.info(f"Erfolgreich {filename} aus PDF extrahiert.")
                
                # Bestimme spezifisches Format
                if filename == "factur-x.xml":
                    return InvoiceFormat.FACTURX_CII, xml_data
                else:
                    return InvoiceFormat.ZUGFERD_CII, xml_data

        # Kein standardisiertes XML gefunden
        return InvoiceFormat.OTHER_PDF, None

    except PdfReadError as e:
        # Fängt beschädigte oder ungültige PDFs ab
        logger.error(f"Beschädigte oder ungültige PDF-Datei: {e}")
        return InvoiceFormat.UNKNOWN, None
    except Exception as e:
        # Fängt alle anderen unerwarteten Fehler ab
        logger.error(f"Unerwarteter Fehler bei der PDF-Extraktion: {e}", exc_info=True)
        return InvoiceFormat.UNKNOWN, None