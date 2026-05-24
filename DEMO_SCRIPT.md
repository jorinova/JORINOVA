# JORINOVA NEXUS — Tournament Demo Script

A 5–6 minute live screen recording of the **real system** with **Jorinova
(the in-app voice assistant) narrating** every step. Every voice line in
this script is a verbatim quote from `backend/ai_services/training_scenarios.py`
— that is what your speakers will hear.

You drive the recording with **voice commands**. The wake-word for the
assistant is `Jorinova` (also accepts `nexus`, `alis-x`, `hey jorinova`).
Once a training scene is loaded, say `Jorinova start`, then `Jorinova next`
to advance step by step. Say `Jorinova pause` to stop, `Jorinova restart`
to replay.

---

## 0. Pre-flight checklist (do once, before pressing Record)

```
# 1. Bring DB to a known good state
cd backend
python scripts/seed_database.py
python scripts/seed_operational.py
python scripts/seed_production_clinical.py
python scripts/seed_training_pilot.py     # ensures the demo's anchor row exists

# 2. Start backend (terminal 1)
uvicorn main:app --host 0.0.0.0 --port 8000

# 3. Start frontend (terminal 2)
cd ../frontend && npm run dev

# 4. Open browser at http://localhost:3000
#    Log in if needed: labmanager / nexus2026
```

Verify in browser BEFORE recording:
- [ ] Mic permission granted (Chrome shows the lock icon → site settings → Microphone: Allow)
- [ ] Speakers/headphones turned **up** — judges need to hear Jorinova clearly
- [ ] Browser zoom = 100% (Ctrl+0)
- [ ] Browser in fullscreen (F11) — hides bookmarks, tabs, anything that looks like a dev machine
- [ ] Devtools closed (F12 to toggle off if open)
- [ ] Network/proxy off if you want zero risk of stutter
- [ ] System notifications muted

