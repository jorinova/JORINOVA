# JORINOVA NEXUS — AI Training Runbook (Day 1)

This is the day-one training pipeline. It does NOT fine-tune model weights —
that needs GPU time you don't have today. What it DOES do, in one day:

1. Build a reusable dataset-extraction pipeline (DB → JSONL)
2. Run an eval harness with a hand-curated golden set
3. Score every Ollama worker on the same set and pick winners
4. Show you exactly where the system is wrong, by language and intent

After today, you'll know which models to fine-tune, on what data, against
what evals. That's the precondition for all later training.

## What lives where

```
backend/training/
├── extract.py             DB → JSONL (intent, lis_mapping, clinical)
├── synthetic.py           Template-driven utterance generator (en/fr/rw)
├── golden/
│   ├── intent_golden.jsonl       62 hand-curated examples
│   └── lis_mapping_golden.jsonl  10 OCR snippets w/ expected fields
├── eval_intent.py         Score the cascade (regex/local/cloud/auto)
├── eval_lis_mapping.py    Score the LIS extractors (DB-free)
└── benchmark_models.py    Per-worker Ollama leaderboard
```

## Prerequisites

```
cd backend
pip install -r requirements.txt        # one-time
# Optional but recommended for stages 3 & 4:
ollama serve                            # start Ollama daemon
ollama pull phi3:mini mistral nous-hermes llama3 tinyllama
```

If Ollama isn't running, the local/cloud/auto stages just SKIP — they don't
crash. You still get the regex baseline.

## The one-day pipeline

### Step 0 — Seed realistic pilot data (one time, ~5s)

```
cd backend
python scripts/seed_database.py                 # if you have not already
python scripts/seed_production_clinical.py      # 30 patients + 80 lab requests + results
```

`seed_production_clinical.py` builds a realistic week of a Rwandan district
hospital: real names + national IDs + districts, 10 clinical scenarios
(sepsis, anemia, ANC, diabetes follow-up, …), realistic value distributions
(70% normal / 20% mild abnormal / 10% critical) with proper flagging,
spread across pending/in-progress/validated/released so each downstream
task has real material to train on. Idempotent — re-running does not
duplicate. Use `--reset` to wipe the seeded rows and start over.

### Step 1 — Extract training data (5 s)

```
python scripts/extract_training_data.py                       # → /datasets/
```

Output (real numbers on the seeded DB):
- `intent.jsonl`        — 153 rows (synthetic en/fr/rw)
- `lis_mapping.jsonl`   —  80 rows (real LabRequests reverse-engineered to text)
- `ocr.jsonl`           — 240 rows (noisy/clean pairs for OCR-cleanup)
- `clinical.jsonl`      —  43 rows (validated/released requests with real values + flags)

### Step 2 — Build the golden truth files (one time)

```
python scripts/build_golden_set.py                            # → /golden_set/
```

Locks the per-language goldens that all evals score against:
- `golden_set/intent_en.json`  — 99 examples
- `golden_set/intent_fr.json`  — 50 examples
- `golden_set/intent_rw.json`  — 43 examples
- `golden_set/lis_mapping.json` — 10 OCR snippets
- `golden_set/ocr_samples.json` —  5 cleanup pairs

These are **locked truth** — do not let any script overwrite them. If you
disagree with a label, change the source `backend/training/golden/intent_golden.jsonl`
and re-run `build_golden_set.py`.

### Step 3 — Score the current system (no Ollama / no key needed)

```
python scripts/eval_intent.py --stage regex
python scripts/eval_lis_mapping.py --show-misses
```

Current scores on the production goldens:
- **Intent (regex)** : 192/192 = **100 %** (en 100 % · fr 100 % · rw 100 %)
- **LIS PID**        : 100 %
- **LIS family name** : 100 %
- **LIS priority**   : 100 %
- **LIS tests**      : F1 71 % (P 60 % / R 88 %)

### Step 4 — Benchmark the Ollama workers (optional, 10–60 min on CPU)

```
ollama serve                                       # in another terminal
python scripts/benchmark_models.py --out backend/training/benchmark.json
```

Each of the five workers (fast / deep / chat / general / fallback) runs the
full intent golden. You get latency p95 + accuracy per worker.

**Hardware reality check.** Loading a 4 GB Ollama model on a 4 GB-free CPU
laptop yields ~30 s per request — useless for live voice. On Rwandan
laptop-class hardware, regex + cloud Claude is the realistic cascade. Local
LLM only adds value with ≥ 8 GB free RAM and matters most on a GPU. See
`local_llm.py` — `num_ctx=2048` is forced so even phi3:mini fits in 3 GiB.

### Step 5 — Enable the cloud fallback (production cascade)

The cascade in `training_intent.classify()` is:
**regex → local Ollama → cloud Claude → unknown**

To turn on the cloud layer:

```
# In your .env (copy from .env.example):
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-haiku-4-5-20251001        # already the default
```

Then verify it works:

```
python scripts/eval_intent.py --stage cloud
python scripts/eval_intent.py --stage all     # full cascade leaderboard
```

Without the key, the cloud stage is silently skipped — no error, just no
fallback for anything the regex misses.

### Step 5 — Grow the golden set (continuous)

Every time the system misclassifies a real user utterance, append it to
`backend/training/golden/intent_golden.jsonl` with the correct label.
The eval harness will catch regressions next time anyone changes the
matcher or the prompts.

Rule of thumb: a useful golden set has at least 100 examples per task,
covering all intent classes and all supported languages. You're at 62 now.

## What this DOES NOT do (and the next steps that would)

This toolkit is the foundation. The actual model-training steps still
ahead:

1. **Real-data labeling** — replace synthetic intent corpus with
   transcribed pilot recordings (~2000 utterances). Without this, every
   model trained on synthetic data will overfit to template phrasing.
2. **OCR fine-tune** — needs ~500–2000 scanned lab request forms with
   field bounding boxes. Tooling: Tesseract `tesstrain` + LabelStudio.
3. **Whisper-rw fine-tune** — needs ~10–50h labeled Kinyarwanda audio.
   Tooling: HuggingFace `transformers` + a GPU.
4. **Local LLM LoRA fine-tune** — needs the labeled intent/LIS data
   above + GPU. Tooling: `unsloth` or `peft`, ~4–8h per epoch on a 24GB
   GPU. Output is an Ollama-importable Modelfile.

Each of those is a multi-week workstream. None of them are blockers for
running the system — the off-the-shelf models + the cascade are good
enough to pilot. They're how you get from "works in demo" to "reliable
in clinic."

## Commands cheat-sheet

| Command | Purpose | Needs Ollama |
|---|---|---|
| `python -m training.extract` | DB → JSONL | No (skips empty tasks) |
| `python -m training.synthetic` | Print synthetic intent corpus | No |
| `python -m training.eval_intent --stage regex` | Baseline accuracy | No |
| `python -m training.eval_intent --stage all` | Full cascade leaderboard | Yes (for local/cloud) |
| `python -m training.eval_lis_mapping --show-misses` | LIS extractor scoreboard | No |
| `python -m training.benchmark_models` | Per-worker model leaderboard | Yes |
| `python -m training.benchmark_models --model phi3:mini` | One model only | Yes |
