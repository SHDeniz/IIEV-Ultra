from lxml import etree
from typing import Optional, List, Dict
from decimal import Decimal, InvalidOperation
import logging

logger = logging.getLogger(__name__)

class MappingError(ValueError):
    """Spezifische Exception für Mapping-Fehler (Daten fehlen oder sind ungültig)."""
    pass

def xp(element: etree._Element, query: str, nsmap: Dict[str, str]) -> Optional[etree._Element]:
    """Führt XPath-Abfrage aus und gibt das erste passende Element zurück, oder None."""
    if element is None: return None
    try:
        results = element.xpath(query, namespaces=nsmap)
        return results[0] if results else None
    except Exception as e:
        logger.warning(f"Fehler bei XPath-Abfrage '{query}': {e}")
        return None

def xps(element: etree._Element, query: str, nsmap: Dict[str, str]) -> List[etree._Element]:
    """Führt XPath-Abfrage aus und gibt alle passenden Elemente zurück."""
    if element is None: return []
    try:
        return element.xpath(query, namespaces=nsmap)
    except Exception:
        return []

def xp_text(element: etree._Element, query: str, nsmap: Dict[str, str], default: Optional[str] = None, mandatory: bool = False) -> Optional[str]:
    """Führt XPath-Abfrage aus und gibt den Textinhalt des ersten Treffers zurück, gestrippt."""
    if element is None:
        if mandatory:
             raise MappingError(f"Pflichtfeld fehlt, da Kontext-Element None ist. XPath: {query}")
        return default

    results = element.xpath(query, namespaces=nsmap)
    text = None
    if results:
        # Ergebnis kann Element (hat .text Attribut) oder Attribut/Textknoten (ist str) sein
        text = results[0].text if hasattr(results[0], 'text') else str(results[0])
        text = text.strip() if text else None
    
    if text:
        return text
    
    if mandatory:
        raise MappingError(f"Pflichtfeld fehlt oder ist leer bei XPath: {query}")
        
    return default

def xp_decimal(element: etree._Element, query: str, nsmap: Dict[str, str], default: Optional[Decimal] = None, mandatory: bool = False) -> Optional[Decimal]:
    """Führt XPath-Abfrage aus und gibt den Inhalt als Decimal zurück."""
    # Wir rufen xp_text auf, aber setzen mandatory=False temporär, um den Wert für die Fehlermeldung zu erhalten
    text = xp_text(element, query, nsmap, mandatory=False)
    
    if text:
        try:
            return Decimal(text)
        except InvalidOperation:
            raise MappingError(f"Ungültiger numerischer Wert '{text}' bei XPath: {query}")
            
    if mandatory:
        raise MappingError(f"Pflichtfeld (Decimal) fehlt oder ist leer bei XPath: {query}")
        
    return default