# scripts/setup_validation_assets.py (Vollständig aktualisiert)
import requests
import zipfile
import io
import logging
import shutil
from pathlib import Path
from typing import Optional

# Konfiguriere Logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Definiere das Zielverzeichnis
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSET_DIR = PROJECT_ROOT / "assets" / "validation"
MANUAL_DOWNLOAD_DIR = PROJECT_ROOT / "manual_downloads" # Verzeichnis für manuelle Downloads

# URLs der benötigten Assets (Aktualisiert Stand 2024/2025)

# XSD Schemas
# CII D16B von UNECE (Oft durch Bots blockiert)
URL_CII_D16B = "https://unece.org/fileadmin/DAM/cefact/xml_schemas/D16B.zip"
CII_D16B_PATTERN = "D16B*.zip" # Pattern für die manuelle Suche

# UBL 2.1 von OASIS
URL_UBL_2_1 = "http://docs.oasis-open.org/ubl/os-UBL-2.1/UBL-2.1.zip"

# KoSIT Assets
# Validator Tool v1.5.2
URL_KOSIT_VALIDATOR = "https://github.com/itplr-kosit/validator/releases/download/v1.5.2/validator-1.5.2.zip"

# XRechnung Configuration (Release 2025-07-10 für XRechnung 3.0.2)
URL_KOSIT_XRECHNUNG_CONFIG = "https://github.com/itplr-kosit/validator-configuration-xrechnung/releases/download/release-2025-07-10/validator-configuration-xrechnung_3.0.2_2025-07-10.zip"

# Standard User-Agent, falls automatischer Download versucht wird
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36'
}

def download_file(url: str, target_path: Path, skip_if_exists: bool = True):
    """Lädt eine einzelne Datei herunter (z.B. JAR)."""
    if skip_if_exists and target_path.exists():
        logging.info(f"Datei existiert bereits: {target_path.name}. Überspringe Download.")
        return

    logging.info(f"Lade herunter: {url.split('/')[-1]}")
    try:
        response = requests.get(url, stream=True, headers=HEADERS)
        response.raise_for_status()

        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        logging.info(f"✅ Erfolgreich gespeichert unter: {target_path.name}")

    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Fehler beim Download: {e}")

def download_and_extract_zip(url: str, extract_to: Path, manual_pattern: Optional[str] = None, skip_if_exists: bool = True):
    """Lädt eine ZIP-Datei herunter (priorisiert manuelle Downloads) und entpackt sie."""
    if skip_if_exists and extract_to.exists() and any(extract_to.iterdir()):
        logging.info(f"Zielverzeichnis existiert bereits: {extract_to.name}. Überspringe.")
        return

    zip_data = None

    # 1. Priorisiere manuellen Download
    if manual_pattern and MANUAL_DOWNLOAD_DIR.exists():
        # Suche nach passenden Dateien im manuellen Verzeichnis
        manual_files = list(MANUAL_DOWNLOAD_DIR.glob(manual_pattern))
        if manual_files:
            manual_file = manual_files[0]
            logging.info(f"✅ Verwende manuell heruntergeladene Datei: {manual_file.name}")
            try:
                with open(manual_file, 'rb') as f:
                    zip_data = f.read()
            except IOError as e:
                logging.error(f"❌ Fehler beim Lesen der manuellen Datei: {e}")
                return

    # 2. Fallback auf automatischen Download
    if zip_data is None:
        logging.info(f"Starte automatischen Download von: {url.split('/')[-1]}")
        try:
            response = requests.get(url, stream=True, headers=HEADERS)
            response.raise_for_status()
            zip_data = response.content
        except requests.exceptions.RequestException as e:
            logging.error(f"❌ Fehler beim automatischen Download: {e}")
            if manual_pattern:
                # Wenn automatischer Download fehlschlägt und manueller Fallback konfiguriert war, aber nicht gefunden wurde.
                logging.warning(f"⚠️ Bitte laden Sie die Datei manuell von {url} herunter und legen Sie sie in {MANUAL_DOWNLOAD_DIR} ab.")
            return

    # 3. Entpacken
    if zip_data:
        logging.info(f"Entpacke nach: {extract_to.name}")
        extract_to.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
                z.extractall(path=extract_to)
            logging.info("✅ Erfolgreich entpackt.")
        except zipfile.BadZipFile:
            logging.error(f"❌ Datei ist keine gültige ZIP-Datei.")

