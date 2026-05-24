# JORINOVA NEXUS — Colab Training Playbook

Buri "track" ni capability imwe ya AI. Per track:

- **WHAT** — exactly what the model learns to do
- **WHO uses it** — which scene / endpoint will consume it
- **DATA — files you upload to Colab**
  | File name | Path in repo | What's in it | Rows |
  |---|---|---|---|
- **MODEL** — which base model to fine-tune / use
- **GPU** — what tier (free T4 / paid A100 / CPU only)
- **TIME** — rough estimate
- **STATUS** — ready to go today / needs data prep / blocked
- **WHAT YOU GET BACK** — the artefact you bring back to the laptop

The first three tracks are **ready today**. Tracks 4–8 need a bit of
prep work first.

---

## TRACK 1 — Intent classifier (LANGUAGES, voice commands)

**WHAT**: classify a spoken transcript (en / fr / rw) into one of 11
intents: `start, next, pause, resume, restart, stop, greet, wake, help,
thanks, unknown`.

**WHO uses it**: the training-runner voice commands (`Jorinova next`,
`komeza`, etc.) — fallback when the regex matcher misses.

**DATA — upload these two files to Colab**:

| File | Path in repo | What | Rows |
|---|---|---|---|
| `intent.jsonl` | `datasets/intent.jsonl` | synthetic en/fr/rw utterances per intent | 153 |
| `intent_golden.jsonl` | `backend/training/golden/intent_golden.jsonl` | hand-curated locked eval set | 192 |

**MODEL**: `microsoft/Phi-3-mini-4k-instruct` + LoRA (rank 8)

**GPU**: free T4 (Colab default)

**TIME**: ~30 min for 2 epochs

**STATUS**: ✅ **READY** — notebook already in repo

**NOTEBOOK**: [`notebooks/intent_finetune_colab.ipynb`](notebooks/intent_finetune_colab.ipynb)

**GOAL**: ≥ 95 % accuracy on the locked golden. Today the regex baseline
is 100 %; the model is the fallback for novel phrasing.

**WHAT YOU GET BACK**: an Ollama `Modelfile` + the fine-tuned weights.
Run `ollama create jorinova-intent -f Modelfile` then set
`OLLAMA_MODEL_CHAT=jorinova-intent` in `backend/.env`.

---

## TRACK 2 — LIS auto-mapping (PARAMETERS, OCR'd forms)

**WHAT**: read raw OCR'd lab-request text → extract patient PID,
family name, gender, priority, and the list of tests.

**WHO uses it**: `/modules/lis_mapping` page. Today's regex-based
extractor scores 100 % on the golden — but only for forms that look
like the templates. The model adds robustness to layout variation.

**DATA**:

| File | Path | What | Rows |
|---|---|---|---|
| `lis_mapping.jsonl` | `datasets/lis_mapping.jsonl` | real LabRequests reverse-engineered to text | 80 |
| `lis_mapping_golden.jsonl` | `backend/training/golden/lis_mapping_golden.jsonl` | hand-curated locked eval | 10 |

**MODEL**: `google/flan-t5-base` — text-to-structured-text is the
natural T5 task; better than Phi-3 for this.

**GPU**: free T4

**TIME**: ~45 min for 3 epochs

**STATUS**: ⏳ **needs notebook** — I'll write
`notebooks/lis_finetune_colab.ipynb` if you green-light this track.

**GOAL**: ≥ 95 % F1 on test extraction across novel form layouts (where
the regex breaks).

**WHAT YOU GET BACK**: an HF model directory. Wrap in a FastAPI route
or convert to ONNX for inference. The regex stays as the fast path;
the model handles "weird forms" the regex rejects.

---

## TRACK 3 — OCR cleanup (LANGUAGES + PARAMETERS)

**WHAT**: noisy OCR text (typos, broken line breaks, character drift like
`l→1`, `O→0`, `B→8`) → clean canonical text.

**WHO uses it**: every OCR pipeline (`document_reader.py`,
`ocr_service.py`). Replaces the current "trust Tesseract output as-is"
step.

**DATA**:

| File | Path | What | Rows |
|---|---|---|---|
| `ocr.jsonl` | `datasets/ocr.jsonl` | (noisy, clean) pairs from real DB rows + synthesised noise | 240 |
| `ocr_samples.json` | `golden_set/ocr_samples.json` | hand-curated noisy/clean eval | 5 |

**MODEL**: `google/byt5-small` — byte-level is the right choice for
character-error correction (Tesseract errors are at the character
level, not token).

**GPU**: free T4

**TIME**: ~40 min for 2 epochs

**STATUS**: ⏳ **needs notebook**

**GOAL**: ≥ 90 % character-accuracy on noisy inputs, with no
hallucinated text on already-clean inputs.

