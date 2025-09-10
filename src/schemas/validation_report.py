"""
Pydantic Modelle für Validierungsberichte
Strukturierte Darstellung aller Validierungsergebnisse
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class ValidationSeverity(str, Enum):
    """Schweregrad von Validierungsfehlern"""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    FATAL = "FATAL"


class ValidationCategory(str, Enum):
    """Kategorien von Validierungsfehlern"""
    STRUCTURE = "STRUCTURE"      # XSD Schema Fehler
    SEMANTIC = "SEMANTIC"        # Schematron/Business Rules
    CALCULATION = "CALCULATION"  # Mathematische Fehler
    COMPLIANCE = "COMPLIANCE"    # Rechtliche Anforderungen (§14 UStG)
    BUSINESS = "BUSINESS"        # ERP Integration Fehler
    TECHNICAL = "TECHNICAL"      # Systemfehler


class ValidationError(BaseModel):
    """Einzelner Validierungsfehler"""
    category: ValidationCategory
    severity: ValidationSeverity
    code: Optional[str] = None          # z.B. "BR-DE-15" (KoSIT Regel)
    message: str
    description: Optional[str] = None    # Detaillierte Erklärung
    location: Optional[str] = None       # XPath oder Zeilennummer
    expected_value: Optional[str] = None
    actual_value: Optional[str] = None
    suggestion: Optional[str] = None     # Lösungsvorschlag
    
    model_config = ConfigDict(
        json_schema_extra = {
            "example": {
                "category": "SEMANTIC",
                "severity": "ERROR",
                "code": "BR-DE-15",
                "message": "Invoice total amount does not match sum of line amounts",
                "description": "The total invoice amount (119.00 EUR) does not equal the sum of all line net amounts plus tax (120.00 EUR)",
                "location": "/ubl:Invoice/cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount",
                "expected_value": "120.00",
                "actual_value": "119.00",
                "suggestion": "Correct the total amount or review individual line calculations"
            }
        }
    )


class ValidationStep(BaseModel):
    """Einzelner Validierungsschritt"""
    step_name: str
    step_description: Optional[str] = None
    status: str = Field(..., pattern="^(SUCCESS|FAILED|SKIPPED|WARNING)$")
    duration_seconds: Optional[float] = None
    errors: List[ValidationError] = Field(default_factory=list)
    warnings: List[ValidationError] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None  # Zusätzliche Informationen
    
    def has_errors(self) -> bool:
        """Hat dieser Schritt Fehler?"""
        return len(self.errors) > 0
    
    def has_warnings(self) -> bool:
        """Hat dieser Schritt Warnungen?"""
        return len(self.warnings) > 0
    
    def is_successful(self) -> bool:
        """War dieser Schritt erfolgreich?"""
        return self.status == "SUCCESS" and not self.has_errors()


class ValidationSummary(BaseModel):
    """Zusammenfassung der Validierung"""
    total_errors: int = 0
    total_warnings: int = 0
    fatal_errors: int = 0
    
    # Aufschlüsselung nach Kategorien
    structure_errors: int = 0
    semantic_errors: int = 0
    calculation_errors: int = 0
    compliance_errors: int = 0
    business_errors: int = 0
    technical_errors: int = 0
    
    # Status
    is_valid: bool = False
    highest_level_reached: str = "NONE"  # STRUCTURE, SEMANTIC, CALCULATION, BUSINESS, COMPLIANCE
    
    def update_from_errors(self, errors: List[ValidationError]):
        """Aktualisiere Statistiken basierend auf Fehlerliste"""
        self.total_errors = len([e for e in errors if e.severity in ['ERROR', 'FATAL']])
        self.total_warnings = len([e for e in errors if e.severity == 'WARNING'])
        self.fatal_errors = len([e for e in errors if e.severity == 'FATAL'])
        
        # Kategorien zählen
        for error in errors:
            if error.severity in ['ERROR', 'FATAL']:
                if error.category == ValidationCategory.STRUCTURE:
                    self.structure_errors += 1
                elif error.category == ValidationCategory.SEMANTIC:
                    self.semantic_errors += 1
                elif error.category == ValidationCategory.CALCULATION:
                    self.calculation_errors += 1
                elif error.category == ValidationCategory.COMPLIANCE:
                    self.compliance_errors += 1
                elif error.category == ValidationCategory.BUSINESS:
                    self.business_errors += 1
                elif error.category == ValidationCategory.TECHNICAL:
                    self.technical_errors += 1
        
        # Gültigkeitsstatus
        self.is_valid = self.total_errors == 0 and self.fatal_errors == 0


class ValidationReport(BaseModel):
    """Vollständiger Validierungsbericht"""
    
    # Metadaten
    transaction_id: str
    invoice_number: Optional[str] = None
    validation_timestamp: datetime = Field(default_factory=datetime.now)
    validator_version: str = "1.0.0"
    
    # Format-Informationen
    detected_format: Optional[str] = None
    format_version: Optional[str] = None
    
    # Validierungsschritte (in chronologischer Reihenfolge)
    steps: List[ValidationStep] = Field(default_factory=list)
    
    # Zusammenfassung
    summary: ValidationSummary = Field(default_factory=ValidationSummary)
    
    # Performance-Metriken
    total_duration_seconds: Optional[float] = None
    
    # Zusätzliche Metadaten
    metadata: Optional[Dict[str, Any]] = None
    
    def add_step(self, step: ValidationStep):
        """Füge Validierungsschritt hinzu"""
        self.steps.append(step)
        self._update_summary()
    
    def _update_summary(self):
        """Aktualisiere Zusammenfassung basierend auf allen Schritten"""
        all_errors = []
        all_warnings = []
        
        for step in self.steps:
            all_errors.extend(step.errors)
            all_warnings.extend(step.warnings)
        
        self.summary.update_from_errors(all_errors + all_warnings)
        
        # Bestimme höchstes erreichtes Level
        if any(step.step_name == "compliance_check" and step.is_successful() for step in self.steps):
            self.summary.highest_level_reached = "COMPLIANCE"
        elif any(step.step_name == "business_validation" and step.is_successful() for step in self.steps):
            self.summary.highest_level_reached = "BUSINESS"
        elif any(step.step_name == "calculation_validation" and step.is_successful() for step in self.steps):
            self.summary.highest_level_reached = "CALCULATION"
        elif any(step.step_name == "semantic_validation" and step.is_successful() for step in self.steps):
            self.summary.highest_level_reached = "SEMANTIC"
        elif any(step.step_name == "structure_validation" and step.is_successful() for step in self.steps):
            self.summary.highest_level_reached = "STRUCTURE"
    
    def get_all_errors(self) -> List[ValidationError]:
        """Alle Fehler aus allen Schritten"""
        errors = []
        for step in self.steps:
            errors.extend(step.errors)
        return errors
    
    def get_all_warnings(self) -> List[ValidationError]:
        """Alle Warnungen aus allen Schritten"""
        warnings = []
        for step in self.steps:
            warnings.extend(step.warnings)
        return warnings
    
    def get_errors_by_category(self, category: ValidationCategory) -> List[ValidationError]:
        """Fehler einer bestimmten Kategorie"""
        return [error for error in self.get_all_errors() if error.category == category]
    
    def is_valid(self) -> bool:
        """Ist die Rechnung insgesamt gültig?"""
        return self.summary.is_valid
    
    def has_fatal_errors(self) -> bool:
        """Hat die Validierung fatale Fehler?"""
        return self.summary.fatal_errors > 0
    
    def to_json_summary(self) -> dict:
        """Kompakte JSON-Darstellung für API"""
        return {
            "transaction_id": self.transaction_id,
            "invoice_number": self.invoice_number,
            "is_valid": self.is_valid(),
            "total_errors": self.summary.total_errors,
            "total_warnings": self.summary.total_warnings,
            "highest_level_reached": self.summary.highest_level_reached,
            "validation_timestamp": self.validation_timestamp.isoformat(),
            "duration_seconds": self.total_duration_seconds
        }
    
    class ConfigDict:
        json_schema_extra = {
            "example": {
                "transaction_id": "550e8400-e29b-41d4-a716-446655440000",
                "invoice_number": "R2024-001",
                "detected_format": "XRECHNUNG_UBL",
                "format_version": "2.3.1",
                "summary": {
                    "is_valid": False,
                    "total_errors": 2,
                    "total_warnings": 1,
                    "highest_level_reached": "SEMANTIC"
                }
            }
        }
