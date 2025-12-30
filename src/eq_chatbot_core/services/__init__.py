"""
Core services for chatbot operations.

- ChatService: Main chat orchestration
- CostService: Token and cost tracking
- ErrorHandler: Provider error handling with fallbacks
- KnowledgeService: Odoo data export to vector databases
"""

from eq_chatbot_core.services.cost_service import calculate_cost, PRICING
from eq_chatbot_core.services.error_handler import ChatbotErrorHandler
from eq_chatbot_core.services.knowledge_service import (
    FieldConfig,
    ModelConfig,
    ExportRecord,
    OdooSchemaGenerator,
    RecordTransformer,
    KnowledgeExporter,
)

__all__ = [
    "calculate_cost",
    "PRICING",
    "ChatbotErrorHandler",
    # Knowledge Export
    "FieldConfig",
    "ModelConfig",
    "ExportRecord",
    "OdooSchemaGenerator",
    "RecordTransformer",
    "KnowledgeExporter",
]
