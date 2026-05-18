"""
JORINOVA NEXUS ALIS-X — Modular AI Services Package
====================================================
Priority stack (offline-first):
  1. Rules Engine   → always available, deterministic, zero-latency
  2. Local LLM      → Ollama (Phi/Mistral), CPU-capable, offline
  3. Cloud LLM      → Claude, enhancement only, graceful degradation
  4. Speech Service → Whisper local STT
  5. Vision Service → async-queued image analysis

All services are lazy-loaded. Nothing runs unless called.
"""
