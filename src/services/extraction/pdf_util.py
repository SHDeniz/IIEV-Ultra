import logging
import PyPDF2
import io
from typing import Optional, Tuple
from ...db.models import InvoiceFormat

logger = logging.getLogger(__name__)

# Standardisierte Anhangsnamen für ZUGFeRD und Factur-X
ZUGFERD_FILENAMES = [
    "factur-x.xml",       # Factur-X und ZUGFeRD 2.1+
    "zugferd-invoice.xml", # ZUGFeRD 1.0/2.0
    "xrechnung.xml"       # Manchmal in hybriden XRechnungen verwendet
]

def extract_xml_from_pdf(pdf_bytes: bytes) -> Tuple[Optional[InvoiceFormat], Optional[bytes]]:
    """
    Analysiert eine PDF-Datei und extrahiert das eingebettete XML.
    Löst PDF-Objektreferenzen robust auf.
    """
    # Schneller Check auf PDF-Header
    if not pdf_bytes.strip().startswith(b'%PDF-'):
        return InvoiceFormat.UNKNOWN, None

    try:
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        
        # Zugriff auf den PDF-Katalog (Root)
        if reader.trailer is None or "/Root" not in reader.trailer:
            return InvoiceFormat.OTHER_PDF, None
            
        # Wichtig: .get_object() verwenden, um indirekte Referenzen aufzulösen
        catalog = reader.trailer["/Root"].get_object()

        # Navigiere zu Names -> EmbeddedFiles
        names = catalog.get("/Names")
        if not names:
            return InvoiceFormat.OTHER_PDF, None
        names = names.get_object()

        embedded_files_dict = names.get("/EmbeddedFiles")
        if not embedded_files_dict:
             return InvoiceFormat.OTHER_PDF, None
        embedded_files_dict = embedded_files_dict.get_object()

        # Die /Names Liste enthält [Name1, FileSpec1, Name2, FileSpec2, ...]
        embedded_files_list = embedded_files_dict.get("/Names")
        if not embedded_files_list or not isinstance(embedded_files_list, list):
            return InvoiceFormat.OTHER_PDF, None

        # Iteriere durch eingebettete Dateien
        for i in range(0, len(embedded_files_list) - 1, 2):
            try:
                filename = embedded_files_list[i]
                if filename in ZUGFERD_FILENAMES:
                    # FileSpec auflösen
                    file_spec = embedded_files_list[i+1].get_object()
                    
                    # Zugriff auf den Embedded File Stream (EF)
                    if "/EF" in file_spec and "/F" in file_spec["/EF"]:
                        file_data_stream = file_spec["/EF"]["/F"]
                        xml_data = file_data_stream.get_data()
                        
                        logger.info(f"Erfolgreich {filename} aus PDF extrahiert.")
                        
                        # Bestimme spezifisches Format
                        if filename == "factur-x.xml":
                            return InvoiceFormat.FACTURX_CII, xml_data
                        else:
                            return InvoiceFormat.ZUGFERD_CII, xml_data
            except Exception as inner_e:
                logger.warning(f"Fehler bei der Verarbeitung eingebetteter Datei bei Index {i}: {inner_e}")
                continue

        # Kein standardisiertes XML gefunden
        return InvoiceFormat.OTHER_PDF, None

    except PyPDF2.errors.PdfReadError as e:
        logger.error(f"Beschädigte oder ungültige PDF-Datei: {e}")
        return InvoiceFormat.UNKNOWN, None
    except Exception as e:
        logger.error(f"Unerwarteter Fehler bei der PDF-Extraktion: {e}")
        return InvoiceFormat.UNKNOWN, None