### Recording setup
- **OBS Studio** (free). Scene: Display Capture, source: your primary monitor.
- **Output**: 1920×1080 @ 60 fps, MP4, x264, 8000 Kbps.
- **Audio**: Desktop audio (so Jorinova's voice records) + your microphone (so your voice commands record).
- Do a 10-second test recording first — confirm both Jorinova and your voice are audible at the same level.

### Where to upload
YouTube → Upload → set visibility to **Unlisted** → copy the share link. That's your "video link" for the tournament submission.

---

## 1. Opening (0:00 – 0:25) — wake-word demo, language pick

**On screen:** Login screen, then the dashboard. Pause for 2 seconds on each.

**You (off-camera, into the mic):** `Hello Jorinova`

**Jorinova (real-time TTS reply, en/fr/rw based on the scene language):**
> *"Good morning. Thank you for calling Jorinova."*

**You:** *"Today we are demonstrating Jorinova Nexus — the offline-first laboratory information system for African hospitals."*

> Why this beats a static intro: judges immediately see this is a real voice agent (regex → local LLM → cloud cascade), not a video overlay. The wake-word + reply happens in front of them.

---

## 2. Scene 1 — IoT: any analyzer, one contract (0:25 – 1:05)

**Why this comes first:** vendor-neutral integration is the rarest claim in
this space. Showing it up-front establishes credibility for everything after.

**Navigate:** `/modules/training/iot_analyzer_intake_demo?demo=1`

**You:** `Jorinova start`

**Jorinova (verbatim, the system says this):**
> *"Good day. Thank you for taking time today. This demo shows how any laboratory analyzer connects to the system."*

**Jorinova (auto-advance, step 2):**
> *"Here is the live list of analyzer adapters. We are not locked to one brand. Sysmex, Roche, Mindray, BioRad, Beckman — any vendor can plug in."*

**You (interject, only if needed):** `Jorinova next`

**Jorinova (step 3 → 4 → 5 → 6, ~25 seconds):**
> *"When the technician selects an adapter, the system knows the wire format and the vendor."*
> *"This is what the analyzer sends. Some send HL7, some send ASTM, some send JSON or CSV. The adapter understands them all."*
> *"Ingest into the laboratory information system."*
> *"All payloads end up in the same shape. Sample identifier, test code, value, flag. You are welcome. Have a nice day."*

**You (one line, after the scene):** *"Six built-in adapters today. New analyzer support is one Python file — no router changes."*

---

## 3. Scene 2 — OCR auto-scan + LIS auto-mapping (1:05 – 1:50)

**Navigate:** `/modules/training/lis_mapping_walkthrough?demo=1`

**You:** `Jorinova start`

**Jorinova:**
> *"Welcome. We will demonstrate the LIS auto-mapping feature."*
> *"A scanned lab request is dropped into the upload area."*
> *"The Extract draft button starts the OCR and matching pipeline."*
> *"In a moment the patient, the tests, and the priority appear with confidence chips. CBC is expanded into nine individual tests."*
> *"After review, the user clicks Create LabRequest. The worklist is now populated."*
> *"LabRequest created. The end-to-end mapping is now complete."*

**You (after the scene):** *"Patient identification, priority detection, and test mapping — 100 percent accurate on our locked golden set. Tesseract, EasyOCR, and Claude Vision all available, picked automatically per page quality."*

---

## 4. Scene 3 — STAT specimen intake + workflow (1:50 – 2:25)

**Navigate:** `/modules/training/specimen_intake_stat?demo=1`

**You:** `Jorinova start`

**Jorinova (verbatim):**
> *"Welcome. We will walk through receiving a STAT priority specimen."*
> *"First, place the cursor in the barcode scanner field."*
> *"Now we simulate scanning the tube. Barcode S-I-D dash zero-one-zero-one."*
> *"The patient is now identified: Mary Uwineza, female, twenty-eight years old."*
> *"Priority is STAT. The system will route this specimen to the front of the worklist."*
> *"Click Print to generate the aliquot labels."*
> *"Labels printed. The specimen is now in the worklist with STAT priority."*

**You:** *"Barcode in, patient out, STAT routed in under three seconds — fully offline."*

---

## 5. Scene 4 — Critical CBC: validation + auto-save in records book (2:25 – 3:00)

**Navigate:** `/modules/training/critical_value_validation?demo=1`

**You:** `Jorinova start`

**Jorinova:**
> *"Welcome. This scenario reviews a CBC with a critical White Blood Cell count."*
> *"Accessing patient records for ID One-Zero-One."*
> *"Analyzing laboratory data. Hemoglobin is normal, but White Blood Cell count is elevated at 15,000 cells per microliter. Flagging mild leukocytosis."*
> *"No critical panic values exceed the threshold. Approving and signing the result under Jorinova Nexus protocols."*
> *"Authorized. Result has been digitally signed and transmitted."*

**You:** *"Once authorized, the result is post-quantum signed and the entry is auto-archived in the immutable Critical Result Book — every critical value, who validated it, when, and with read-back confirmation."*

---

## 6. Scene 5 — Biochemistry / clinical interpretation (3:00 – 3:35)

**Navigate:** open any released LabRequest from `/modules/laboratory` and
click "Interpret" — uses the cloud cascade we've already wired.

**You:** *"For panel-level interpretation, the rules engine runs first — deterministic and instant. If reasoning is needed, the local Ollama worker takes it; if still needed, Claude takes over. Three layers, one fallback chain."*

**You can demo with one of the seeded clinical cases. Example narration over a real result screen:**

> *"Here you can see a released chemistry panel for a fifty-year-old patient on diabetes follow-up. HbA1c at seven point one, fasting glucose seven point five, creatinine slightly elevated. The system flags long-standing poor glycaemic control with possible early diabetic nephropathy, and recommends an eGFR calculation. Every flag and every interpretation is traceable to the rule or the model that produced it."*

> Honest framing: don't claim the local fine-tune is done. Say "rules + cloud reasoning today, local fine-tune is the next training cycle."

---

## 7. Scene 6 — Genomic / MedGenome: TB GeneXpert (3:35 – 4:15)

**Navigate:** `/modules/training/medgenome_pcr_demo?demo=1`

**You:** `Jorinova start`

**Jorinova:**
> *"Welcome. We will interpret a GeneXpert MTB and Rif Ultra result."*
> *"Here is the PCR run, with the test name, instrument, cartridge, and result."*
> *"The Cycle threshold value places this case in a medium bacillary load band."*
> *"Rifampicin resistance is checked. Detected resistance escalates to multi-drug-resistance protocol."*
> *"AI interpretation synthesises the Ct, semi-quant band, and resistance markers into a clinical summary."*
> *"The case is routed into the molecular epidemiology surveillance signal pipeline."*

**You:** *"GeneXpert is one of our molecular workflows. The same pipeline routes HIV viral load, HCV RNA, and the resistance markers feed our outbreak signal layer."*

---

## 8. Scene 7 — Blood bank: chamber/slot crossmatch (4:15 – 4:50)

**Navigate:** `/modules/training/blood_bank_crossmatch_demo?demo=1`

**You:** `Jorinova start`

**Jorinova:**
> *"Welcome. We will demonstrate a blood-bank crossmatch with chamber and slot tracking."*
> *"Here is the selected bag. The system shows blood group, component, volume, and expiry."*
> *"The bag is tracked at the fridge, chamber, and numbered slot level. FIFO and FEFO rules picked this exact unit."*
> *"The technician triggers the Indirect Antiglobulin crossmatch."*
> *"Compatible result. The unit is issued and the haemovigilance watch is armed."*
> *"Transfusion clock started. Any reaction will auto-link to this bag."*

**You:** *"Every bag is physically tracked to the chamber and the slot. Reaction reports auto-link to the issued unit — full traceability end to end."*

---

## 9. Scene 8 — MoMo payment + release (4:50 – 5:15)

**Navigate:** `/modules/training/momo_billing_demo?demo=1`

**You:** `Jorinova start`

**Jorinova:**
> *"Welcome. We will accept a Mobile Money payment for a confirmed lab bill."*
> *"The invoice was auto-generated from the requested tests using the test catalogue prices."*
> *"The receptionist enters the MoMo reference returned by the patient."*
> *"Confirming the payment registers the receipt and matches it to the bill."*
> *"The receipt now shows the MoMo reference, the method, and the paid amount."*
> *"The bill is settled. The worklist is now released to the analyzer floor."*

**You:** *"Mobile Money is the dominant payment rail in Rwanda. We close the financial loop and release the worklist in one step."*

---

## 10. Roadmap callout — image AI, smart inventory, fine-tuned LLM (5:15 – 5:45)

**On screen:** open any module showing the architecture diagram, or just
stay on the dashboard.

**You (calm, confident — this is your roadmap pitch):**

> *"What you have seen today runs on the real pilot database. Three things are next."*
>
> *"First, vision-based screening for cancerous cells and fungi on stained slides. The vision service is wired into the same orchestrator — we are now in the data collection phase with two partner hospitals."*
>
> *"Second, predictive inventory. The inventory module already tracks every reagent, every blood bag, every cartridge. The AI layer that forecasts re-order points is in training."*
>
> *"Third, the local language model fine-tune. Today the assistant runs on a regex + cloud cascade, scoring one hundred percent on our locked golden set across English, French, and Kinyarwanda. A Kinyarwanda-specialised local model is the next training cycle, so the system works even when the internet does not."*

> Why this works: judges respect a real roadmap on top of a real demo more than vapor. You are saying "here is what's live, here is exactly what's next, this is how we get there."

---

## 11. Close (5:45 – 6:00)

**You:** `Jorinova, thank you`

**Jorinova (verbatim reply from the persona module):**
> *"You're welcome. Have a nice day."*

(In Kinyarwanda mode this is *"Murakaza neza. Mugire umunsi mwiza."* — even better for a Rwandan tournament. Set the language by visiting any scene with `?lang=rw`.)

**You (one final line, slow, into camera if you have one — otherwise voice only):**

> *"Jorinova Nexus. Built for African laboratories. Online or offline. Murakoze cyane."*

Fade to logo. Stop recording.

---

## Backup commands (memorise these — say only if a step misfires)

| You say | What happens |
|---|---|
| `Jorinova next` | Skip to the next step |
| `Jorinova pause` | Pause the current scene |
| `Jorinova resume` | Resume after pause |
| `Jorinova restart` | Replay the whole scene from the top |
| `Jorinova stop` | End the scene |
| `Jorinova help` | Lists every voice command (useful if you forget on stage) |

If TTS doesn't fire (browser audio quirk), click the mute toggle 🔊 once
in the runner header — voices reload. The subtitle bar always shows the
line even if audio dies, so you can read it aloud yourself.

---

## What to NOT say on camera

- Don't promise cancer/fungi detection works **today**. Say "in training,
  partnering with two hospitals for data."
- Don't claim "fully GPU-accelerated" or "real-time vision" — neither is
  true yet.
- Don't claim multi-tenancy — currently single-hospital.
- Don't show code or terminals. Stay in the browser the whole time.
- If a scene stutters, just say `Jorinova restart` and keep moving. Live
  demos are expected to have one recover-moment — judges respect a clean
  recovery more than a stitched-together fake.
