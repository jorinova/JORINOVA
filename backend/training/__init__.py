"""
JORINOVA NEXUS — Training toolkit
=================================
Day-one scaffolding for training, evaluating, and selecting AI models.

Layout
------
  extract.py            DB → JSONL extractors (one file per task)
  synthetic.py          Template-driven utterance/document synthesis
  golden/               Hand-curated eval sets (small, expensive truth)
  eval_intent.py        Score intent classifier vs golden set
  eval_lis_mapping.py   Score LIS field extractors vs golden OCR snippets
  benchmark_models.py   Per-worker latency + accuracy leaderboard

See ../../TRAINING.md for the one-day runbook.
"""
