# Nexux by Klyx — Communication Contracts Specification

## Purpose

This document defines the communication standards between:

- orchestrator
- memory systems
- skills
- tools
- helper models
- cloud providers
- runtime services

The purpose of communication contracts is to:

- standardize runtime behavior
- prevent orchestration chaos
- reduce provider coupling
- improve observability
- simplify debugging
- make systems replaceable

Without communication contracts:

- outputs become inconsistent
- orchestration becomes fragile
- providers become tightly coupled
- debugging becomes extremely difficult

This document defines the internal language of Nexux.

---

# Core Philosophy

All runtime systems should communicate through:

- structured payloads
- deterministic schemas
- explicit metadata
- observable states

The runtime should avoid:

- raw unstructured responses
- provider-specific assumptions
- hidden reasoning formats
- inconsistent tool outputs

Every runtime interaction should be:

- machine-readable
- debuggable
- versionable
- extensible

---

# Contract Principles

## 1. Provider Agnostic

Contracts must not depend on:

- OpenAI formats
- Anthropic formats
- Ollama formats
- Chroma-specific responses

Internal runtime schemas remain stable even if providers change.

---

## 2. Human Observable

Contracts should remain readable by:

- developers
- debugging tools
- observability systems

Avoid opaque payloads whenever possible.

---

## 3. Explicit State

Every response should include:

- status
- timestamps
- source
- execution metadata
- error information

The runtime should avoid implicit assumptions.

---

## 4. Structured Failure Handling

Failures must return structured information.

Never return:

- silent failures
- ambiguous states
- incomplete execution metadata

---

# Core Runtime Payload Structure

All internal runtime payloads should follow a common structure.

---

## Base Event Schema

```json id="l6v5or"
{
  "event_id": "uuid",
  "event_type": "tool_execution",
  "source": "browser_skill",
  "timestamp": "ISO_TIMESTAMP",
  "session_id": "uuid",
  "task_id": "uuid",
  "status": "success",
  "payload": {},
  "metadata": {}
}
```

---

# Status Values

Allowed status values:

```text id="g0c2ut"
success
failure
partial_success
pending
cancelled
timeout
requires_permission
```

These values should remain standardized across all systems.

---

# Orchestrator Contracts (LLM1)

The orchestrator communicates with:

- memory
- tools
- skills
- permissions
- cloud providers

The orchestrator should NEVER directly parse:

- raw terminal output
- raw OCR dumps
- raw provider formats

All systems must return structured responses.

---

# Orchestrator Task Request Schema

```json id="4htrv8"
{
  "task_type": "browser_automation",
  "intent": "fill_form",
  "priority": "medium",
  "requires_memory": true,
  "requires_permission": true,
  "context": {},
  "user_input": ""
}
```

---

# Orchestrator Decision Response

```json id="1pn5sw"
{
  "decision": "invoke_skill",
  "selected_skill": "browser_skill",
  "reasoning_summary": "",
  "permission_level": "medium",
  "requires_cloud": false
}
```

The orchestrator should return:

- concise reasoning
- execution direction
- required permissions
- escalation requirements

---

# Memory System Contracts

The memory layer should remain independent from:

- vector database implementation
- embedding provider
- storage engine

The orchestrator interacts with memory through contracts only.

---

# Memory Query Request

```json id="4xjrf9"
{
  "query": "Shopify CSV workflow",
  "memory_scope": ["working_memory", "long_term_memory"],
  "top_k": 5,
  "session_id": "uuid"
}
```

---

# Memory Retrieval Response

```json id="3aj2nr"
{
  "status": "success",
  "results": [
    {
      "memory_id": "uuid",
      "summary": "",
      "relevance_score": 0.92,
      "timestamp": "",
      "source_type": "workflow_memory"
    }
  ]
}
```

---

# Memory Compression Contract (LLM2)

```json id="9m1qdt"
{
  "input_type": "conversation_chunk",
  "content": "",
  "compression_goal": "long_term_summary",
  "metadata": {}
}
```

---

# Memory Summary Response

```json id="3wqzme"
{
  "summary": "",
  "keywords": [],
  "embedding_required": true,
  "importance_score": 0.84,
  "retention_policy": "long_term"
}
```

---

# Tool Runtime Contracts

Tool execution must remain deterministic.

Tools should return:

- structured summaries
- explicit failures
- execution metadata

Never raw uncontrolled output directly to LLM1.

---

# Tool Execution Request

```json id="g6k4sp"
{
  "tool_name": "terminal",
  "command": "npm run build",
  "timeout_seconds": 60,
  "requires_permission": true,
  "sandboxed": true
}
```

---

