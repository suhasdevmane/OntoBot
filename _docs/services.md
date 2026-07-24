---
layout: post
title: Services
date: 2025-09-28
---

# Services

## Analytics Microservices

- Base: http://localhost:6001
- Endpoints: `/health`, `/analytics/run`
- Accepts flat or nested payloads; returns results with `unit` and UK defaults
- See repo: `microservices/README.md`

## Rasa Stack

- Rasa (5005); Action Server (5055); Duckling (8000)
- Editor (6080) and Frontend (3000)
- Actions build payloads, call Decider/Analytics, and format replies
- See repo: `rasa-ui/README.md` and `rasa-ui/actions/README.md`

## Decider Service

- Base: http://localhost:6009
- POST `/decide` → `{perform_analytics, analytics}`
- Helps choose `analysis_type` based on the question
- See repo: `decider-service/README.md`

## Visualiser & API (optional)

- Visualiser (8090) and API (8091) as an independent dashboard
- See repo: `Abacws/visualiser/README.md` and `Abacws/api/README.md`

## Transformers (optional)

- NL2SPARQL (6005) and Ollama (11434) for AI-driven helpers
- See repo: `Transformers/README.md`
