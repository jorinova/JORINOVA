# JORINOVA NEXUS — AI Training Baseline

Locked numbers as of the latest pipeline run. Re-run any script below and
the same scores should reproduce on the same seeded data.

## Pipeline scoreboard

| Task                 | Metric         | Score  | Where                                          |
| -------------------- | -------------- | ------ | ---------------------------------------------- |
| Intent (regex)       | accuracy       | **100 %** (192/192) | `python scripts/eval_intent.py --stage regex`  |
| Intent — English     | accuracy       | **100 %**           | per-language breakdown in the same eval        |
| Intent — French      | accuracy       | **100 %**           | "                                              |
| Intent — Kinyarwanda | accuracy       | **100 %**           | "                                              |
| LIS — patient PID    | accuracy       | **100 %** (5/5)     | `python scripts/eval_lis_mapping.py`           |
| LIS — family name    | accuracy       | **100 %** (10/10)   | "                                              |
| LIS — gender         | accuracy       | **100 %** (9/9)     | "                                              |
| LIS — national ID    | accuracy       | **100 %** (2/2)     | "                                              |
| LIS — priority       | accuracy       | **100 %** (10/10)   | "                                              |
| LIS — tests          | F1 (P / R)     | **100 %** (P 100, R 100) | tp 36, fp 0, fn 0                         |

## Dataset sizes (extracted from the seeded pilot DB)

| File                                | Rows | Notes                                   |
| ----------------------------------- | ---- | --------------------------------------- |
| `datasets/intent.jsonl`             | 153  | synthetic en / fr / rw utterances       |
| `datasets/lis_mapping.jsonl`        | 80   | one row per real LabRequest             |
| `datasets/ocr.jsonl`                | 240  | noisy/clean pairs from the same forms   |
| `datasets/clinical.jsonl`           | 43   | validated/released requests + results   |

Golden sets (locked truth):
- `golden_set/intent_en.json`   — 99 rows
- `golden_set/intent_fr.json`   — 50 rows
- `golden_set/intent_rw.json`   — 43 rows
- `golden_set/lis_mapping.json` — 10 rows
- `golden_set/ocr_samples.json` —  5 rows

## What this 100 % means — and what it does NOT

Means:
- Regex + the rule-based LIS extractor cover **every example in our
  curated goldens** with no false positives and no false negatives.
- Adding a new utterance / form variant the regex doesn't yet handle
  will surface immediately as a miss and become the next bug to fix.

Does NOT mean:
- The system handles every utterance a real user might say. The golden
  is broad (192 examples, 3 languages, polite/imperative/code-switching
  forms) but cannot cover the long tail. The fallback is the cloud
  LLM cascade.
- The LIS extractor handles every form layout. Real OCR'd photos with
  rotation, glare, handwriting and bad ink will need either better OCR
  or a fine-tuned model.

## The cloud cascade (already wired, awaiting key)

Cascade in `training_intent.classify()`:
**regex → local Ollama → cloud Claude → unknown**

- Regex handles everything in the golden today (100 %).
- Local Ollama runs `phi3:mini` etc. — too slow on 4 GB free RAM,
  recommended only on hosts with 8 GB+ free or a GPU.
- Cloud Claude (`claude-haiku-4-5-20251001` by default) is the
  fallback for anything regex misses. Activate by setting
  `ANTHROPIC_API_KEY` in `backend/.env`.

In DEBUG mode + no SMTP, the OTP endpoint also echoes the code in
its response — useful for testing the password-reset UX without
configuring an email provider.

## To go from 'baseline' to 'fine-tuned model'

The pipeline above is the **data layer**. Fine-tuning a local model on
top of it requires GPU. Three realistic paths in priority order:

### A. Google Colab — Phi-3 LoRA fine-tune (recommended)
Use `notebooks/intent_finetune_colab.ipynb` (committed alongside this
file). Upload to Colab, attach a T4 (free tier), runtime ~30 min for
one epoch on the 153 intent examples + 30 % held-out eval. Exports an
Ollama-compatible `Modelfile` you can `ollama create` on your laptop.

### B. Anthropic Claude — synthetic clinical interpretations
With `ANTHROPIC_API_KEY` set, generate gold interpretations for the
43 `clinical.jsonl` rows. Run:

```bash
python scripts/generate_interpretations_with_claude.py   # to-be-added
```

The output is a `clinical_with_interp.jsonl` that becomes the
training set for a later clinical-interpretation fine-tune.

### C. RAG over medical_knowledge.py
The `medical_knowledge.py` module (783 lines of hand-curated content)
is already in the repo. Index it into a vector store so the cloud
cascade has retrieval-augmented context — no model training needed,
just retrieval. ChromaDB or a simple BM25 index will do.

## Reproduce these scores

Fresh checkout:
```bash
cd backend
python scripts/seed_database.py
python scripts/seed_operational.py
python scripts/seed_production_clinical.py

python scripts/extract_training_data.py     # → /datasets/
python scripts/build_golden_set.py          # → /golden_set/
python scripts/eval_intent.py --stage regex
python scripts/eval_lis_mapping.py
python services/test_production_core.py     # 21/21 production smoke
```

All four output files should match this document.
