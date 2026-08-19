# Reasoning & Thinking Modes — eq-chatbot-core

> **Language / Sprache**: [DE](#deutsch) | [EN](#english)

---

## English

### Overview

"Thinking mode" is not one feature. Across the providers in the registry it refers to **four
structurally different mechanisms** that happen to share a marketing word. Treating them as one
thing is the most common source of confusion — and of runtime 400s, because a parameter that
enables reasoning on one provider is rejected as unknown on another.

This document describes the four mechanisms, maps each provider onto one of them, and explains how
`eq-chatbot-core` normalizes the response side.

**Rule of thumb:** reasoning is a property of the *model*, not of the request — except where it
explicitly isn't. Sections below say which is which.

### The four mechanisms

#### 1. Intrinsic — always on, not switchable

The model reasons by construction. There is no off switch; you can only tune how much effort it
spends. These models typically also reject sampling parameters.

- **Providers:** OpenAI (`o1`, `o3`, `o4`), Azure when serving those deployments
- **Control:** `reasoning_effort: "low" | "medium" | "high"`
- **Library behavior:** temperature is dropped automatically for this family (see
  [Temperature clamping](providers.md#temperature-clamping)). Passing `temperature=0.7` is safe —
  the library strips it rather than letting the provider 400.

#### 2. Toggle — switchable per request (hybrid models)

One model, two behaviors, selected in the request body. Usually off by default.

- **Anthropic:** a `thinking` block with an explicit token budget
- **Google Vertex (Gemini 2.5):** a thinking budget in the generation config
- **Qwen3 (via local / gateway):** an `enable_thinking` boolean
- **Privatemode (Kimi):** `chat_template_kwargs={"thinking": False}` — reasoning is *on* by
  default here; the provider accepts this as a plain keyword and routes it into the request body
- **Control:** per request, and the budget is a real cost/latency lever
- **Caveat:** budgets interact with `max_tokens`. Reasoning tokens are billed and count toward the
  output budget on most providers — size `max_tokens` accordingly or responses truncate mid-answer.

#### 3. Variant — separate model IDs

The reasoning version is a different model. You choose by ID; there is nothing to toggle.

- **Melious:** DeepSeek-R1, Kimi Thinking, Qwen Thinking variants (vs. their instruct siblings)
- **Local:** separate GGUF builds under Ollama / LM Studio
- **Control:** `model=` selection; some variants additionally accept `reasoning_effort`
- **Note:** these are slower *per token*, not just in total, because intermediate reasoning is
  emitted as tokens.

#### 4. Router hint — a scheduling preference, not a mode

The gateway uses the hint to pick infrastructure or a default model class. It does not turn
reasoning on inside a given model.

- **Melious:** `preset: "reasoning" | "non_reasoning"` (the latter is equivalent to the `:speed`
  routing flavor)
- **Do not confuse this with the `:flavor` suffix.** `<MODEL_ID>:speed`, `:price`, `:eco`,
  `:balanced`, `:batch` select *which European provider runs your inference*, weighted across
  price / speed / environment. They do not change model behavior at all. Any other suffix is
  treated as part of the model ID and yields an unknown-model error.

### Provider matrix

| Provider | Mechanism | Control surface | Off by default? |
| --- | --- | --- | --- |
| `openai` | Intrinsic (o-series) | `reasoning_effort` | n/a — always on |
| `anthropic` | Toggle | `thinking` block + budget | yes |
| `azure` | Intrinsic / none | depends on deployed model | model-dependent |
| `vertex` | Toggle | thinking budget (Gemini 2.5) | yes |
| `langdock` | Pass-through | whatever the target model accepts | model-dependent |
| `openrouter` | Pass-through | own reasoning params + suffixes | model-dependent |
| `mammouth` | Pass-through | target-model dependent | model-dependent |
| `litellm` | Pass-through | gateway/model dependent | model-dependent |
| `ionos` | Variant | model selection (mostly non-reasoning catalogue) | yes |
| `melious` | Variant + router hint | model ID, `preset`, `reasoning_effort` | yes |
| `privatemode` | Toggle | `chat_template_kwargs={"thinking": false}` (Kimi) | yes |
| `local` / `lm_studio` / `ollama` | Variant | which GGUF you pulled | yes |

> **Verify parameter names per release.** The *mechanisms* are stable; the *spellings* are not.
> Upstream providers rename and deprecate reasoning parameters frequently. Treat the middle column
> as a pointer to the vendor docs, not as a contract.

> **Odoo-layer note:** `azure` and `vertex` stay in this registry but are **frozen in the Odoo
> chatbot UI** since 09.07.2026 (`FROZEN_PROVIDERS` in `eq.chatbot.config`) — not selectable there.
> The Odoo layer also has no combined `local` provider; it exposes `ollama` and `lm_studio`
> separately.

### Reasoning traces in responses

This is where OpenAI compatibility actually breaks. Every gateway serializes the reasoning trace
differently — `reasoning_content`, `reasoning`, or typed thinking blocks inside a content array.

`eq-chatbot-core` normalizes this:

- `LLMResponse.content` — **the answer only.** Reasoning traces are never merged in.
- `LLMResponse.raw_response` — the untouched upstream payload, including whatever trace field the
  provider used.

```python
response = provider.chat_completion(messages=..., model="...")

print(response.content)          # answer, always clean
trace = response.raw_response     # provider-specific; may contain reasoning_content
```

Three consequences worth internalizing:

1. **Never parse `content` for reasoning.** If you need the trace, read `raw_response` and branch
   on the provider. Do not regex `content` for `<think>` tags.
2. **Reasoning tokens are billed.** `total_tokens` includes them where the provider reports them.
   A reasoning model can cost several times a non-reasoning one for an identical answer.
3. **Never surface a trace to end users** without a deliberate decision. Traces routinely contain
   restated user input, discarded hypotheses, and speculative statements the model itself rejected.
   In an Odoo-embedded chatbot that is both a support-quality and a data-protection problem.

### Choosing: when reasoning helps and when it hurts

| Task | Reasoning? | Why |
| --- | --- | --- |
| Transcript cleanup, punctuation, formatting | **No** | Mechanical rewriting; reasoning adds latency, not accuracy |
| Translation | **No** | Pattern task |
| Summarization | **No** | Extraction, not deduction |
| Classification / routing | **No** | Latency dominates; use the fastest model that passes eval |
| RAG answer synthesis | Usually no | Quality comes from retrieval, not from deliberation |
| Multi-step data transformation | Yes | Intermediate steps genuinely help |
| Code generation with constraints | Yes | Benefits from planning |
| Ambiguous business-logic decisions | Yes | Explicit tradeoff weighing |

Default to non-reasoning. Escalate to a reasoning model only when an eval shows it beats the
cheaper option on your actual data — not on intuition.

### Transcription is not a reasoning question

A recurring misconception: speech-to-text models have no thinking mode to enable or disable.
Whisper-class models are encoder-decoder ASR — audio in, text out. No `messages` array, no chat
semantics, no reasoning traces. They are reached through a different endpoint entirely:

```python
# STT — not chat_completion(), not a reasoning decision
text = provider.transcribe(("speech.wav", audio_bytes, "audio/wav"),
                           model="whisper-large-v3")
```

The reasoning decision belongs to the **next** step — the LLM that post-processes the transcript.
Per the table above, that step should almost always be non-reasoning.

There is a separate, easily-confused capability: some chat models accept audio directly as message
content and reason *about* it rather than transcribing it (Voxtral on Melious, for example). That
is `chat_completion()` with audio content blocks, not `transcribe()`. Pick deliberately — the two
produce very different outputs and cost profiles.

> **Interface note:** `transcribe()` / `text_to_speech()` currently live on the LiteLLM provider
> only, while `BaseLLMProvider` covers `chat_completion()`, `stream_completion()` and
> `list_models()`. Melious and IONOS also serve audio models. If speech becomes a broader use case,
> promoting STT to an optional protocol on the base class is the clean fix.

### Querying reasoning support in code

Since **1.19.0** the question "does this model reason?" is answerable from code instead of from
this page. `eq_chatbot_core.services.capability_catalog` ships a curated catalog
(`data/capability_catalog.json`) that carries a per-model `capabilities.reasoning` boolean
alongside the other modality flags, plus limits and pricing:

```python
from eq_chatbot_core.services.capability_catalog import CapabilityCatalog

catalog = CapabilityCatalog.from_snapshot()   # or .from_remote() for the live catalog
caps = catalog.lookup("anthropic/claude-sonnet-4")
caps["reasoning"]   # True — the resolved bundle is flat, not nested
```

`lookup()` returns a `ModelCapabilities` bundle (or `None` for an unknown model) that flattens
capabilities, limits and pricing into one dict — `reasoning`, `tools`, `image_input`,
`context_length`, `input_per_1k`, … Aliases resolve, so `lookup("gpt-4o")` and
`lookup("azure/gpt-4o")` hit the same entry.

`capability_meta` in the same JSON provides the icon plus a bilingual label/help string per flag,
so UIs render the catalog without hardcoding copy.

**What the catalog does *not* answer:** it is one bit — *whether*, never *by which mechanism*. The
four-mechanism taxonomy above stays documentation, and so does the parameter spelling per provider.

**Consumer (Odoo):** `eq.chatbot.available.model.supports_reasoning` is filled from the catalog on
"Refresh Models" and rendered as the "Thinking" icon in the model capability card
(`eq_chatbot` ≥ 19.0.1.8.0).

**Still open — `ModelInfo` does not carry the flag.** A provider's `list_models()` returns
`ModelInfo(id, name, provider, context_length, supports_streaming, supports_tools,
supports_vision)`; reasoning is absent, so callers must go through the catalog. Two additions would
close that gap and make the mechanism itself queryable:

```python
@dataclass
class ModelInfo:
    ...
    supports_reasoning: bool = False
    reasoning_control: Literal["none", "effort", "toggle", "variant"] = "none"
```

Mapping to the sections above: `effort` → intrinsic, `toggle` → per-request, `variant` → separate
model ID, `none` → no reasoning. Callers could then branch generically:

```python
info = provider.get_model_info(model)
if info.reasoning_control == "toggle":
    kwargs["thinking"] = {...}
elif info.reasoning_control == "effort":
    kwargs["reasoning_effort"] = "low"
```

### See also

- [Providers](providers.md#english) — registry, auth, capability matrix, temperature clamping
- [CLI reference](cli.md#english) — `eq-chatbot list-models` for live catalogues
- [RAG pipeline](rag.md#english) — why retrieval quality beats reasoning for grounded answers

---

[← Back to README](../README.md#english) · [docs index →](README.md#english)

---

## Deutsch

### Überblick

„Thinking Mode“ ist kein einzelnes Feature. Über die Provider der Registry hinweg bezeichnet der
Begriff **vier strukturell verschiedene Mechanismen**, die sich zufällig ein Marketingwort teilen.
Sie als eine Sache zu behandeln ist die häufigste Verwechslungsquelle — und eine Ursache für 400er
zur Laufzeit, denn ein Parameter, der bei einem Provider Reasoning aktiviert, wird beim nächsten als
unbekannt abgelehnt.

Dieses Dokument beschreibt die vier Mechanismen, ordnet jeden Provider einem davon zu und erklärt,
wie `eq-chatbot-core` die Antwortseite normalisiert.

**Faustregel:** Reasoning ist eine Eigenschaft des *Modells*, nicht des Requests — außer dort, wo es
das ausdrücklich nicht ist. Die Abschnitte unten sagen, was wo gilt.

### Die vier Mechanismen

#### 1. Intrinsisch — immer an, nicht abschaltbar

Das Modell denkt konstruktionsbedingt. Es gibt keinen Aus-Schalter; steuerbar ist nur der Aufwand.
Diese Modelle lehnen typischerweise auch Sampling-Parameter ab.

- **Provider:** OpenAI (`o1`, `o3`, `o4`), Azure bei entsprechenden Deployments
- **Steuerung:** `reasoning_effort: "low" | "medium" | "high"`
- **Verhalten der Library:** Temperature wird für diese Familie automatisch verworfen (siehe
  [Temperature-Clamping](providers.md#temperature-clamping)). `temperature=0.7` zu übergeben ist
  unkritisch — die Library entfernt den Wert, statt den Provider mit 400 antworten zu lassen.

#### 2. Toggle — pro Request umschaltbar (Hybrid-Modelle)

Ein Modell, zwei Verhalten, ausgewählt im Request-Body. Meist standardmäßig aus.

- **Anthropic:** ein `thinking`-Block mit explizitem Token-Budget
- **Google Vertex (Gemini 2.5):** ein Thinking-Budget in der Generation-Config
- **Qwen3 (lokal / via Gateway):** ein `enable_thinking`-Boolean
- **Privatemode (Kimi):** `chat_template_kwargs={"thinking": False}` — Reasoning ist hier
  standardmäßig *an*; der Provider nimmt das als normales Keyword und routet es in den Request-Body
- **Steuerung:** pro Request; das Budget ist ein echter Kosten- und Latenzhebel
- **Vorsicht:** Budgets interagieren mit `max_tokens`. Reasoning-Tokens werden abgerechnet und
  zählen bei den meisten Providern gegen das Output-Budget — `max_tokens` entsprechend
  dimensionieren, sonst brechen Antworten mitten im Satz ab.

#### 3. Variante — eigene Modell-IDs

Die Reasoning-Version ist ein anderes Modell. Auswahl über die ID; es gibt nichts umzuschalten.

- **Melious:** DeepSeek-R1, Kimi Thinking, Qwen-Thinking-Varianten (gegenüber ihren
  Instruct-Geschwistern)
- **Local:** eigene GGUF-Builds unter Ollama / LM Studio
- **Steuerung:** `model=`; manche Varianten akzeptieren zusätzlich `reasoning_effort`
- **Hinweis:** Diese Modelle sind *pro Token* langsamer, nicht nur insgesamt, weil
  Zwischenschritte als Tokens ausgegeben werden.

#### 4. Router-Hint — eine Scheduling-Präferenz, kein Modus

Das Gateway nutzt den Hinweis zur Auswahl von Infrastruktur oder einer Default-Modellklasse. Es
aktiviert kein Reasoning innerhalb eines gegebenen Modells.

- **Melious:** `preset: "reasoning" | "non_reasoning"` (letzteres entspricht dem
  Routing-Flavor `:speed`)
- **Nicht mit dem `:flavor`-Suffix verwechseln.** `<MODEL_ID>:speed`, `:price`, `:eco`,
  `:balanced`, `:batch` wählen, *welcher europäische Provider die Inferenz ausführt*, gewichtet
  über Preis / Geschwindigkeit / Umwelt. Sie ändern das Modellverhalten überhaupt nicht. Jedes
  andere Suffix wird als Teil der Modell-ID gewertet und erzeugt einen Unknown-Model-Fehler.

### Provider-Matrix

| Provider | Mechanismus | Steuerung | Standardmäßig aus? |
| --- | --- | --- | --- |
| `openai` | Intrinsisch (o-Reihe) | `reasoning_effort` | n/a — immer an |
| `anthropic` | Toggle | `thinking`-Block + Budget | ja |
| `azure` | Intrinsisch / keins | je nach deployten Modell | modellabhängig |
| `vertex` | Toggle | Thinking-Budget (Gemini 2.5) | ja |
| `langdock` | Durchgereicht | was das Zielmodell akzeptiert | modellabhängig |
| `openrouter` | Durchgereicht | eigene Reasoning-Parameter + Suffixe | modellabhängig |
| `mammouth` | Durchgereicht | zielmodellabhängig | modellabhängig |
| `litellm` | Durchgereicht | gateway-/modellabhängig | modellabhängig |
| `ionos` | Variante | Modellwahl (überwiegend Non-Reasoning-Katalog) | ja |
| `melious` | Variante + Router-Hint | Modell-ID, `preset`, `reasoning_effort` | ja |
| `privatemode` | Toggle | `chat_template_kwargs={"thinking": false}` (Kimi) | ja |
| `local` / `lm_studio` / `ollama` | Variante | welches GGUF geladen wurde | ja |

> **Parameternamen pro Release verifizieren.** Die *Mechanismen* sind stabil, die *Schreibweisen*
> nicht. Upstream-Provider benennen Reasoning-Parameter regelmäßig um oder deprecaten sie. Die
> mittlere Spalte ist ein Zeiger auf die Herstellerdoku, kein Vertrag.

> **Hinweis zur Odoo-Ebene:** `azure` und `vertex` bleiben in dieser Registry, sind in der
> Odoo-Chatbot-UI aber seit 09.07.2026 **eingefroren** (`FROZEN_PROVIDERS` in `eq.chatbot.config`)
> — dort nicht wählbar. Die Odoo-Ebene kennt außerdem keinen kombinierten `local`-Provider, sondern
> `ollama` und `lm_studio` getrennt.

### Reasoning-Traces in Antworten

Hier bricht die OpenAI-Kompatibilität tatsächlich. Jedes Gateway serialisiert den Denkprozess
anders — `reasoning_content`, `reasoning` oder typisierte Thinking-Blöcke innerhalb eines
Content-Arrays.

`eq-chatbot-core` normalisiert das:

- `LLMResponse.content` — **nur die Antwort.** Reasoning-Traces werden nie hineingemischt.
- `LLMResponse.raw_response` — das unveränderte Upstream-Payload, inklusive des vom Provider
  verwendeten Trace-Feldes.

```python
response = provider.chat_completion(messages=..., model="...")

print(response.content)          # Antwort, immer sauber
trace = response.raw_response     # providerspezifisch; ggf. mit reasoning_content
```

Drei Konsequenzen, die man verinnerlichen sollte:

1. **Niemals `content` nach Reasoning parsen.** Wer den Trace braucht, liest `raw_response` und
   verzweigt nach Provider. Kein Regex auf `<think>`-Tags in `content`.
2. **Reasoning-Tokens werden abgerechnet.** `total_tokens` enthält sie, wo der Provider sie meldet.
   Ein Reasoning-Modell kann für dieselbe Antwort ein Vielfaches eines Non-Reasoning-Modells kosten.
3. **Traces nie ungeprüft an Endnutzer ausgeben.** Sie enthalten regelmäßig wiederholte
   Nutzereingaben, verworfene Hypothesen und spekulative Aussagen, die das Modell selbst verworfen
   hat. In einem Odoo-eingebetteten Chatbot ist das sowohl ein Qualitäts- als auch ein
   Datenschutzproblem.

### Auswahl: wann Reasoning hilft und wann es schadet

| Aufgabe | Reasoning? | Begründung |
| --- | --- | --- |
| Transkript-Bereinigung, Interpunktion, Formatierung | **Nein** | Mechanisches Umschreiben; Reasoning bringt Latenz, keine Genauigkeit |
| Übersetzung | **Nein** | Mustertask |
| Zusammenfassung | **Nein** | Extraktion, keine Deduktion |
| Klassifikation / Routing | **Nein** | Latenz dominiert; schnellstes Modell nehmen, das die Eval besteht |
| RAG-Antwortsynthese | Meist nein | Qualität kommt aus dem Retrieval, nicht aus dem Nachdenken |
| Mehrstufige Datentransformation | Ja | Zwischenschritte helfen wirklich |
| Codegenerierung mit Constraints | Ja | Profitiert von Planung |
| Mehrdeutige Business-Logik-Entscheidungen | Ja | Explizites Abwägen von Tradeoffs |

Standard ist Non-Reasoning. Eskalation auf ein Reasoning-Modell nur, wenn eine Eval auf euren
echten Daten zeigt, dass es die günstigere Option schlägt — nicht nach Bauchgefühl.

### Transkription ist keine Reasoning-Frage

Ein wiederkehrendes Missverständnis: Speech-to-Text-Modelle haben keinen Thinking Mode, den man
aktivieren oder deaktivieren könnte. Whisper-Klasse-Modelle sind Encoder-Decoder-ASR — Audio rein,
Text raus. Kein `messages`-Array, keine Chat-Semantik, keine Reasoning-Traces. Sie werden über einen
völlig anderen Endpunkt angesprochen:

```python
# STT — nicht chat_completion(), keine Reasoning-Entscheidung
text = provider.transcribe(("speech.wav", audio_bytes, "audio/wav"),
                           model="whisper-large-v3")
```

Die Reasoning-Entscheidung gehört zum **nächsten** Schritt — dem LLM, das das Transkript
nachbearbeitet. Laut Tabelle oben sollte dieser Schritt fast immer ohne Reasoning laufen.

Davon zu unterscheiden ist eine leicht zu verwechselnde Fähigkeit: Manche Chat-Modelle nehmen Audio
direkt als Message-Content entgegen und schlussfolgern *darüber*, statt es zu transkribieren (etwa
Voxtral bei Melious). Das ist `chat_completion()` mit Audio-Content-Blöcken, nicht `transcribe()`.
Bewusst wählen — die beiden erzeugen sehr unterschiedliche Ausgaben und Kostenprofile.

> **Interface-Hinweis:** `transcribe()` / `text_to_speech()` liegen derzeit nur am
> LiteLLM-Provider, während `BaseLLMProvider` `chat_completion()`, `stream_completion()` und
> `list_models()` abdeckt. Melious und IONOS bieten ebenfalls Audio-Modelle. Wird Sprache zum
> breiteren Use Case, ist STT als optionales Protokoll auf der Basisklasse der saubere Weg.

### Reasoning-Fähigkeit im Code abfragen

Seit **1.19.0** ist die Frage „Denkt dieses Modell?“ aus dem Code beantwortbar statt aus dieser
Seite. `eq_chatbot_core.services.capability_catalog` liefert einen kuratierten Katalog
(`data/capability_catalog.json`) mit einem `capabilities.reasoning`-Boolean je Modell — neben den
übrigen Modalitäts-Flags sowie Limits und Preisen:

```python
from eq_chatbot_core.services.capability_catalog import CapabilityCatalog

catalog = CapabilityCatalog.from_snapshot()   # oder .from_remote() für den Live-Katalog
caps = catalog.lookup("anthropic/claude-sonnet-4")
caps["reasoning"]   # True — das aufgelöste Bündel ist flach, nicht verschachtelt
```

`lookup()` liefert ein `ModelCapabilities`-Bündel (oder `None` bei unbekanntem Modell), das
Capabilities, Limits und Preise in ein Dict zusammenzieht — `reasoning`, `tools`, `image_input`,
`context_length`, `input_per_1k`, … Aliase werden aufgelöst, `lookup("gpt-4o")` und
`lookup("azure/gpt-4o")` treffen denselben Eintrag.

`capability_meta` in derselben JSON-Datei liefert je Flag das Icon plus einen zweisprachigen
Label-/Hilfetext, sodass UIs den Katalog ohne hartcodierte Texte rendern.

**Was der Katalog *nicht* beantwortet:** Er ist ein einzelnes Bit — *ob*, nie *nach welchem
Mechanismus*. Die Vier-Mechanismen-Taxonomie oben bleibt Dokumentation, ebenso die Schreibweise der
Parameter je Provider.

**Konsument (Odoo):** `eq.chatbot.available.model.supports_reasoning` wird beim „Refresh Models“ aus
dem Katalog befüllt und in der Fähigkeiten-Karte als „Thinking“-Icon gerendert
(`eq_chatbot` ≥ 19.0.1.8.0).

**Weiterhin offen — `ModelInfo` trägt das Flag nicht.** `list_models()` eines Providers liefert
`ModelInfo(id, name, provider, context_length, supports_streaming, supports_tools,
supports_vision)`; Reasoning fehlt, Aufrufer müssen also über den Katalog gehen. Zwei Ergänzungen
würden die Lücke schließen und den Mechanismus selbst abfragbar machen:

```python
@dataclass
class ModelInfo:
    ...
    supports_reasoning: bool = False
    reasoning_control: Literal["none", "effort", "toggle", "variant"] = "none"
```

Zuordnung zu den Abschnitten oben: `effort` → intrinsisch, `toggle` → pro Request, `variant` →
eigene Modell-ID, `none` → kein Reasoning. Aufrufer könnten dann generisch verzweigen:

```python
info = provider.get_model_info(model)
if info.reasoning_control == "toggle":
    kwargs["thinking"] = {...}
elif info.reasoning_control == "effort":
    kwargs["reasoning_effort"] = "low"
```

### Siehe auch

- [Provider](providers.md#deutsch) — Registry, Auth, Capability-Matrix, Temperature-Clamping
- [CLI-Referenz](cli.md#deutsch) — `eq-chatbot list-models` für Live-Kataloge
- [RAG-Pipeline](rag.md#deutsch) — warum Retrieval-Qualität Reasoning bei fundierten Antworten schlägt

---

[← Zurück zum README](../README.md#deutsch) · [Doku-Index →](README.md#deutsch)
