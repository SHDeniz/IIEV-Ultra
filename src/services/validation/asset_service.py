# src/services/validation/asset_service.py
import logging
from pathlib import Path
from typing import Optional
from lxml import etree
from io import BytesIO
from ...db.models import InvoiceFormat

logger = logging.getLogger(__name__)

# Definiere das Basisverzeichnis der Assets. 
# Wir verwenden Path(__file__).resolve().parents[3], um vom src/services/validation/ zum Projekt-Root zu navigieren.
try:
    BASE_ASSET_DIR = Path(__file__).resolve().parents[3] / "assets" / "validation"
except IndexError:
    # Fallback für Umgebungen, in denen die relative Pfadbestimmung schwierig ist (z.B. manche Testrunner)
    BASE_ASSET_DIR = Path("assets/validation")

class AssetService:
    """
    Verwaltet den Zugriff auf Validierungs-Assets (XSD, Schematron, KoSIT JAR).
    """
    def __init__(self, base_dir: Path = BASE_ASSET_DIR):
        self.base_dir = base_dir
        
        # KoSIT Pfade
        # Annahme: Das JAR liegt direkt im kosit/ Verzeichnis oder wird dynamisch gefunden.
        self.kosit_jar_path: Optional[Path] = None
        self.kosit_scenarios_path = base_dir / "kosit" / "configuration" / "scenarios.xml"
        
        # XSD Pfade
        self.xsd_cii = base_dir / "xsd" / "cii" / "CrossIndustryInvoice_13p1.xsd"
        self.xsd_ubl_invoice = base_dir / "xsd" / "ubl" / "UBL-Invoice-2.1.xsd"
        self.xsd_ubl_creditnote = base_dir / "xsd" / "ubl" / "UBL-CreditNote-2.1.xsd"

        self._find_kosit_jar()
        self._log_asset_status()

    def _find_kosit_jar(self):
        """Sucht dynamisch nach dem KoSIT Validator JAR."""
        kosit_dir = self.base_dir / "kosit"
        if kosit_dir.exists():
            jars = list(kosit_dir.glob("*.jar"))
            if jars:
                self.kosit_jar_path = jars[0]

    def _log_asset_status(self):
        if not self.kosit_jar_path:
            logger.error(f"KoSIT Validator JAR nicht gefunden im Verzeichnis: {self.base_dir / 'kosit'}")
        if not self.kosit_scenarios_path.exists():
            logger.error(f"KoSIT Scenarios XML nicht gefunden: {self.kosit_scenarios_path}")

    def get_xsd_path(self, format: InvoiceFormat, xml_bytes: bytes) -> Optional[Path]:
        """
        Gibt den Pfad zum Haupt-XSD-Schema zurück. Berücksichtigt UBL Invoice vs. CreditNote.
        """
        path = None
        
        if format in [InvoiceFormat.XRECHNUNG_CII, InvoiceFormat.ZUGFERD_CII, InvoiceFormat.FACTURX_CII]:
            path = self.xsd_cii
            
        elif format == InvoiceFormat.XRECHNUNG_UBL:
            # Unterscheide zwischen Invoice und CreditNote durch Analyse des XML Root Elements
            doc_type = self._get_ubl_document_type(xml_bytes)
            if doc_type == 'CreditNote':
                path = self.xsd_ubl_creditnote
            else:
                # Default zu Invoice
                path = self.xsd_ubl_invoice

        if path and path.exists():
            return path
        elif path:
            logger.error(f"XSD Schema nicht gefunden unter: {path}")
            return None
        return None

    def _get_ubl_document_type(self, xml_bytes: bytes) -> str:
        """Ermittelt schnell den Dokumententyp (Invoice/CreditNote) aus UBL XML."""
        try:
            # Nutze iterparse für effizienten Zugriff auf das Root-Element
            context = etree.iterparse(BytesIO(xml_bytes), events=("start",), tag="*")
            _, root = next(context)
            # Gebe den lokalen Namen des Root-Tags zurück (z.B. 'Invoice' oder 'CreditNote')
            return etree.QName(root.tag).localname
        except Exception:
            # Fallback, wenn Parsing fehlschlägt
            return "Invoice"

# Singleton Instanz
asset_service = AssetService()