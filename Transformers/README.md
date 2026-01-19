# Language & Translation Services (Transformers)

This directory contains language-oriented helper services that can plug into the broader OntoBot action pipelines. They provide:
1. Deterministic (or model‑based) NL → SPARQL translation for ontology + telemetry joins.
2. Local summarization / natural language post‑processing of analytics JSON and SPARQL results.

All runtime components in OntoBot are considered part of a flexible graph of pipelines; none is singled out as inherently “more core” than others. The Action Server can call these services when their corresponding features (translation or summarization) are desired.

Remote deployment note: Both `nl2sparql` and `ollama` can be hosted on separate machines or clusters. Simply set `NL2SPARQL_URL` and `SUMMARIZATION_URL` (e.g. to `http://translator.host:6005/nl2sparql` or `https://llm.gateway/api`) in the Action Server environment. If reachable over HTTP and following the expected request/response contract, the local containers for these services are not required.

---
## NL2SPARQL (T5)

- Purpose: Convert natural language questions into SPARQL queries.
- Service: `nl2sparql` on port 6005 (compose + extras overlay).
- Health: `GET /health`
- Model: `Transformers/t5_base/trained/checkpoint-3` (Download the files from Huggingface https://huggingface.co/suhasdevmane/nl2sparql-brick/tree/main or search repository suhasdevmane/nl2sparql-brick )
- Volume: Mount `Transformers/t5_base/trained/checkpoint-3` read‑only into container (see compose)
- ENV: `MODEL_PATH=/app/checkpoint-3`

If you omit this service, ensure the Action Server guards translation calls and either:
1) Falls back to a rule/template set of SPARQL queries, or
2) Routes the user toward intents that do not require dynamic SPARQL generation.

---
## Ollama (Mistral)

- Purpose: Summarization of SPARQL / analytics outputs, natural language refinement, and optional explanatory responses.
- Service: `ollama` on port 11434
- Health: root shows model list; use `ollama ps` inside container for process status
- GPU: Supported (comment out GPU section if running on CPU only)
- ENV recommendations:
	- `AUTO_PULL_MODELS=mistral:latest`
	- `WARMUP_MODELS=true` to pre‑generate tokens (reduces first‑response latency)

If disabled, set a flag (e.g., `DISABLE_SUMMARIZATION=true`) and ensure `actions.py` skips summarization stages gracefully (display raw metrics or structured JSON instead).

---
## Customize / Extend

- Swap checkpoints: adjust the mounted directory + `MODEL_PATH` env.
- Multiple translators: add additional services (e.g., `nl2sparql_large`) and implement a switching rule in the Action Server.
- Additional LLM runtimes: you can run a second `ollama` based model or integrate vLLM; keep the summarization contract stable.
- Healthchecks: Always add a `/health` endpoint for orchestrator stability.

---
## Feature Toggle Guidelines

If you run without one or both services:
| Skipped | Impact | Mitigation |
|---------|--------|------------|
| nl2sparql | No automated SPARQL generation | Provide template SPARQL or restrict intents |
| ollama | No NL summaries; raw JSON/stat numbers shown | Deterministic text assembly in Python |

Document intentional feature toggles in the main `README.md` if you maintain a minimal deployment profile.

---
## Quick Test Commands (PowerShell)
```powershell
curl http://localhost:6005/health
curl http://localhost:11434
```

---
**End of file**