def setup_schemas():
    """Richtet die XSD Schemas ein."""
    logging.info("--- Setup XSD Schemas (UBL & CII) ---")
    
    # 1. CII D16B (Mit manuellem Fallback)
    download_and_extract_zip(
        URL_CII_D16B, 
        ASSET_DIR / "xsd" / "cii_d16b",
        manual_pattern=CII_D16B_PATTERN
    )
    
    # 2. UBL 2.1 (Automatischer Download und Reorganisation)
    ubl_temp_dir = ASSET_DIR / "xsd" / "ubl_2_1_temp"
    ubl_target_dir = ASSET_DIR / "xsd" / "ubl_2_1"
    
    if ubl_target_dir.exists() and any(ubl_target_dir.iterdir()):
         logging.info(f"Zielverzeichnis existiert bereits: {ubl_target_dir.name}. Überspringe UBL Download.")
         return

    download_and_extract_zip(URL_UBL_2_1, ubl_temp_dir, skip_if_exists=False)
    
    # Reorganisiere UBL Struktur
    if ubl_temp_dir.exists():
        try:
            # Finde das Quellverzeichnis (z.B. os-UBL-2.1)
            source_dir = next((d for d in ubl_temp_dir.iterdir() if d.is_dir()), None)
            if source_dir:
                # Benenne das Quellverzeichnis in das Zielverzeichnis um
                if ubl_target_dir.exists():
                    shutil.rmtree(ubl_target_dir) # Sicherstellen, dass Ziel leer ist
                source_dir.rename(ubl_target_dir)
                logging.info(f"UBL Verzeichnis reorganisiert nach: {ubl_target_dir.name}")
            
            # Aufräumen
            if ubl_temp_dir.exists():
                 shutil.rmtree(ubl_temp_dir)
        except (StopIteration, OSError) as e:
            logging.error(f"❌ Fehler bei der Reorganisation des UBL Verzeichnisses: {e}")

def setup_kosit():
    """Richtet das KoSIT Prüftool und die Konfiguration ein."""
    logging.info("--- Setup KoSIT Validator & Konfiguration ---")
    kosit_dir = ASSET_DIR / "kosit"
    
    # 1. Validator (Das Tool selbst)
    validator_temp_dir = kosit_dir / "validator_temp"
    download_and_extract_zip(URL_KOSIT_VALIDATOR, validator_temp_dir, skip_if_exists=False)
    
    # Finde das JAR im entpackten Verzeichnis und verschiebe es ins kosit/ Hauptverzeichnis
    if validator_temp_dir.exists():
        # Suche nach dem Validator JAR mit dem exakten Muster 'validator-<version>-standalone.jar'
        # Das Versionsmuster besteht typischerweise aus Ziffern und Punkten, z.B. 1.5.2
        import re
        jars = [
            p for p in validator_temp_dir.iterdir()
            if p.is_file() and re.fullmatch(r"validator-\d+\.\d+\.\d+-standalone\.jar", p.name)
        ]
        if jars:
            jar_path = jars[0]
            target_path = kosit_dir / jar_path.name
            if not target_path.exists():
                jar_path.rename(target_path)
                logging.info(f"JAR verschoben nach: {target_path.name}")
            # Aufräumen
            shutil.rmtree(validator_temp_dir)
        else:
            logging.error("Kein CLI JAR im Validator Download gefunden.")

    # 2. Konfiguration (Die Regeln)
    download_and_extract_zip(URL_KOSIT_XRECHNUNG_CONFIG, kosit_dir / "configuration")


if __name__ == "__main__":
    logging.info("🚀 Starte Setup der Validierungs-Assets...")
    # Stelle sicher, dass die Verzeichnisse existieren
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    MANUAL_DOWNLOAD_DIR.mkdir(exist_ok=True)
    
    setup_schemas()
    setup_kosit()
    logging.info("🏁 Setup abgeschlossen.")