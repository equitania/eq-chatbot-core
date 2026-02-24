"""
Unit tests for the knowledge export service.

Tests schema generation, record transformation, and export preparation.
"""

import pytest

from eq_chatbot_core.services.knowledge_service import (
    ExportRecord,
    FieldConfig,
    KnowledgeExporter,
    ModelConfig,
    OdooSchemaGenerator,
    RecordTransformer,
)

# =============================================================================
# FieldConfig Tests
# =============================================================================


@pytest.mark.unit
class TestFieldConfig:
    """Test FieldConfig dataclass."""

    def test_basic_field(self):
        """Test creating a basic field configuration."""
        field = FieldConfig(
            name="name",
            label="Name",
            field_type="char",
        )

        assert field.name == "name"
        assert field.label == "Name"
        assert field.field_type == "char"
        assert field.relation is None
        assert field.is_text_field is False

    def test_relational_field(self):
        """Test creating a relational field configuration."""
        field = FieldConfig(
            name="partner_id",
            label="Partner",
            field_type="many2one",
            relation="res.partner",
        )

        assert field.name == "partner_id"
        assert field.relation == "res.partner"

    def test_text_field(self):
        """Test creating a text field for chunking."""
        field = FieldConfig(
            name="description",
            label="Description",
            field_type="text",
            is_text_field=True,
        )

        assert field.is_text_field is True


# =============================================================================
# ModelConfig Tests
# =============================================================================


@pytest.mark.unit
class TestModelConfig:
    """Test ModelConfig dataclass."""

    def test_basic_model_config(self):
        """Test creating a basic model configuration."""
        config = ModelConfig(
            model_name="res.partner",
            model_label="Contact",
            fields=[
                FieldConfig(name="name", label="Name", field_type="char"),
                FieldConfig(name="email", label="Email", field_type="char"),
            ],
        )

        assert config.model_name == "res.partner"
        assert config.model_label == "Contact"
        assert len(config.fields) == 2
        assert config.domain == "[]"

    def test_model_config_with_domain(self):
        """Test creating a model configuration with domain filter."""
        config = ModelConfig(
            model_name="res.partner",
            model_label="Active Contacts",
            fields=[FieldConfig(name="name", label="Name", field_type="char")],
            domain="[('active', '=', True)]",
        )

        assert config.domain == "[('active', '=', True)]"


# =============================================================================
# OdooSchemaGenerator Tests
# =============================================================================


@pytest.mark.unit
class TestOdooSchemaGenerator:
    """Test OdooSchemaGenerator class."""

    @pytest.fixture
    def sample_model_configs(self):
        """Create sample model configurations."""
        return [
            ModelConfig(
                model_name="res.partner",
                model_label="Contact",
                fields=[
                    FieldConfig(name="name", label="Name", field_type="char"),
                    FieldConfig(name="email", label="Email", field_type="char"),
                    FieldConfig(
                        name="country_id",
                        label="Country",
                        field_type="many2one",
                        relation="res.country",
                    ),
                ],
            ),
            ModelConfig(
                model_name="sale.order",
                model_label="Sales Order",
                fields=[
                    FieldConfig(name="name", label="Order Reference", field_type="char"),
                    FieldConfig(
                        name="partner_id",
                        label="Customer",
                        field_type="many2one",
                        relation="res.partner",
                    ),
                    FieldConfig(name="amount_total", label="Total", field_type="monetary"),
                ],
            ),
        ]

    def test_generate_schema(self, sample_model_configs):
        """Test generating schema documentation."""
        generator = OdooSchemaGenerator()
        schema = generator.generate_schema(sample_model_configs)

        assert "# Data Schema Documentation" in schema
        assert "## Model: res.partner" in schema
        assert "## Model: sale.order" in schema
        assert "| `name` |" in schema
        assert "| `email` |" in schema
        assert "Reference to res.country" in schema

    def test_generate_relations(self, sample_model_configs):
        """Test generating relations documentation."""
        generator = OdooSchemaGenerator()
        relations = generator.generate_relations(sample_model_configs)

        assert "# Data Relations Overview" in relations
        assert "## res.partner" in relations
        assert "**country_id** → `res.country`" in relations
        assert "Many2One" in relations

    def test_generate_search_instructions(self, sample_model_configs):
        """Test generating search instructions."""
        generator = OdooSchemaGenerator()
        instructions = generator.generate_search_instructions(sample_model_configs)

        assert "# AI Search Instructions" in instructions
        assert "res.partner" in instructions
        assert "sale.order" in instructions
        assert "## How to Search" in instructions


# =============================================================================
# RecordTransformer Tests
# =============================================================================