# Raw Tool Response

```json id="cy4j0m"
{
  "execution_status": "failure",
  "exit_code": 1,
  "stdout": "",
  "stderr": "",
  "execution_time_ms": 2480
}
```

Raw tool responses should NOT directly enter orchestrator context.

---

# Tool Interpretation Contract (LLM3)

LLM3 converts noisy operational output into compressed semantic information.

---

# Tool Interpretation Request

```json id="u3wnsk"
{
  "tool_type": "terminal",
  "raw_output": "",
  "compression_goal": "extract_meaning"
}
```

---

# Tool Interpretation Response

```json id="ej8d5p"
{
  "summary": "Build failed because dependency is missing.",
  "important_errors": ["Cannot find package xyz"],
  "severity": "medium",
  "retry_recommended": false
}
```

---

# Skill Contracts

Skills are isolated operational modules.

Every skill should expose:

- metadata
- execution handler
- permissions
- validation rules

---

# Skill Metadata Contract

```json id="z7k5cw"
{
  "skill_name": "browser_skill",
  "version": "0.1.0",
  "description": "",
  "required_permissions": ["browser_access"],
  "supported_tasks": ["form_fill", "navigation"]
}
```

---

# Skill Execution Request

```json id="v9b2rq"
{
  "skill_name": "excel_skill",
  "task_type": "fill_empty_rows",
  "input_data": {},
  "execution_context": {}
}
```

---

# Skill Execution Response

```json id="3txihf"
{
  "status": "success",
  "summary": "24 rows updated.",
  "changes_preview": [],
  "requires_confirmation": true
}
```

---

# Permission Contracts

Permissions must remain explicit and structured.

---

# Permission Evaluation Request

```json id="v9sdz6"
{
  "action_type": "file_edit",
  "risk_level": "medium",
  "target_resource": "spreadsheet.xlsx"
}
```

---

# Permission Response

```json id="y7l6mo"
{
  "permission_required": true,
  "risk_category": "medium",
  "reason": "Spreadsheet modification detected."
}
```

---

# Vision Contracts

Vision systems process:

- screenshots
- OCR
- UI understanding
- PDFs

---

# Vision Request

```json id="0sn3ft"
{
  "input_type": "screenshot",
  "goal": "detect_form_fields"
}
```

---

# Vision Response

```json id="s1n7cq"
{
  "detected_elements": [
    {
      "type": "input_field",
      "label": "Email"
    }
  ],
  "confidence": 0.91
}
```

---

# Cloud Escalation Contracts

Cloud providers remain advisory cognition systems.

---

# Cloud Escalation Request

```json id="j8o2ke"
{
  "task_type": "advanced_debugging",
  "context_summary": "",
  "constraints": [],
  "privacy_level": "safe"
}
```

---

# Cloud Response

```json id="vdq3mr"
{
  "summary": "",
  "recommendations": [],
  "confidence": 0.88
}
```

---

# Failure Contracts

All failures must remain structured.

---

# Failure Response Schema

```json id="2pqy70"
{
  "status": "failure",
  "failure_type": "tool_execution_error",
  "summary": "",
  "retryable": true,
  "recommended_action": ""
}
```

---

# Retry Philosophy

Retries must remain bounded.

The runtime should avoid:

- infinite retries
- recursive retry chains
- uncontrolled self-correction loops

---

# Observability Metadata

Every contract should support observability.

Recommended metadata:

```json id="i2n5kb"
{
  "latency_ms": 120,
  "provider": "ollama",
  "model": "deepseek",
  "memory_tokens_used": 2048
}
```

---

# Event Correlation

All contracts should support:

- session tracking
- task tracking
- workflow tracking

Required IDs:

- session_id
- task_id
- event_id

This enables:

- debugging
- observability
- replay systems
- auditability

---

# Contract Versioning

Contracts must support versioning.

Example:

```json id="bmyxgz"
{
  "contract_version": "1.0"
}
```

Breaking schema changes should increment contract versions.

---

# Runtime Communication Philosophy

Nexux communication should behave like:

```text id="ptk0cc"
Structured Cognitive Infrastructure
```

NOT:

```text id="9i0k5t"
LLMs passing random text blobs endlessly
```

The runtime should remain:

- deterministic
- observable
- modular
- debuggable
- provider-independent

at every layer.

---

# Final Principle

Every system inside Nexux should communicate through:

- structured intent
- explicit state
- compressed meaning
- observable execution

The runtime should prioritize:

- operational clarity
- orchestration discipline
- predictable cognition

over:

- uncontrolled emergent behavior
- hidden reasoning chains
- chaotic autonomous interactions

```

```