**WHAT YOU GET BACK**: HF model directory. Plug into
`ocr_service.py` as a post-processing step after Tesseract.

---

## TRACK 4 — Clinical interpretation (PARAMETERS, language)

**WHAT**: given a lab panel (results + flags + diagnosis) → write a
2-3 sentence clinical interpretation.

**WHO uses it**: the "Interpret" button on a released LabRequest;
`AI Nexus` module.

**DATA**:

| File | Path | What | Rows |
|---|---|---|---|
| `clinical.jsonl` | `datasets/clinical.jsonl` | request + results, **interpretation field empty** | 43 |

**PREP REQUIRED — this track is gated on labelling first**:
1. Add `ANTHROPIC_API_KEY` to `backend/.env`
2. Run (script to write):
   ```bash
   python scripts/generate_interpretations_with_claude.py
   ```
3. Output: `datasets/clinical_with_interp.jsonl` (43 rows × 1 paragraph each)
4. THEN fine-tune

**MODEL**: `microsoft/Phi-3-mini-4k-instruct` + LoRA, or `mistralai/Mistral-7B-Instruct`

**GPU**: free T4 for Phi-3; needs paid A100/L4 for Mistral

**TIME**: ~30 min Phi-3, ~2 h Mistral

**STATUS**: 🔧 **needs Claude bootstrap step first**

**GOAL**: produce interpretations that match Claude's quality at ≥ 80 %
similarity (BLEU / ROUGE-L), so the lab can run interpretation offline.

**WHAT YOU GET BACK**: Modelfile + weights. The cloud stage becomes
optional once this model exists.

---

## TRACK 5 — Kinyarwanda TTS / voice synthesis (VOICE)

**WHAT**: text → Kinyarwanda audio (the "Jorinova" voice the system
already uses, but **dedicated**, not the browser default).

**WHO uses it**: the training-runner voice narrator on every demo
scene. Today: browser Web Speech API (uses whatever the OS provides).

**DATA — you don't have it yet**:

| File | Path | What | Rows |
|---|---|---|---|
| (none) | — | Kinyarwanda speech corpus needed | 0 |

**PREP — three honest options**:

1. **Mozilla Common Voice rw** (free, open) — ~30 h Kinyarwanda
   recordings, already aligned. Sufficient for a basic voice.
   Download: https://commonvoice.mozilla.org/en/datasets
2. **Record your own** — 100-500 sentences read aloud by 2-3 speakers
   gives a clean, controlled corpus. Days of work but the best quality.
3. **Skip and pay** — use OpenAI / ElevenLabs / Google TTS Kinyarwanda
   if/when they offer it commercially.

**MODEL**: `coqui-ai/XTTS-v2` (multilingual TTS, supports voice cloning
with 6 s of reference audio) — the fastest realistic path.

**GPU**: T4 for inference, A100 for fine-tuning from scratch

**TIME**: 2-3 hours for XTTS voice clone fine-tune; full retrain
takes days

**STATUS**: 🚧 **blocked on audio data**

**GOAL**: 24 kHz natural-sounding Kinyarwanda voice that says the
training scene narration without relying on the browser.

**WHAT YOU GET BACK**: a `.pth` checkpoint + an inference script. The
frontend swaps from Web Speech API to your own `/api/v1/tts/synthesise`
endpoint.

---

## TRACK 6 — Kinyarwanda speech recognition (VOICE + LANGUAGES)

**WHAT**: spoken Kinyarwanda → transcribed text (so users can say
`tangira`, `komeza`, `hagarara` and have the system understand).

**WHO uses it**: the voice-command mic in the training runner.
Currently uses the browser's built-in SpeechRecognition, which is
weak on Kinyarwanda (English/French OK).

**DATA**:

| File | Path | What | Rows |
|---|---|---|---|
| Common Voice rw `clips/*.mp3` | (download to Colab) | 16 kHz Kinyarwanda recordings + transcripts | ~30 000 |

**MODEL**: `openai/whisper-small` (244 M params) fine-tuned on
Kinyarwanda. Whisper is already pretrained on rw — fine-tuning just
specialises.

**GPU**: T4 works for small, A100 ideal for medium

**TIME**: ~4-6 hours on T4 for whisper-small

**STATUS**: 🚧 **blocked on Common Voice download**

**GOAL**: WER (word error rate) ≤ 25 % on a held-out Kinyarwanda set.
Whisper-large gets ~18 % out of the box; we want a smaller model that
runs offline at the lab.

**WHAT YOU GET BACK**: HF model. Drop into a FastAPI endpoint at
`/api/v1/stt/transcribe` and the frontend swaps from browser
SpeechRecognition to your own STT.

---

## TRACK 7 — Vision: cells / parasites / fungi (IMAGES)

