"""Service routers for the AI microservice scaffold."""
from . import health, ocr_stub, llm_stub

__all__ = ['health', 'ocr_stub', 'llm_stub']
