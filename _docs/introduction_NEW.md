---
layout: post
title: OntoBot Introduction
date: 2025-09-28
---

# OntoBot: Talking Buildings

OntoBot is a modular platform for human–building interaction in natural language. It combines:

- A Rasa-based conversational layer (NLU + Actions)
- An analytics microservice for time-series sensor data
- Knowledge stores (MySQL for telemetry, Jena Fuseki for SPARQL)
- Optional AI helpers (NL2SPARQL, local LLM via Ollama)
- A frontend chat UI and optional 3D visualiser/API

The goal: enable occupants and operators to ask questions like “What’s the CO2 in room 2.11?” or “Are there anomalies in HVAC today?” and receive clear, unit-aware answers with sensible defaults (UK indoor guidelines) and data-backed artifacts.

Key features:

- Standardized payloads from actions to analytics (flat or nested)
- Robust key matching and timestamp normalization
- UK-oriented thresholds/units in responses
- Health checks and a smoke test for end-to-end validation

Next, see Setup, Services, and Customization for new buildings.

