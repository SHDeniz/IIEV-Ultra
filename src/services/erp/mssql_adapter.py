import logging
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

# Importiere das Interface und die Datenstrukturen
from .interface import IERPAdapter, ERPVendor, ERPBankDetails, ERPPurchaseOrder, ERPPurchaseOrderLine

logger = logging.getLogger(__name__)

class MSSQL_ERPAdapter(IERPAdapter):
    """
    Konkrete Implementierung für Azure MSSQL ERP Systeme.
    Nutzt SQLAlchemy Textual SQL für Read-Only Zugriff.
    """
    
    def __init__(self, db_session: Session):
        # Der Adapter arbeitet innerhalb einer bestehenden Session.
        self.db = db_session

    # --------------------------------------------------------------------
    # 4.1 Kreditor-Lookup
    # --------------------------------------------------------------------
    def find_vendor_by_vat_id(self, vat_id: str) -> Optional[ERPVendor]:
        if not vat_id:
            return None
            
        # ANNAHME SCHEMA: dbo.KreditorenStamm
        # SICHERHEIT: Parameterisierte Abfragen verhindern SQL-Injection.
        query = text("""
            SELECT KreditorID, UStIdNr, Status
            FROM dbo.KreditorenStamm
            WHERE UStIdNr = :vat_id
        """)
        
        try:
            result = self.db.execute(query, {"vat_id": vat_id}).fetchone()
            
            if result:
                return ERPVendor(
                    vendor_id=result.KreditorID,
                    vat_id=result.UStIdNr,
                    # ANNAHME: Status 'Aktiv' bedeutet aktiv
                    is_active=(result.Status == 'Aktiv')
                )
            return None
        except SQLAlchemyError as e:
            logger.error(f"Datenbankfehler beim Kreditor-Lookup für USt-IdNr. {vat_id}: {e}")
            # Werfe Exception, damit Celery Retry Mechanismus greift (bei transienten Fehlern)
            raise

    # --------------------------------------------------------------------
    # 4.2 Dublettenprüfung
    # --------------------------------------------------------------------
    def is_duplicate_invoice(self, vendor_id: str, invoice_number: str) -> bool:
        # ANNAHME SCHEMA: dbo.RechnungsJournal
        query = text("""
            SELECT COUNT(*)
            FROM dbo.RechnungsJournal
            WHERE KreditorID = :vendor_id AND ExterneRechnungsNr = :invoice_number
        """)
        
        try:
            count = self.db.execute(query, {
                "vendor_id": vendor_id, 
                "invoice_number": invoice_number
            }).scalar()
            return count > 0
        except SQLAlchemyError as e:
            logger.error(f"Datenbankfehler bei Dublettenprüfung für {invoice_number}: {e}")
            raise

    # --------------------------------------------------------------------
    # 4.3 Bankdaten-Validierung
    # --------------------------------------------------------------------
    def get_vendor_bank_details(self, vendor_id: str) -> List[ERPBankDetails]:
        # ANNAHME SCHEMA: dbo.KreditorenBanken
        query = text("""
            SELECT IBAN
            FROM dbo.KreditorenBanken
            WHERE KreditorID = :vendor_id
        """)
        
        try:
            results = self.db.execute(query, {"vendor_id": vendor_id}).fetchall()
            return [ERPBankDetails(iban=row.IBAN) for row in results if row.IBAN]
        except SQLAlchemyError as e:
            logger.error(f"Datenbankfehler beim Abruf der Bankdaten für {vendor_id}: {e}")
            raise

    # --------------------------------------------------------------------
    # 4.4 & 4.5 Bestellabgleich (Header und Positionen)
    # --------------------------------------------------------------------
    def get_purchase_order_details(self, po_number: str, vendor_id: str) -> Optional[ERPPurchaseOrder]:
        if not po_number:
            return None

        # 1. Abruf Bestellkopf
        # ANNAHME SCHEMA: dbo.Bestellungen
        header_query = text("""
            SELECT BestellNr, KreditorID, GesamtbetragNetto, Status
            FROM dbo.Bestellungen
            WHERE BestellNr = :po_number
        """)
        
        try:
            header_result = self.db.execute(header_query, {"po_number": po_number}).fetchone()
            
            if not header_result:
                return None

            # Sicherheitsprüfung: Gehört die Bestellung zum Kreditor der Rechnung?
            if header_result.KreditorID != vendor_id:
                logger.warning(f"Bestellung {po_number} gefunden, gehört aber zu Kreditor {header_result.KreditorID}, nicht zu {vendor_id}.")
                return None # Behandle als ungültig

            # 2. Abruf Bestellpositionen
            # ANNAHME SCHEMA: dbo.BestellPositionen
            lines_query = text("""
                SELECT ArtikelHAN, MengeBestellt, MengeBerechnet
                FROM dbo.BestellPositionen
                WHERE BestellNr = :po_number
            """)
            
            lines_result = self.db.execute(lines_query, {"po_number": po_number}).fetchall()
            
            # Map Positionen in ein Dictionary (Key = HAN)
            lines_dict: Dict[str, ERPPurchaseOrderLine] = {}
            for row in lines_result:
                han = row.ArtikelHAN
                # Aggregation bei doppelten HANs in der Bestellung (falls vorkommt)
                if han in lines_dict:
                    lines_dict[han].quantity_ordered += row.MengeBestellt
                    lines_dict[han].quantity_invoiced += row.MengeBerechnet
                else:
                    lines_dict[han] = ERPPurchaseOrderLine(
                        han_ean_gtin=han,
                        quantity_ordered=row.MengeBestellt,
                        quantity_invoiced=row.MengeBerechnet
                    )

            # ANNAHME: Status 'Offen' oder 'Teilgeliefert' erlaubt Buchung
            is_open = header_result.Status in ['Offen', 'Teilgeliefert']

            return ERPPurchaseOrder(
                po_number=header_result.BestellNr,
                vendor_id=header_result.KreditorID,
                total_net_amount=header_result.GesamtbetragNetto,
                is_open_for_invoicing=is_open,
                lines=lines_dict
            )

        except SQLAlchemyError as e:
            logger.error(f"Datenbankfehler beim Abruf der Bestellung {po_number}: {e}")
            raise