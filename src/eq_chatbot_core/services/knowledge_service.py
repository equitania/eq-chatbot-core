"""
Knowledge Export Service for Odoo data.

Provides schema generation, data transformation, and export orchestration
for vector databases (Qdrant) and LangDock Knowledge Folders.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterator
import json
import logging

logger = logging.getLogger(__name__)


class FieldType(Enum):
    """Odoo field types."""

    CHAR = "char"
    TEXT = "text"
    HTML = "html"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    SELECTION = "selection"
    MANY2ONE = "many2one"
    ONE2MANY = "one2many"
    MANY2MANY = "many2many"
    BINARY = "binary"
    MONETARY = "monetary"


@dataclass
class FieldConfig:
    """Configuration for a single field to export."""

    name: str
    """Technical field name."""

    label: str
    """Human-readable field label."""

    field_type: str
    """Odoo field type (char, text, many2one, etc.)."""

    relation: str | None = None
    """Related model for relational fields."""

    is_text_field: bool = False
    """Whether this field should be chunked (large text)."""


@dataclass
class ModelConfig:
    """Configuration for a model to export."""

    model_name: str
    """Technical model name (e.g., 'res.partner')."""

    model_label: str
    """Human-readable model name."""

    fields: list[FieldConfig]
    """Fields to export."""

    domain: str = "[]"
    """Domain filter as string."""


@dataclass
class ExportRecord:
    """A single record prepared for export."""

    id: int
    """Record ID in Odoo."""

    model: str
    """Model name."""

    content: str
    """Text content for embedding."""

    metadata: dict[str, Any]
    """Additional metadata."""


class OdooSchemaGenerator:
    """
    Generate documentation schemas from Odoo model configurations.

    Produces Markdown documentation for LLMs to understand
    the structure and relationships of exported data.
    """

    def generate_schema(self, model_configs: list[ModelConfig]) -> str:
        """
        Generate schema documentation in Markdown format.

        Args:
            model_configs: List of model configurations

        Returns:
            Markdown string describing all models and fields
        """
        lines = ["# Data Schema Documentation", ""]
        lines.append("This document describes the structure of the exported Odoo data.")
        lines.append("")

        for config in model_configs:
            lines.append(f"## Model: {config.model_name}")
            lines.append(f"**Description:** {config.model_label}")
            lines.append("")
            lines.append("### Fields")
            lines.append("")
            lines.append("| Field | Label | Type | Description |")
            lines.append("|-------|-------|------|-------------|")

            for field in config.fields:
                field_desc = self._get_field_description(field)
                lines.append(f"| `{field.name}` | {field.label} | {field.field_type} | {field_desc} |")

            lines.append("")

        return "\n".join(lines)

    def generate_relations(self, model_configs: list[ModelConfig]) -> str:
        """
        Generate relations documentation in Markdown format.

        Args:
            model_configs: List of model configurations

        Returns:
            Markdown string describing relationships between models
        """
        lines = ["# Data Relations Overview", ""]
        lines.append("This document describes the relationships between exported models.")
        lines.append("")

        for config in model_configs:
            relation_fields = [f for f in config.fields if f.field_type in ("many2one", "one2many", "many2many")]

            if not relation_fields:
                continue

            lines.append(f"## {config.model_name}")
            lines.append("")

            for field in relation_fields:
                rel_type = self._format_relation_type(field.field_type)
                lines.append(f"- **{field.name}** → `{field.relation}` ({rel_type})")

            lines.append("")

        # Add relationship diagram hint
        lines.append("## Relationship Types")
        lines.append("")
        lines.append("- **Many2One**: Single reference (foreign key)")
        lines.append("- **One2Many**: Multiple records referencing back")
        lines.append("- **Many2Many**: Multiple references in both directions")
        lines.append("")

        return "\n".join(lines)

    def generate_search_instructions(self, model_configs: list[ModelConfig]) -> str:
        """
        Generate search instructions for LLMs.

        Args:
            model_configs: List of model configurations

        Returns:
            Markdown string with search instructions
        """
        model_names = [c.model_name for c in model_configs]

        instructions = f"""# AI Search Instructions

## Overview
You have access to structured data from Odoo ERP containing the following models:
{', '.join(model_names)}

## How to Search

### 1. Understand the Schema
- Check the schema documentation for available fields
- Check relations documentation for model connections
- Identify which models contain the needed information

### 2. Query the Data
- Search the vector database for relevant chunks
- Use metadata filters to narrow results by model
- Combine results from multiple models when needed

### 3. Resolve Relationships
For relational fields (many2one, one2many, many2many):
- The stored value is the ID(s) of related records
- Load the related model to get full details
- Join data to provide complete answers

### 4. Handle Large Results
- Results are chunked for embedding efficiency
- Multiple chunks may belong to the same record
- Use the record ID in metadata to group related chunks

## Search Patterns

### Direct Search
Query: "Find customer XYZ"
1. Search res.partner for name containing "XYZ"
2. Return matching records with key fields

