# JORINOVA NEXUS — What the AI knows and doesn't

Honest answer to the question "do the local models know medical
terminology, staining methods, mycology, parasitology, histotechnology,
immunology, organs, tissues, cells, pathophysiology?"

## Short answer

Off-the-shelf `phi3:mini`, `mistral`, `llama3`, `nous-hermes` and
`tinyllama` are **book-smart generalists with first-year-medical-student
depth**. They know the common framework. They do NOT know lab-grade
detail — and they will sound confident while inventing it.

Don't trust them on:
- Specific staining steps and reagents
- Exact critical/panic values
- Reference ranges for any specific test
- Rwandan abbreviations (GE, FS, PTME, RBC)
- Parasitology species details
- Mycology specifics (CHROMagar colours, media compositions)
- Rejection rules and SOPs

Do trust them on (when paired with RAG):
- Common abbreviations explanations (CBC, TB, HIV)
- Major-organ pathophysiology framework
- Test category buckets (hematology vs biochemistry)
- Natural-language paraphrasing of provided facts

## How we proved it — the probe

```bash
cd backend
python -m training.probe_medical                       # all 5 workers
python -m training.probe_medical --model phi3:mini      # one model
python -m training.probe_medical --only stain,parasit   # filter domains
python -m training.probe_medical --detail               # show wrong answers
```

Runs 27 fixed questions across 9 domains (abbrev, stain, parasit, mycol,
critical, ref, tube, immuno, histo) and grades each answer against the
ground truth in [`medical_knowledge.py`](backend/ai_services/medical_knowledge.py).

Grades:
- **CORRECT** — answer contains every must-have keyword
- **PARTIAL** — some keywords; the right shape, wrong detail
- **WRONG**   — direct contradiction (a hallucinated number, a wrong colour)
- **REFUSED** — model said it didn't know (preferred over WRONG)

## How we fixed it — RAG (no fine-tuning needed)

Your repo already ships [`backend/ai_services/medical_knowledge.py`](backend/ai_services/medical_knowledge.py) — 783 lines of:
- ~250 abbreviations (lab, disease, ward, Rwandan)
- ~30 staining methods with reagents, steps, expected results, clinical
  interpretation
- Culture media with selectivity, incubation, expected colonies
- Critical / panic values per test
- Reference ranges by age and sex
- Tube colour mapping
- Rejection guidance

That IS your training data. The new bridge is
[`backend/ai_services/medical_rag.py`](backend/ai_services/medical_rag.py):

```python
from ai_services.medical_rag import answer_with_kb
resp = await answer_with_kb('what colour does Candida albicans appear on CHROMagar?')
print(resp.content)
# → "On CHROMagar, Candida albicans appears GREEN."
# resp.metadata['kb_chunks'] = [{'kind':'STAIN', 'key':'CHROMAGAR'}, ...]
```

How it works per inference:
1. Tokenise the user's question (drop stop-words)
2. Score every KB chunk by keyword overlap
3. Inject the top-K matching chunks into the system prompt
4. Generate with `local_llm.generate` (or via the router)

Why this beats fine-tuning for you right now:
- **No GPU needed.** Runs on the same CPU Ollama is already using.
- **Updates are instant.** Edit `medical_knowledge.py`, the next query
  uses the new facts.
- **Auditable.** `resp.metadata['kb_chunks']` shows exactly which
  source rows produced the answer. A clinician can trace every claim.
- **Beats fine-tuning on this size of data.** 783 lines of curated
  knowledge is too small to teach a 4B-parameter model anything new
  reliably; it IS plenty for retrieval.

## Domains we still don't cover (honest gap list)

| Domain | Status today | What it would take |
|---|---|---|
| Lab abbreviations | Curated in `MEDICAL_ABBREVIATIONS` | — done — |
| Staining methods | Curated in `STAINING_METHODS` | — done — |
| Bacterial culture media | Partial coverage | Add 10-15 more entries (~2h) |
| Parasitology species detail | Names only | Add per-species chunks (~4h) |
| Mycology specifics | Partial | Extend CHROMagar + Sabouraud sections (~2h) |
| Histotechnology workflow | Stains only | Add fixation / processing / embedding (~6h) |
| Pathophysiology / Robbins-level disease detail | Not in KB | Long-form — best handled by Claude cascade |
| Organ / tissue / cell anatomy | Not in KB | RAG over an open anatomy text (~1 day to ingest) |
| Drug interactions | Not in KB | Use Claude cascade — too much to maintain in-house |

## Realistic training program (priority order)

1. **Run the probe** — get a real baseline number, not a vibe.
2. **Expand `medical_knowledge.py`** in the order above. Every entry you
   add is instantly retrievable — no retrain, no rebuild. Two hours of
   curation is worth more than a week of fine-tuning right now.
3. **Wire `answer_with_kb` into the orchestrator** as a new task type
   (e.g. `KNOWLEDGE_QUERY`). Today it's a library function; routing it
   into the `/api/v1/ai/...` surface makes it visible to the front end.
4. **Add Claude cascade for long-form pathophysiology** — those
   questions don't belong in a curated KB; they belong in a cloud LLM
   that already has Robbins, Harrison and Bates in its weights. Add
   `ANTHROPIC_API_KEY` to backend/.env to unlock.
5. **Fine-tune later, only if needed.** After 4-6 weeks of pilot use,
   look at the questions the cascade is still getting wrong. If a
   pattern emerges, THEN fine-tune Phi-3 or Mistral on those examples
   (see [notebooks/intent_finetune_colab.ipynb](notebooks/intent_finetune_colab.ipynb) for the template).

## Reproduce in 60 seconds

```bash
cd backend

# 1. Measure baseline knowledge
python -m training.probe_medical

# 2. Show how RAG bridges the gap (single question)
python -c "
import asyncio
from ai_services.medical_rag import answer_with_kb, chunk_count
print(f'KB chunks indexed: {chunk_count()}')
r = asyncio.run(answer_with_kb('what colour is C. albicans on CHROMagar?'))
print(r.content)
print('cited:', r.metadata.get('kb_chunks'))
"
```