@pytest.mark.unit
class TestRecordTransformer:
    """Test RecordTransformer class."""

    @pytest.fixture
    def partner_config(self):
        """Create partner model configuration."""
        return ModelConfig(
            model_name="res.partner",
            model_label="Contact",
            fields=[
                FieldConfig(name="name", label="Name", field_type="char"),
                FieldConfig(name="email", label="Email", field_type="char"),
                FieldConfig(
                    name="comment",
                    label="Notes",
                    field_type="text",
                    is_text_field=True,
                ),
            ],
        )

    def test_transform_simple_record(self, partner_config):
        """Test transforming a simple record."""
        transformer = RecordTransformer(partner_config)

        records = list(
            transformer.transform_record(
                record_id=1,
                field_values={
                    "name": "Test Partner",
                    "email": "test@example.com",
                    "comment": "Short note",
                },
            )
        )

        assert len(records) == 1
        record = records[0]
        assert record.id == 1
        assert record.model == "res.partner"
        assert "Test Partner" in record.content
        assert record.metadata["name"] == "Test Partner"

    def test_transform_record_with_display_values(self, partner_config):
        """Test transforming a record with display values."""
        # Add a relational field
        partner_config.fields.append(
            FieldConfig(
                name="country_id",
                label="Country",
                field_type="many2one",
                relation="res.country",
            )
        )

        transformer = RecordTransformer(partner_config)

        records = list(
            transformer.transform_record(
                record_id=1,
                field_values={
                    "name": "Test Partner",
                    "email": "test@example.com",
                    "comment": "",
                    "country_id": 42,
                },
                display_values={
                    "country_id": "Germany",
                },
            )
        )

        assert len(records) == 1
        record = records[0]
        assert record.metadata["country_id"] == 42
        assert record.metadata["country_id_display"] == "Germany"

    def test_transform_multiple_records(self, partner_config):
        """Test transforming multiple records."""
        transformer = RecordTransformer(partner_config)

        records_data = [
            {
                "id": 1,
                "values": {"name": "Partner A", "email": "a@test.com", "comment": ""},
            },
            {
                "id": 2,
                "values": {"name": "Partner B", "email": "b@test.com", "comment": ""},
            },
        ]

        records = list(transformer.transform_records(records_data))

        assert len(records) == 2
        assert records[0].id == 1
        assert records[1].id == 2


# =============================================================================
# KnowledgeExporter Tests
# =============================================================================


@pytest.mark.unit
class TestKnowledgeExporter:
    """Test KnowledgeExporter class."""

    @pytest.fixture
    def sample_configs(self):
        """Create sample model configurations."""
        return [
            ModelConfig(
                model_name="res.partner",
                model_label="Contact",
                fields=[
                    FieldConfig(name="name", label="Name", field_type="char"),
                    FieldConfig(name="email", label="Email", field_type="char"),
                ],
            ),
        ]

    def test_generate_documentation(self, sample_configs):
        """Test generating all documentation."""
        exporter = KnowledgeExporter(sample_configs)
        docs = exporter.generate_documentation()

        assert "schema" in docs
        assert "relations" in docs
        assert "instructions" in docs
        assert "# Data Schema Documentation" in docs["schema"]

    def test_prepare_for_qdrant(self, sample_configs):
        """Test preparing records for Qdrant."""
        exporter = KnowledgeExporter(sample_configs)

        records_by_model = {
            "res.partner": [
                {
                    "id": 1,
                    "values": {"name": "Test Partner", "email": "test@example.com"},
                },
                {
                    "id": 2,
                    "values": {"name": "Another Partner", "email": "another@example.com"},
                },
            ],
        }

        chunks = exporter.prepare_for_qdrant(records_by_model)

        assert len(chunks) == 2
        assert all("content" in chunk for chunk in chunks)
        assert all("metadata" in chunk for chunk in chunks)
        assert all("source" in chunk for chunk in chunks)
        assert chunks[0]["source"] == "odoo:res.partner:1"

    def test_prepare_for_langdock(self, sample_configs):
        """Test preparing files for LangDock."""
        exporter = KnowledgeExporter(sample_configs)

        records_by_model = {
            "res.partner": [
                {
                    "id": 1,
                    "values": {"name": "Test Partner", "email": "test@example.com"},
                },
            ],
        }

        files = exporter.prepare_for_langdock(records_by_model)

        assert "schema.md" in files
        assert "relations.md" in files
        assert "search_instructions.md" in files
        assert "res_partner_001.md" in files

    def test_empty_records(self, sample_configs):
        """Test handling empty records."""
        exporter = KnowledgeExporter(sample_configs)

        chunks = exporter.prepare_for_qdrant({})
        assert chunks == []

        files = exporter.prepare_for_langdock({})
        # Should still have documentation files
        assert "schema.md" in files
        # No data files for empty records
        data_files = [k for k in files if k not in ("schema.md", "relations.md", "search_instructions.md")]
        assert len(data_files) == 0


# =============================================================================
# ExportRecord Tests
# =============================================================================


@pytest.mark.unit
class TestExportRecord:
    """Test ExportRecord dataclass."""

    def test_create_export_record(self):
        """Test creating an export record."""
        record = ExportRecord(
            id=1,
            model="res.partner",
            content="# Test Content",
            metadata={"name": "Test", "id": 1},
        )

        assert record.id == 1
        assert record.model == "res.partner"
        assert record.content == "# Test Content"
        assert record.metadata["name"] == "Test"
