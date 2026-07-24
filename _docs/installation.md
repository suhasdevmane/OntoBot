---
layout: post
title: Installation
date: 2025-09-28
---

# Installation

## Prerequisites

- Docker Desktop (Windows/macOS) or Docker Engine (Linux)
- Optional: Python 3.9+ for local utilities

## Bring up the stack

From the repository root:

```powershell
docker-compose up -d
```

Stop:

```powershell
docker-compose down
```

Rebuild a service (example: microservices):

```powershell
docker-compose up microservices --build
```

## Health checks

- Analytics: http://localhost:6001/health
- Rasa: http://localhost:5005/version
- Action server: http://localhost:5055/health
- Duckling: http://localhost:8000/
- File server: http://localhost:8080/health
- Jena Fuseki: http://localhost:3030/$/ping

## Optional local Python env

```powershell
python -m venv ./.abacws-venv
./.abacws-venv/Scripts/Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```
