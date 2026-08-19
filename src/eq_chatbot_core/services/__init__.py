"""
Core services for chatbot operations.

- DocumentExtractor: Office documents to Markdown (knowledge ingestion)
- ErrorHandler: Provider error handling with fallbacks
- KnowledgeService: Odoo data export to vector databases
"""

from eq_chatbot_core.services.document_extractor import (
    ExtractionResult,
    extract_markdown,
    is_document_extraction_available,
    supported_extensions,
)
from eq_chatbot_core.services.error_handler import ChatbotErrorHandler
from eq_chatbot_core.services.knowledge_service import (
    ExportRecord,
    FieldConfig,
    KnowledgeExporter,
    ModelConfig,
    OdooSchemaGenerator,
    RecordTransformer,
)

__all__ = [
    "ChatbotErrorHandler",
    # Document Extraction
    "ExtractionResult",
    "extract_markdown",
    "is_document_extraction_available",
    "supported_extensions",
    # Knowledge Export
    "FieldConfig",
    "ModelConfig",
    "ExportRecord",
    "OdooSchemaGenerator",
    "RecordTransformer",
    "KnowledgeExporter",
]
