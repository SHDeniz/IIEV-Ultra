import logging
from lxml import etree
from typing import Optional

from ...db.models import InvoiceFormat
from ...schemas.canonical_model import CanonicalInvoice
from ..extraction.xml_util import analyze_xml
from .xpath_util import MappingError
from .cii_mapper import map_cii_to_canonical
from .ubl_mapper import map_ubl_to_canonical

logger = logging.getLogger(__name__)

def map_xml_to_canonical(xml_bytes: bytes, detected_format: InvoiceFormat) -> CanonicalInvoice:
    """
    Haupt-Einstiegspunkt für das Mapping.
    Wählt den korrekten Mapper (CII oder UBL) basierend auf dem Format.
    """
    
    # 1. XML Parsen und Root-Element extrahieren. 
    # Wir nutzen analyze_xml erneut, um das Root-Element zu erhalten und das exakte XML-Format zu bestätigen.
    format_analyzed, root = analyze_xml(xml_bytes)
    
    if root is None:
        # Sollte durch vorherige Schritte abgefangen sein, aber als Sicherheitsnetz.
        raise MappingError("Die bereitgestellten Bytes sind kein valides XML.")
        
    # 2. Bestimmung des Zielformats für das Mapping
    # Hybride Formate (ZUGFeRD/Factur-X) verwenden die CII-Syntax.
    if detected_format in [InvoiceFormat.ZUGFERD_CII, InvoiceFormat.FACTURX_CII, InvoiceFormat.XRECHNUNG_CII]:
         format_to_map = InvoiceFormat.XRECHNUNG_CII
    elif detected_format == InvoiceFormat.XRECHNUNG_UBL:
         format_to_map = InvoiceFormat.XRECHNUNG_UBL
    elif format_analyzed in [InvoiceFormat.XRECHNUNG_CII, InvoiceFormat.XRECHNUNG_UBL]:
        # Fallback, wenn detected_format unspezifisch war (z.B. PLAIN_XML)
        format_to_map = format_analyzed
    else:
        raise MappingError(f"Das Format {detected_format.value} wird für das Mapping nicht unterstützt.")

    # Optional: Cross-Check zwischen erkanntem Format und XML-Inhalt
    if format_analyzed and format_analyzed != format_to_map:
         logger.warning(f"Diskrepanz festgestellt: Datei als {detected_format.value} identifiziert, XML-Analyse ergab {format_analyzed.value}. Verwende {format_to_map.value} für Mapping.")


    # 3. Routing zum spezifischen Mapper
    try:
        if format_to_map == InvoiceFormat.XRECHNUNG_CII:
            return map_cii_to_canonical(root)
        
        elif format_to_map == InvoiceFormat.XRECHNUNG_UBL:
            return map_ubl_to_canonical(root)
            
    except MappingError as e:
        # Fange spezifische Mapping-Fehler ab und gebe sie weiter
        logger.error(f"Mapping-Fehler im Format {format_to_map.value}: {e}")
        raise
    except Exception as e:
        # Fange unerwartete Fehler während des Mappings ab (z.B. Pydantic Validation Errors)
        logger.error(f"Unerwarteter Fehler während des Mappings von {format_to_map.value}: {e}", exc_info=True)
        raise MappingError(f"Interner Fehler beim Mapping: {e}")