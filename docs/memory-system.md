# Nexux by Klyx — Memory System Specification

## Purpose

This document defines the memory architecture of Nexux.

The goal of the memory system is NOT:

- infinite chat history replay
- unlimited context stuffing
- storing everything directly inside LLM context

The goal is:

```text
Persistent, structured, retrievable cognition.
```

Nexux memory should behave more like:

- human memory
- contextual recall
- semantic understanding
- summarized experience

instead of:

- endless transcript replay

---

# Core Memory Philosophy

## 1. Context Windows Are NOT Memory

The runtime should never depend entirely on:

- massive context windows
- replaying entire conversations
- full operational logs

Large context windows eventually:

- become inefficient
- degrade reasoning quality
- increase latency
- increase hallucination risk

Memory must remain externalized and structured.

---

## 2. Retrieval Over Replay

The system should retrieve:

- relevant knowledge
- relevant workflows
- relevant summaries
- relevant operational history

instead of replaying:

- entire sessions
- full logs
- irrelevant history

Only contextually relevant memory should enter active cognition.

---

## 3. Layered Memory

Different types of cognition require different memory layers.

Nexux uses:

- working memory
- session memory
- long-term semantic memory
- raw archival memory

Each layer has:

- different retention rules
- different retrieval behavior
- different compression levels

---

## 4. Compression Is Mandatory

Raw cognition should eventually become compressed.

Examples:

- conversations summarized
- workflows abstracted
- tool outputs compressed
- operational history distilled

The runtime should avoid:

- infinite memory growth
- operational noise accumulation
- context pollution

---

## 5. Memory Must Remain Observable

Memory operations should remain inspectable.

The runtime should expose:

- retrieved memories
- memory ranking
- memory summaries
- retrieval reasoning
- memory sources

The user should never feel:

- hidden manipulation
- invisible context injection

---

# Memory Architecture Overview

```text id="8x8m7c"
Working Memory
        ↓
Session Memory
        ↓
Long-Term Semantic Memory
        ↓
Raw Archive
```

---

# Memory Layers

---

# 1. Working Memory

## Purpose

Short-term active cognition.

Contains:

- current conversation
- active workflow state
- pending tasks
- temporary reasoning context
- immediate operational data

---

## Characteristics

- fast access
- temporary
- high relevance
- low compression
- token-sensitive

---

## Retention

Working memory should:

- expire aggressively
- summarize frequently
- avoid uncontrolled growth

---

## Example

```text id="lf1wdm"
Current browser workflow
Current spreadsheet task
Pending permission request
```

---

# 2. Session Memory

## Purpose

Session-level compressed cognition.

Contains:

- conversation summaries
- workflow summaries
- task history
- operational context

---

## Characteristics

- moderately compressed
- retrievable
- contextual
- semi-persistent

---

## Retention

Session memory may:

- persist temporarily
- merge into long-term memory
- expire based on relevance

---

## Example

```text id="jlwm2u"
"User modified Shopify product CSV workflow today."
```

---

# 3. Long-Term Semantic Memory

## Purpose

Persistent structured memory.

Contains:

- workflows
- user preferences
- recurring tasks
- project context
- operational history
- learned patterns

---

## Characteristics

- embedding-indexed
- semantically retrievable
- compressed
- persistent

---

## Retrieval Method

Uses:

- embeddings
- vector search
- metadata ranking
- semantic similarity
- temporal relevance

---

## Example

```text id="1ih6cb"
"User usually validates spreadsheet changes before export."
```

---

# 4. Raw Archive

## Purpose

Unmodified historical storage.

Contains:

- raw logs
- full transcripts
- operational history
- debugging records

---

## Characteristics

- not injected directly into context
- low retrieval priority
- audit-focused
- fallback-oriented

---

## Purpose

Used for:

- debugging
- auditability
- manual recovery
- forensic tracing

---

# Memory Lifecycle

Memory flows through multiple stages.

---

# Step 1 — Capture

Input sources:

- conversations
- workflows
- screenshots
- files
- automation events
- tool outputs

---

# Step 2 — Chunking

Large content is segmented into chunks.

Chunking should preserve:

- semantic meaning
- workflow boundaries
- contextual continuity

Avoid arbitrary splitting.

---

# Step 3 — Compression

LLM2 performs:

- summarization
- abstraction
- operational distillation

Purpose:
reduce context load while preserving meaning.

---

# Step 4 — Metadata Tagging

Memory entries receive metadata.

Examples:

- timestamp
- workflow type
- source
- project
- importance score
- trust level
- related skills

---

# Step 5 — Embedding Generation

