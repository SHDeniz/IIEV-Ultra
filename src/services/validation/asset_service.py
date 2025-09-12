# src/services/validation/asset_service.py (Vollständig aktualisiert)
import logging
from pathlib import Path
from typing import Optional
from lxml import etree
from io import BytesIO
from ...db.models import InvoiceFormat

logger = logging.getLogger(__name__)

# Definiere das Basisverzeichnis der Assets.
try:
    # Navigiert vom src/services/validation/ zum Projekt-Root
    BASE_ASSET_DIR = Path(__file__).resolve().parents[3] / "assets" / "validation"
except IndexError:
    # Fallback für Umgebungen (z.B. Tests)
    BASE_ASSET_DIR = Path("assets/validation")

class AssetService:
    """
    Verwaltet den Zugriff auf Validierungs-Assets. Findet Assets dynamisch und robust.
    """
    def __init__(self, base_dir: Path = BASE_ASSET_DIR):
        self.base_dir = base_dir
        
        # Pfade initialisieren
        self.kosit_jar_path: Optional[Path] = None
        self.kosit_config_base = base_dir / "kosit" / "configuration"
        self.kosit_scenarios_path: Optional[Path] = None
        
        self.xsd_ubl_invoice: Optional[Path] = None
        self.xsd_ubl_creditnote: Optional[Path] = None
        self.xsd_cii: Optional[Path] = None

        # --- Asset Discovery ---
        self._find_kosit_assets()
        self._find_schemas() # Aktualisiert, um UBL in KoSIT zu priorisieren
        self._log_asset_status()

    def _find_kosit_assets(self):
        """Sucht dynamisch nach dem KoSIT Validator JAR und der Konfiguration."""
        kosit_dir = self.base_dir / "kosit"
        
        # 1. Finde JAR
        if kosit_dir.exists():
            jars = list(kosit_dir.glob("validator-*-standalone.jar"))
            if jars:
                self.kosit_jar_path = jars[0]

        # 2. Finde scenarios.xml
        if self.kosit_config_base.exists():
            scenarios = list(self.kosit_config_base.rglob("scenarios.xml"))
            if scenarios:
                 self.kosit_scenarios_path = scenarios[0]

    def _find_schemas(self):
        """Findet XSD Schemas für UBL und CII. Priorisiert die KoSIT Konfiguration für UBL."""
        
        # 1. UBL Schemas (NEU: Suche primär in KoSIT Konfiguration)
        # Wir nutzen die rekursive Suche _find_ubl_maindoc auf dem KoSIT Config Base Pfad.
        ubl_maindoc = self._find_ubl_maindoc(self.kosit_config_base)
        
        if ubl_maindoc:
            logger.info("Verwende UBL Schemas aus KoSIT Konfigurationspaket.")
        else:
            # Fallback auf das standalone UBL Verzeichnis (falls das Setup-Skript die separate UBL ZIP genutzt hat)
            logger.info("UBL Schemas nicht in KoSIT Konfiguration gefunden. Fallback auf standalone UBL Verzeichnis (assets/validation/xsd/ubl_2_1).")
            ubl_maindoc = self._find_ubl_maindoc(self.base_dir / "xsd" / "ubl_2_1")
        
        if ubl_maindoc:
            self.xsd_ubl_invoice = ubl_maindoc / "UBL-Invoice-2.1.xsd"
            self.xsd_ubl_creditnote = ubl_maindoc / "UBL-CreditNote-2.1.xsd"

        # 2. CII Schema (Verwende das robuste Suchverfahren)
        self.xsd_cii = self._find_cii_main_xsd(self.base_dir / "xsd" / "cii_d16b")

    def _find_ubl_maindoc(self, search_dir: Path) -> Optional[Path]:
        """Findet das maindoc Verzeichnis innerhalb einer UBL Struktur (rekursiv)."""
        if not search_dir.exists():
            return None
        # Suche rekursiv (rglob) nach dem 'maindoc' Ordner
        maindocs = list(search_dir.rglob("maindoc"))
        if maindocs:
            # Filter zur Sicherstellung, dass es das korrekte UBL maindoc ist
            for doc_path in maindocs:
                if (doc_path / "UBL-Invoice-2.1.xsd").exists():
                    return doc_path
        return None

    def _find_cii_main_xsd(self, cii_base_dir: Path) -> Optional[Path]:
        """
        Findet das Haupt-XSD für CII im UNECE Paket ('uncoupled' Version).
        """
        if not cii_base_dir.exists():
            return None

        main_xsd_name = "CrossIndustryInvoice_100pD16B.xsd"
        
        # Basierend auf der Analyse, kann der Pfad sehr spezifisch sein:
        # D16B SCRDM (Subset) CII uncoupled/uncoupled clm/CII/uncefact/data/standard/
        specific_path = cii_base_dir / "D16B SCRDM (Subset) CII uncoupled" / "uncoupled clm" / "CII" / "uncefact" / "data" / "standard" / main_xsd_name
        if specific_path.exists():
            return specific_path

        # Fallback auf das vorherige robuste Suchverfahren, falls die Struktur leicht abweicht
        
        preferred_relative_path = Path("uncoupled") / "data" / "standard" / main_xsd_name
        
        # Check Scenario A: Direkter Pfad
        if (cii_base_dir / preferred_relative_path).exists():
            return cii_base_dir / preferred_relative_path

        # Check Scenario B: Mit Root-Ordner
        if cii_base_dir.is_dir():
            for subdir in cii_base_dir.iterdir():
                if subdir.is_dir() and (subdir / preferred_relative_path).exists():
                    return subdir / preferred_relative_path
        
        # Fallback: Rekursive Suche (rglob)
        files = list(cii_base_dir.rglob(main_xsd_name))
        if files:
            uncoupled_files = [f for f in files if 'uncoupled' in [p.lower() for p in f.parts]]
            if uncoupled_files:
                return uncoupled_files[0]
            return files[0]
            
        return None

    def _log_asset_status(self):
        """Prüft die Verfügbarkeit der Assets und protokolliert Warnungen, falls sie fehlen."""
        # (Logik bleibt unverändert)
        if not self.base_dir.exists():
            logger.warning(f"Basisverzeichnis für Assets nicht gefunden: {self.base_dir}.")
            return

        if not self.kosit_jar_path:
            logger.warning(f"KoSIT Validator JAR nicht gefunden.")
        if not self.kosit_scenarios_path:
            logger.warning(f"KoSIT Scenarios XML nicht gefunden.")
        
        if not self.xsd_cii or not self.xsd_cii.exists():
            logger.warning(f"CII XSD (CrossIndustryInvoice_100pD16B.xsd) nicht gefunden.")
            
        if not self.xsd_ubl_invoice or not self.xsd_ubl_invoice.exists():
            logger.warning(f"UBL Invoice XSD nicht gefunden.")

    def get_xsd_path(self, format: InvoiceFormat, xml_bytes: bytes) -> Optional[Path]:
        """
        Gibt den Pfad zum Haupt-XSD-Schema zurück.
        """
        path = None
        
        if format in [InvoiceFormat.XRECHNUNG_CII, InvoiceFormat.ZUGFERD_CII, InvoiceFormat.FACTURX_CII]:
            path = self.xsd_cii
            
        elif format == InvoiceFormat.XRECHNUNG_UBL:
            doc_type = self._get_ubl_document_type(xml_bytes)
            if doc_type == 'CreditNote':
                path = self.xsd_ubl_creditnote
            else:
                path = self.xsd_ubl_invoice

        if path and path.exists():
            return path
        elif path:
            logger.error(f"XSD Schema physisch nicht gefunden unter dem erwarteten Pfad: {path}")
            return None
        return None

    def _get_ubl_document_type(self, xml_bytes: bytes) -> str:
        """Ermittelt schnell den Dokumententyp (Invoice/CreditNote) aus UBL XML."""
        try:
            parser = etree.XMLParser(resolve_entities=False)
            context = etree.iterparse(BytesIO(xml_bytes), events=("start",), tag="*", parser=parser)
            _, root = next(context)
            return etree.QName(root.tag).localname
        except Exception:
            return "Invoice"

# Singleton Instanz (Wird neu initialisiert, um die Änderungen zu übernehmen)
asset_service = AssetService()