**WHAT**: classify a microscope slide image into:
- Malaria positive / negative (per Plasmodium species)
- TB AFB positive / negative
- Cryptococcus + / -
- Cancer slide grading (Pap, breast, prostate)

**WHO uses it**: a new module `/modules/microscopy` that lets a tech
upload a slide photo and get an AI suggestion.

**DATA — public datasets, not in your repo yet**:

| Dataset | Source | What | Images |
|---|---|---|---|
| NIH Malaria | https://lhncbc.nlm.nih.gov/LHC-research/LHC-projects/image-processing/malaria-datasheet.html | thin-smear cell crops, parasitized vs uninfected | 27 558 |
| BCCD | https://github.com/Shenggan/BCCD_Dataset | blood cell classification, multi-class | 364 |
| PCAM | https://github.com/basveeling/pcam | breast cancer patches, 96×96 | 327 680 |
| Kather colon | https://zenodo.org/record/53169 | colorectal tissue, 8 classes | 5 000 |
| ChestX-ray14 | https://nihcc.app.box.com/v/ChestXray-NIHCC | chest X-ray, 14 conditions | 112 120 |

**MODEL**: `microsoft/resnet-50` or `google/vit-base-patch16-224`
fine-tuned per task. Multi-label heads.

**GPU**: T4 works; A100 cuts time by 5×

**TIME**: 1-2 hours per task

**STATUS**: 🚧 **needs dataset download + per-task notebook**

**GOAL**:
- Malaria: ≥ 95 % accuracy (achievable; published benchmarks ~97 %)
- TB AFB: ≥ 90 %
- Cryptococcus: small dataset, set a realistic baseline first
- Cancer grading: tricky — start with binary (cancer / no cancer) before
  multi-class grading. The honest pitch in any tournament: *"AI-assisted
  screening, not diagnosis."*

**WHAT YOU GET BACK**: ONNX file per task. Plug into
`vision_service.py` (already wired as scaffolding) → exposes
`/api/v1/vision/screen`.

---

## TRACK 8 — Medical knowledge RAG with embeddings (PARAMETERS, KB)

**WHAT**: upgrade the current keyword-based RAG to embedding-based
retrieval so a question like "stain for mold" matches the KOH / GMS
chunks even if the words don't overlap.

**WHO uses it**: `medical_rag.answer_with_kb()` — already wired.

**DATA**:

| File | Path | What |
|---|---|---|
| `medical_knowledge.py` | `backend/ai_services/medical_knowledge.py` | 783 lines → 233 chunks |

**MODEL**: `sentence-transformers/all-MiniLM-L6-v2` (CPU-friendly,
22 M params)

**GPU**: NOT NEEDED — CPU is fine for both indexing and inference

**TIME**: 5 minutes to index, instant queries

**STATUS**: ⏳ **needs a small script** (not even a notebook —
runs locally)

**GOAL**: retrieval recall@5 ≥ 95 % vs the current keyword baseline.

**WHAT YOU GET BACK**: a `chunks.npy` + `index.faiss` you commit to
the repo. `medical_rag.py` gets an extra `embedding_retrieve()`
function. Best of both: keyword for exact-match, embeddings for
semantic.

---

## How to attack this in order

Given limited time and one machine, this is the priority I'd recommend:

| # | Track | Why now | Effort |
|---|---|---|---|
| 1 | TRACK 1 (intent) | Notebook is ready; 30 min on T4 → first trained model | LOW |
| 2 | TRACK 8 (RAG embeddings) | No GPU needed, instant lift in `medical_rag` | LOW |
| 3 | TRACK 2 (LIS mapping) | Real data ready, just need notebook | MED |
| 4 | TRACK 4 (clinical interp) | Highest-impact for clinicians, needs Claude bootstrap first | MED |
| 5 | TRACK 3 (OCR cleanup) | Real data ready, modest gain (regex is already 100 %) | MED |
| 6 | TRACK 7 (vision) | Big PR value but big effort; pick ONE task first (malaria recommended) | HIGH |
| 7 | TRACK 6 (Whisper rw) | Useful but Common Voice rw is small; Whisper-base is OK out of the box for now | HIGH |
| 8 | TRACK 5 (TTS rw) | Browser TTS is already serviceable; lowest urgency | HIGH |

## What you need to bring

For tracks 1-4, the minimum recipe per Colab session:
1. A Google account
2. The two files from this repo (table per track above)
3. Click **Runtime → Change runtime type → T4 GPU**
4. **Runtime → Run all**
5. Wait → download the trained artefact from the Colab files panel

For tracks 5-7, you need to also bring (or download in-Colab) the
relevant public dataset.

I'll write the notebooks for tracks 2, 3, 4, 7, and 8 on request —
just tell me which one to do next.