Semantic embeddings generated for:

- retrieval
- ranking
- contextual matching

Embedding providers should remain modular.

---

# Step 6 — Storage

Stored into:

- vector DB
- relational DB
- archive storage
- custom memory layer

The orchestration layer remains provider-agnostic.

---

# Step 7 — Retrieval

Relevant memory retrieved dynamically based on:

- current task
- workflow similarity
- semantic similarity
- recent activity
- active project

Only relevant memories enter orchestrator context.

---

# Memory Retrieval Philosophy

The runtime should retrieve:

- minimal sufficient context

NOT:

- maximal possible context

---

# Retrieval Goals

The memory system should optimize for:

- relevance
- clarity
- low noise
- contextual usefulness

NOT:

- retrieval quantity

---

# Retrieval Ranking Factors

Memory ranking may consider:

- semantic similarity
- recency
- workflow relevance
- importance score
- user frequency
- project relevance

---

# Memory Query Example

```text id="qspc0t"
"Find previous Shopify CSV workflow."
```

The runtime should retrieve:

- compressed workflow summary
- related actions
- relevant operational context

NOT:

- full unrelated conversations

---

# Importance Scoring

Each memory should receive an importance score.

Examples:

- trivial conversation → low importance
- repeated workflow → high importance
- user preference → high importance
- temporary error log → low importance

---

# Retention Policies

Different memory types require different retention behavior.

---

## Temporary

Examples:

- transient UI states
- temporary logs

May expire quickly.

---

## Session

Examples:

- active workflows
- current project context

May persist days/weeks.

---

## Long-Term

Examples:

- recurring workflows
- user preferences
- project knowledge

Persist indefinitely unless removed.

---

# Forgetting Philosophy

Nexux should support forgetting.

Reasons:

- reduce noise
- improve retrieval quality
- reduce memory pollution
- improve relevance

Memory should not grow infinitely.

---

# Memory Pollution Prevention

The runtime should avoid storing:

- excessive logs
- repetitive noise
- meaningless outputs
- failed retries spam
- duplicate summaries

Compression and filtering are mandatory.

---

# Workflow Memory

Operational workflows should become memory entities.

Examples:

- spreadsheet automation patterns
- browser workflows
- recurring admin tasks
- coding assistance flows

The system should gradually develop:

- reusable operational knowledge

---

# Episodic vs Semantic Memory

Nexux should distinguish:

---

## Episodic Memory

Specific events.

Example:

```text id="9ktp9h"
"User updated Shopify inventory yesterday."
```

---

## Semantic Memory

Generalized knowledge.

Example:

```text id="0y4d8o"
"User frequently works with Shopify CSV imports."
```

Both types are valuable.

---

# Memory Providers

Memory systems remain modular.

Possible providers:

- ChromaDB
- Qdrant
- SQLite/Postgres
- custom memory engine

The orchestration layer should never tightly couple to a provider.

---

# Memory Contracts

The orchestrator interacts with memory through:

- structured retrieval contracts
- structured storage contracts
- provider-independent APIs

The orchestrator should never directly manipulate vector databases.

---

# Memory Observability

The runtime should expose:

- retrieved memories
- why memories were retrieved
- ranking scores
- compression summaries
- retention decisions

The system should avoid hidden memory injection.

---

# Memory Failure Handling

If memory retrieval fails:

- continue operation safely
- avoid hallucinated recall
- request clarification if needed

The assistant should never pretend to remember something it failed to retrieve.

---

# Memory Privacy Philosophy

Memory remains:

- local-first
- user-controlled
- permission-aware

Sensitive workflows should avoid unnecessary cloud exposure.

---

# Memory Non-Goals

Nexux memory is NOT:

- infinite perfect recall
- unrestricted surveillance
- hidden behavioral profiling
- uncontrolled data hoarding

The goal is:

- useful operational cognition
- contextual assistance
- workflow continuity

NOT:

- endless storage accumulation

---

# Long-Term Memory Vision

Over time, Nexux develops:

- operational familiarity
- workflow awareness
- project continuity
- contextual intelligence

The assistant gradually becomes:

- more personalized
- more operationally efficient
- more contextually aware

without requiring:

- infinite context windows
- constant replay
- massive token usage

---

# Final Memory Philosophy

Nexux memory should behave like:

```text id="5u65pb"
Contextual Cognitive Recall
```

NOT:

```text id="epm3jp"
Infinite Chat Transcript Replay
```

The system prioritizes:

- relevance
- compression
- retrieval quality
- operational usefulness
- memory discipline

over:

- endless storage
- raw historical replay
- uncontrolled context growth

```

```
