# JORINOVA NEXUS — AI Microservice (scaffold)

This directory is the future home of the AI inference microservice, designed
to be split out of the monolithic `backend/ai_services/` when load or model
size demands a separate container.

## Current state

Scaffold only. The live AI services are still inside
[../backend/ai_services/](../backend/ai_services/) and serve all traffic
through the main FastAPI app at `:8000`.

## Layout

```
ai_microservice/
├── main.py           # FastAPI entrypoint (placeholder)
├── models/           # Pydantic request / response schemas
├── services/         # Inference pipelines (OCR, LLM routing, vision, …)
└── utils/            # Shared helpers (logging, metrics, model loaders)
```

## When to split it out

Promote this scaffold to a running service when **any** of the following
become true:

- Local LLM inference (`ollama`, whisper) consistently exceeds 80 % CPU
  on the API host
- A second host with GPU access is provisioned for vision / OCR
- Multiple deployments share the same model artifacts
- The AI layer needs an independent release cadence from the core LIS

## Split checklist (for the future)

1. Pin the `ai_services` interfaces in `backend/ai_services/__init__.py` so
   monolith callers can switch between in-process and remote.
2. Move heavy code (model loads, GPU init) into `ai_microservice/services/`.
3. Add a Docker image: `ai_microservice/Dockerfile`.
4. Update `docker-compose.yml` to add a `nexus-ai` service.
5. Add HTTP client shims in `backend/ai_services/` that proxy to the new
   microservice when an `AI_MICROSERVICE_URL` env var is set.

Until then, treat this directory as documentation + an empty contract.
