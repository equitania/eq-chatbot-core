# RAG Pipeline — eq-chatbot-core

> **Language / Sprache**: [DE](#deutsch) | [EN](#english)

---

## English

### Overview

The `eq_chatbot_core.rag` package implements a Retrieval-Augmented Generation pipeline:

```
Documents → DocumentChunker → Embedder → Qdrant → HybridRetriever → ContextWindowManager → LLM prompt
```

Each stage is independently usable. The default vector backend is [Qdrant](https://qdrant.tech) (via `qdrant-client`), and the embedder uses any `BaseLLMProvider`-compatible provider — so the same OpenAI/LangDock/Anthropic credentials power both retrieval embeddings and generation.

### Public API surface

```python
from eq_chatbot_core.rag import (
    Chunk,                  # dataclass
    DocumentChunker,        # text → list[Chunk]
    ContextBudget,          # token-budget config
    ContextWindowManager,   # budget-aware context assembly
)
```

The embedder and retriever submodules are **not** re-exported in `__init__.__all__` — import them directly:

```python
from eq_chatbot_core.rag.embedder import (
    BaseEmbedder,         # ABC
    OpenAIEmbedder,
    LangDockEmbedder,
)
from eq_chatbot_core.rag.retriever import (
    HybridRetriever,
    RetrievalResult,      # dataclass
)
```

### Chunking

```python
from eq_chatbot_core.rag.chunker import DocumentChunker, Chunk

chunker = DocumentChunker(
    chunk_size=800,        # tokens
    chunk_overlap=120,
)

chunks: list[Chunk] = chunker.chunk(
    text=long_document_text,
    metadata={"source": "manual.pdf", "page": 12},
)
# Each chunk: chunk.text, chunk.metadata, chunk.token_count
```

### Embedding

Two providers ship out of the box; both implement `BaseEmbedder` and can be swapped freely.

```python
from eq_chatbot_core.rag.embedder import OpenAIEmbedder

embedder = OpenAIEmbedder(api_key="sk-...", model="text-embedding-3-small")

# Single text
vector = embedder.embed("query text")

# Batch
vectors = embedder.embed_batch(["text 1", "text 2", "text 3"])
```

For local embeddings (no API call), install the `[local]` extra and use `sentence-transformers` directly:

```bash
uv pip install eq-chatbot-core[local]
```

### Retrieval

`HybridRetriever` combines vector similarity with optional metadata filtering and reranking. It manages a Qdrant collection lifecycle (`ensure_collection()`, `upsert()`, `retrieve()`).

```python
from qdrant_client import QdrantClient
from eq_chatbot_core.rag.retriever import HybridRetriever, RetrievalResult

qdrant = QdrantClient(url="http://localhost:6333")

retriever = HybridRetriever(
    qdrant_client=qdrant,
    collection_name="docs",
    embedder=embedder,
)

# One-time setup
retriever.ensure_collection()

# Index chunks
retriever.upsert(chunks)

# Query
results: list[RetrievalResult] = retriever.retrieve(
    query="how does authentication work?",
    limit=5,
)
for r in results:
    print(r.score, r.chunk.text[:100])
```

### Context window management

`ContextWindowManager` assembles the final prompt within a token budget — picking the highest-scoring chunks until the budget is hit, leaving room for the system prompt and the model's expected output.

```python
from eq_chatbot_core.rag.context_manager import ContextWindowManager, ContextBudget

manager = ContextWindowManager(
    budget=ContextBudget(
        total_tokens=8_000,        # model context window
        reserved_for_system=500,
        reserved_for_response=1_500,
    ),
)

context = manager.assemble(
    retrieved=results,            # list[RetrievalResult]
    user_query=query,
)
# context: str ready to drop into the messages array
```

### End-to-end example

```python
from qdrant_client import QdrantClient
from eq_chatbot_core.providers import get_provider
from eq_chatbot_core.rag.chunker import DocumentChunker
from eq_chatbot_core.rag.embedder import OpenAIEmbedder
from eq_chatbot_core.rag.retriever import HybridRetriever
from eq_chatbot_core.rag.context_manager import ContextWindowManager, ContextBudget

# Setup
qdrant = QdrantClient(url="http://localhost:6333")
embedder = OpenAIEmbedder(api_key="sk-...", model="text-embedding-3-small")
retriever = HybridRetriever(qdrant, "docs", embedder)
retriever.ensure_collection()

# Index
chunks = DocumentChunker().chunk(open("manual.txt").read(), metadata={"source": "manual.txt"})
retriever.upsert(chunks)

# Query
query = "how do I configure SSO?"
results = retriever.retrieve(query, limit=5)

manager = ContextWindowManager(ContextBudget(total_tokens=8000))
context = manager.assemble(results, user_query=query)

# Generate
provider = get_provider("openai", api_key="sk-...")
response = provider.chat_completion(
    messages=[
        {"role": "system", "content": f"Answer using this context:\n\n{context}"},
        {"role": "user", "content": query},
    ],
    model="gpt-4o-mini",
)
print(response.content)
```

### See also

- [Providers](providers.md#english) — `OpenAIEmbedder` and `LangDockEmbedder` use the same provider stack
- [Security](security.md#english) — `FernetEncryption` for storing the embedder's API key

---

[← Back to README](../README.md#english) · [docs index →](README.md#english)

---

## Deutsch

### Überblick

Das Paket `eq_chatbot_core.rag` implementiert eine Retrieval-Augmented-Generation-Pipeline:

```
Dokumente → DocumentChunker → Embedder → Qdrant → HybridRetriever → ContextWindowManager → LLM-Prompt
```

Jede Stufe ist unabhängig nutzbar. Default-Vector-Backend ist [Qdrant](https://qdrant.tech) (via `qdrant-client`); der Embedder nutzt einen beliebigen `BaseLLMProvider`-kompatiblen Provider — dieselben OpenAI-/LangDock-/Anthropic-Credentials power Retrieval-Embeddings und Generation.

### Öffentliche API-Oberfläche

```python
from eq_chatbot_core.rag import (
    Chunk,                  # dataclass
    DocumentChunker,        # text → list[Chunk]
    ContextBudget,          # Token-Budget-Config
    ContextWindowManager,   # budget-aware Context-Assembly
)
```

Die Embedder- und Retriever-Submodule sind **nicht** in `__init__.__all__` re-exportiert — direkt importieren:

```python
from eq_chatbot_core.rag.embedder import (
    BaseEmbedder,         # ABC
    OpenAIEmbedder,
    LangDockEmbedder,
)
from eq_chatbot_core.rag.retriever import (
    HybridRetriever,
    RetrievalResult,      # dataclass
)
```

### Chunking

```python
from eq_chatbot_core.rag.chunker import DocumentChunker, Chunk

chunker = DocumentChunker(
    chunk_size=800,        # Tokens
    chunk_overlap=120,
)

chunks: list[Chunk] = chunker.chunk(
    text=langer_dokument_text,
    metadata={"source": "manual.pdf", "page": 12},
)
# Jeder Chunk: chunk.text, chunk.metadata, chunk.token_count
```

### Embedding

Zwei Provider out-of-the-box; beide implementieren `BaseEmbedder` und können frei getauscht werden.

```python
from eq_chatbot_core.rag.embedder import OpenAIEmbedder

embedder = OpenAIEmbedder(api_key="sk-...", model="text-embedding-3-small")

# Einzeltext
vector = embedder.embed("Query-Text")

# Batch
vectors = embedder.embed_batch(["Text 1", "Text 2", "Text 3"])
```

Für lokale Embeddings (kein API-Call) das `[local]`-Extra installieren und `sentence-transformers` direkt nutzen:

```bash
uv pip install eq-chatbot-core[local]
```

### Retrieval

`HybridRetriever` kombiniert Vector-Similarity mit optionalem Metadata-Filtering und Reranking. Verwaltet den Qdrant-Collection-Lifecycle (`ensure_collection()`, `upsert()`, `retrieve()`).

```python
from qdrant_client import QdrantClient
from eq_chatbot_core.rag.retriever import HybridRetriever, RetrievalResult

qdrant = QdrantClient(url="http://localhost:6333")

retriever = HybridRetriever(
    qdrant_client=qdrant,
    collection_name="docs",
    embedder=embedder,
)

# Einmaliges Setup
retriever.ensure_collection()

# Chunks indizieren
retriever.upsert(chunks)

# Abfrage
results: list[RetrievalResult] = retriever.retrieve(
    query="wie funktioniert die Authentifizierung?",
    limit=5,
)
for r in results:
    print(r.score, r.chunk.text[:100])
```

### Context-Window-Management

`ContextWindowManager` baut den finalen Prompt innerhalb eines Token-Budgets — wählt die Top-Scoring-Chunks bis das Budget erreicht ist, lässt Platz für System-Prompt und erwartete Modell-Antwort.

```python
from eq_chatbot_core.rag.context_manager import ContextWindowManager, ContextBudget

manager = ContextWindowManager(
    budget=ContextBudget(
        total_tokens=8_000,        # Modell-Context-Fenster
        reserved_for_system=500,
        reserved_for_response=1_500,
    ),
)

context = manager.assemble(
    retrieved=results,            # list[RetrievalResult]
    user_query=query,
)
# context: str — direkt in Messages einsetzbar
```

### End-to-End-Beispiel

```python
from qdrant_client import QdrantClient
from eq_chatbot_core.providers import get_provider
from eq_chatbot_core.rag.chunker import DocumentChunker
from eq_chatbot_core.rag.embedder import OpenAIEmbedder
from eq_chatbot_core.rag.retriever import HybridRetriever
from eq_chatbot_core.rag.context_manager import ContextWindowManager, ContextBudget

# Setup
qdrant = QdrantClient(url="http://localhost:6333")
embedder = OpenAIEmbedder(api_key="sk-...", model="text-embedding-3-small")
retriever = HybridRetriever(qdrant, "docs", embedder)
retriever.ensure_collection()

# Indizierung
chunks = DocumentChunker().chunk(open("manual.txt").read(), metadata={"source": "manual.txt"})
retriever.upsert(chunks)

# Abfrage
query = "Wie konfiguriere ich SSO?"
results = retriever.retrieve(query, limit=5)

manager = ContextWindowManager(ContextBudget(total_tokens=8000))
context = manager.assemble(results, user_query=query)

# Generation
provider = get_provider("openai", api_key="sk-...")
response = provider.chat_completion(
    messages=[
        {"role": "system", "content": f"Antworte mithilfe dieses Kontexts:\n\n{context}"},
        {"role": "user", "content": query},
    ],
    model="gpt-4o-mini",
)
print(response.content)
```

### Siehe auch

- [Provider](providers.md#deutsch) — `OpenAIEmbedder` und `LangDockEmbedder` nutzen denselben Provider-Stack
- [Security](security.md#deutsch) — `FernetEncryption` zum Speichern des Embedder-API-Keys

---

[← Zurück zum README](../README.md#deutsch) · [Doku-Index →](README.md#deutsch)
