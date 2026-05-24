"""
JORINOVA NEXUS — AI Microservice entrypoint (scaffold)

This is a placeholder FastAPI app meant to become the standalone AI
inference service when the monolith is split. Today it is NOT mounted by
docker-compose.yml and not part of the runtime.

To bring it online later:
    uvicorn ai_microservice.main:app --host 0.0.0.0 --port 8100

See ../README.md for the split checklist.
"""
from __future__ import annotations

from fastapi import FastAPI

from ai_microservice.services import health, ocr_stub, llm_stub

app = FastAPI(
    title='JORINOVA NEXUS — AI Microservice',
    version='0.1.0-scaffold',
    description='Future home of AI inference workloads. Not yet active.',
)

app.include_router(health.router,    prefix='/v1')
app.include_router(ocr_stub.router,  prefix='/v1')
app.include_router(llm_stub.router,  prefix='/v1')


@app.get('/', include_in_schema=False)
def root() -> dict:
    return {
        'service':  'jorinova-nexus-ai',
        'status':   'scaffold',
        'message':  'See README.md before promoting this to a running service.',
    }
