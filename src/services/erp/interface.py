from abc import ABC, abstractmethod
from typing import Optional, Dict, List
from decimal import Decimal
from pydantic import BaseModel

# --- Datenstrukturen für ERP Antworten ---

class ERPVendor(BaseModel):
    """Repräsentiert einen Kreditor aus dem ERP."""
    vendor_id: str
    vat_id: Optional[str]
    is_active: bool

class ERPBankDetails(BaseModel):
    """Repräsentiert eine validierte Bankverbindung aus dem ERP."""
    iban: str

class ERPPurchaseOrderLine(BaseModel):
    """Repräsentiert eine Bestellposition im ERP für den Abgleich."""
    han_ean_gtin: str
    quantity_ordered: Decimal
    quantity_invoiced: Decimal

    @property
    def quantity_open(self) -> Decimal:
        return self.quantity_ordered - self.quantity_invoiced

class ERPPurchaseOrder(BaseModel):
    """Repräsentiert die Bestellung (Kopf und Positionen) aus dem ERP."""
    po_number: str
    vendor_id: str
    total_net_amount: Decimal
    is_open_for_invoicing: bool
    # Dictionary keyed by HAN/EAN/GTIN für schnellen Zugriff beim Abgleich
    lines: Dict[str, ERPPurchaseOrderLine] 

# --- Das Adapter Interface ---

class IERPAdapter(ABC):
    """
    Interface Definition für ERP Interaktionen.
    """

    @abstractmethod
    def find_vendor_by_vat_id(self, vat_id: str) -> Optional[ERPVendor]:
        """Sucht einen Kreditor anhand der USt-IdNr."""
        pass

    @abstractmethod
    def is_duplicate_invoice(self, vendor_id: str, invoice_number: str) -> bool:
        """Prüft, ob die Rechnungsnummer bereits existiert."""
        pass

    @abstractmethod
    def get_vendor_bank_details(self, vendor_id: str) -> List[ERPBankDetails]:
        """Ruft die hinterlegten Bankverbindungen ab."""
        pass

    @abstractmethod
    def get_purchase_order_details(self, po_number: str, vendor_id: str) -> Optional[ERPPurchaseOrder]:
        """
        Ruft Details einer Bestellung ab (inkl. Positionen) und prüft die Zugehörigkeit zum Kreditor.
        """
        pass