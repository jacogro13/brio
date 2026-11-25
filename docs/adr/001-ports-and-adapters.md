# ADR-001: Ports and adapters (hexagonal) architecture

**Status**: Accepted  
**Date**: 2026-05-14

## Context

The app needs to swap the LLM backend (Ollama today, potentially something else tomorrow) without rewriting business logic. It also needs testable services that don't require a live database or network.

## Decision

Use hexagonal / ports-and-adapters architecture:

- `domain/` contains pure Python entities and abstract ports (ABCs). Zero framework deps.
- `adapters/` contains concrete implementations of ports (Postgres, OpenAI-compatible HTTP, mock).
- `services/` contains use cases that depend only on ports — never on concrete adapters.
- `entrypoints/` wires everything together via FastAPI `Depends`.

The **rich form** (BLUEPRINT §3b) is used because two adapter kinds (persistence + LLM) are present from day one, and LLM calls are async with streaming.

## Consequences

- Swapping the LLM adapter requires changing one env-var guard in `dependencies.py` and writing a new adapter class.
- Unit tests can use `MockLLMAdapter` and SQLite in-memory without any Docker dependency.
- The layering rule (outer imports inner, never reverse) must be enforced — linters or code review catch violations.