### Relationship Search
Query: "What orders does customer XYZ have?"
1. Find customer ID in res.partner
2. Search sale.order where partner_id = customer_id
3. Return order details

### Aggregation
Query: "How many customers per country?"
1. Load all res.partner records
2. Group by country_id
3. Count and resolve country names

## Available Models

{self._format_model_summary(model_configs)}
"""
        return instructions

    def _get_field_description(self, field: FieldConfig) -> str:
        """Get a description for a field based on its type."""
        if field.relation:
            return f"Reference to {field.relation}"
        if field.is_text_field:
            return "Large text content (chunked for embedding)"

        type_descriptions = {
            "char": "Short text",
            "text": "Long text",
            "html": "HTML content",
            "integer": "Whole number",
            "float": "Decimal number",
            "boolean": "True/False",
            "date": "Date value",
            "datetime": "Date and time",
            "selection": "Selection from options",
            "binary": "Binary data",
            "monetary": "Currency amount",
        }
        return type_descriptions.get(field.field_type, "Data field")

    def _format_relation_type(self, field_type: str) -> str:
        """Format relation type for display."""
        type_names = {
            "many2one": "Many2One",
            "one2many": "One2Many",
            "many2many": "Many2Many",
        }
        return type_names.get(field_type, field_type)

    def _format_model_summary(self, model_configs: list[ModelConfig]) -> str:
        """Format a summary of all models."""
        lines = []
        for config in model_configs:
            field_names = [f.name for f in config.fields]
            lines.append(f"### {config.model_name}")
            lines.append(f"- Label: {config.model_label}")
            lines.append(f"- Fields: {', '.join(field_names)}")
            lines.append("")
        return "\n".join(lines)


class RecordTransformer:
    """
    Transform Odoo records into exportable format.

    Handles different field types and prepares content for embedding.
    """

    def __init__(
        self,
        model_config: ModelConfig,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
    ):
        """
        Initialize transformer.

        Args:
            model_config: Configuration for the model
            chunk_size: Token size for chunks
            chunk_overlap: Overlap between chunks
        """
        self.config = model_config
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._chunker = None

    @property
    def chunker(self):
        """Lazy initialization of chunker."""
        if self._chunker is None:
            from eq_chatbot_core.rag.chunker import DocumentChunker

            self._chunker = DocumentChunker(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
            )
        return self._chunker

    def transform_record(
        self,
        record_id: int,
        field_values: dict[str, Any],
        display_values: dict[str, str] | None = None,
    ) -> Iterator[ExportRecord]:
        """
        Transform a single record into export format.

        Args:
            record_id: Odoo record ID
            field_values: Raw field values from Odoo
            display_values: Human-readable values for relations

        Yields:
            ExportRecord objects (may yield multiple if chunking large text)
        """
        if display_values is None:
            display_values = {}

        # Separate text fields that need chunking
        text_content_parts = []
        metadata_values = {"id": record_id, "model": self.config.model_name}

        for field in self.config.fields:
            value = field_values.get(field.name)
            display_value = display_values.get(field.name, str(value) if value else "")

            if field.is_text_field and value:
                # Large text field - will be chunked
                text_content_parts.append(f"## {field.label}\n{value}")
            elif field.field_type in ("many2one", "one2many", "many2many"):
                # Relational field - store both ID and display value
                metadata_values[field.name] = value
                if display_value:
                    metadata_values[f"{field.name}_display"] = display_value
            else:
                # Regular field
                metadata_values[field.name] = value

        # Build content string
        content_parts = [f"# {self.config.model_label}: Record {record_id}"]

        # Add summary fields
        summary_fields = [f for f in self.config.fields if not f.is_text_field and f.field_type not in ("binary",)]
        if summary_fields:
            content_parts.append("\n## Summary")
            for field in summary_fields:
                value = display_values.get(field.name, str(field_values.get(field.name, "")))
                if value:
                    content_parts.append(f"- **{field.label}**: {value}")

        # Add text content
        if text_content_parts:
            content_parts.extend(text_content_parts)

        full_content = "\n".join(content_parts)

        # Check if chunking is needed
        token_count = self.chunker.count_tokens(full_content)

        if token_count <= self.chunk_size:
            # Single record, no chunking needed
            yield ExportRecord(
                id=record_id,
                model=self.config.model_name,
                content=full_content,
                metadata=metadata_values,
            )
        else:
            # Chunk the content
            for chunk in self.chunker.chunk_text(full_content, metadata_values):
                yield ExportRecord(
                    id=record_id,
                    model=self.config.model_name,
                    content=chunk.content,
                    metadata={
                        **metadata_values,
                        "chunk_index": chunk.chunk_index,
                        "is_chunked": True,
                    },
                )

    def transform_records(
        self,
        records: list[dict[str, Any]],
    ) -> Iterator[ExportRecord]:
        """
        Transform multiple records.

        Args:
            records: List of record dictionaries with 'id', 'values', 'display_values'

        Yields:
            ExportRecord objects
        """
        for record in records:
            record_id = record["id"]
            field_values = record.get("values", {})
            display_values = record.get("display_values", {})

            yield from self.transform_record(record_id, field_values, display_values)


class KnowledgeExporter:
    """
    Orchestrate export to vector databases and LangDock.

    Coordinates schema generation, record transformation, and upload.
    """

    def __init__(
        self,
        model_configs: list[ModelConfig],
        chunk_size: int = 512,
        chunk_overlap: int = 64,
    ):
        """
        Initialize exporter.

        Args:
            model_configs: Configurations for models to export
            chunk_size: Token size for chunks
            chunk_overlap: Overlap between chunks
        """
        self.model_configs = model_configs
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.schema_generator = OdooSchemaGenerator()

    def generate_documentation(self) -> dict[str, str]:
        """
        Generate all documentation files.

        Returns:
            Dictionary with 'schema', 'relations', 'instructions' keys
        """
        return {
            "schema": self.schema_generator.generate_schema(self.model_configs),
            "relations": self.schema_generator.generate_relations(self.model_configs),
            "instructions": self.schema_generator.generate_search_instructions(self.model_configs),
        }

    def prepare_for_qdrant(
        self,
        records_by_model: dict[str, list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        """
        Prepare records for Qdrant upsert.

        Args:
            records_by_model: Records grouped by model name

        Returns:
            List of chunks ready for HybridRetriever.upsert()
        """
        chunks = []

        for config in self.model_configs:
            model_records = records_by_model.get(config.model_name, [])
            if not model_records:
                continue

            transformer = RecordTransformer(
                config,
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
            )

            for export_record in transformer.transform_records(model_records):
                chunks.append(
                    {
                        "content": export_record.content,
                        "metadata": export_record.metadata,
                        "source": f"odoo:{export_record.model}:{export_record.id}",
                    }
                )

        return chunks

    def prepare_for_langdock(
        self,
        records_by_model: dict[str, list[dict[str, Any]]],
    ) -> dict[str, str]:
        """
        Prepare files for LangDock Knowledge upload.

        Args:
            records_by_model: Records grouped by model name

        Returns:
            Dictionary of filename -> content for upload
        """
        files = {}

        # Add documentation files
        docs = self.generate_documentation()
        files["schema.md"] = docs["schema"]
        files["relations.md"] = docs["relations"]
        files["search_instructions.md"] = docs["instructions"]

        # Add data files as JSON
        for config in self.model_configs:
            model_records = records_by_model.get(config.model_name, [])
            if not model_records:
                continue

            # Simplified JSON format for LangDock
            data = []
            for record in model_records:
                record_data = {"id": record["id"], **record.get("values", {})}
                # Add display values for relations
                for key, value in record.get("display_values", {}).items():
                    if value:
                        record_data[f"{key}_name"] = value
                data.append(record_data)

            filename = f"{config.model_name.replace('.', '_')}.json"
            files[filename] = json.dumps({config.model_name: data}, indent=2, default=str)

        return files

    def export_to_langdock(
        self,
        knowledge_manager: Any,
        folder_id: str,
        records_by_model: dict[str, list[dict[str, Any]]],
        clear_existing: bool = True,
    ) -> dict[str, Any]:
        """
        Export to LangDock Knowledge Folder.

        Args:
            knowledge_manager: LangDockKnowledgeManager instance
            folder_id: Target folder ID
            records_by_model: Records grouped by model name
            clear_existing: Whether to delete existing files first

        Returns:
            Export result with statistics
        """
        import tempfile
        import os

        files = self.prepare_for_langdock(records_by_model)

        # Clear existing files if requested
        if clear_existing:
            try:
                existing = knowledge_manager.list_files(folder_id)
                for file_info in existing:
                    file_id = file_info.get("id")
                    if file_id:
                        knowledge_manager.delete_file(folder_id, file_id)
            except Exception as e:
                logger.warning(f"Could not clear existing files: {e}")

        # Upload new files
        uploaded = []
        errors = []

        with tempfile.TemporaryDirectory() as temp_dir:
            for filename, content in files.items():
                file_path = os.path.join(temp_dir, filename)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)

                try:
                    result = knowledge_manager.upload_file(folder_id, file_path)
                    uploaded.append({"filename": filename, "result": result})
                except Exception as e:
                    errors.append({"filename": filename, "error": str(e)})
                    logger.error(f"Failed to upload {filename}: {e}")

        return {
            "success": len(errors) == 0,
            "uploaded_count": len(uploaded),
            "error_count": len(errors),
            "uploaded": uploaded,
            "errors": errors,
        }


# Re-export main classes
__all__ = [
    "FieldConfig",
    "ModelConfig",
    "ExportRecord",
    "OdooSchemaGenerator",
    "RecordTransformer",
    "KnowledgeExporter",
]
