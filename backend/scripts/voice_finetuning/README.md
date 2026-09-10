# Whisper domain fine-tuning — runbook

## Why this exists

The voice assistant's speech-to-text (`ai/voice/stt.py`, `faster-whisper tiny.en`)
measurably mis-transcribes this project's own domain vocabulary — government-body
acronyms and official-statistics terms that are all over the quiz content and
curricula. Confirmed twice, independently, with two different TTS voices on
clean, artifact-free synthesized speech:

- Windows SAPI voice: "DARPG Sevottam" → "DARPAGE SEV-autumn"
- Piper `en_US-lessac-medium` voice: "The DARPG Sevottam framework improves
  public service delivery." → "The dark, sevetam framework improves public
  service delivery."

This is a real, reproducible bug with a standard, well-understood fix: fine-tune
Whisper on synthetic speech built from the project's own real vocabulary. This
is the **one** genuine ML-training opportunity found in the project. Two other
"AI"-labeled features were investigated and are explicitly **not** candidates —
see "What was *not* trained, and why" at the bottom.

Everything through data prep (steps 1–2) can run on a laptop. Fine-tuning
(step 3) needs a GPU — that's the part meant for your RTX 5090 server.

## What's already done, committed to this branch

- `1_prepare_domain_corpus.py` has been run; `corpus.txt` (1089 deduplicated
  training sentences pulled from `services/curricula.py` and
  `data/hand_authored_questions.json`) is committed alongside it.
- `ai/voice/stt.py` now reads a `WHISPER_MODEL_PATH` env var (falls back to the
  stock `tiny.en` model if unset), so the fine-tuned model can be wired in
  later with zero further code changes — same pattern `LocalPiperTTS` already
  uses for `PIPER_MODEL_PATH`.

## Commands to run on your GPU server

Run these in order, from a clone of this repo, on the
`feat/whisper-domain-finetune` branch (or after merging it to `main`).

### 0. Clone and set up

```bash
git clone https://github.com/Deltasthicc/PRISM.git
cd PRISM
git checkout feat/whisper-domain-finetune
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 1. Install the extra, training-only dependencies

These are deliberately **not** in `requirements.txt` — they're only needed to
run this one-off fine-tune, not to run the deployed app.

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu124
pip install transformers datasets accelerate evaluate jiwer librosa soundfile ctranslate2
```

### 2. Regenerate the corpus (optional — already committed, skip unless you changed curricula/questions)

```bash
python scripts/voice_finetuning/1_prepare_domain_corpus.py
```

### 3. Synthesize training audio

Downloads 4 free Piper voices (~250MB total, one-time) and synthesizes one WAV
per sentence across all 4, for speaker diversity. Takes a few minutes on CPU.

```bash
python scripts/voice_finetuning/2_synthesize_training_audio.py
```

Produces `scripts/voice_finetuning/audio/*.wav`, `manifest_train.jsonl`
(~1002 examples), and `manifest_val.jsonl` (~87 examples).

### 4. Fine-tune Whisper

This is the actual GPU step. `--batch-size 16` is a safe starting point for a
24GB+ card on `whisper-tiny.en`; the RTX 5090 has plenty of headroom to raise
it (try 32) if you want faster epochs.

```bash
python scripts/voice_finetuning/3_finetune_whisper.py \
    --base-model openai/whisper-tiny.en \
    --output-dir scripts/voice_finetuning/whisper-domain-finetuned \
    --epochs 8 \
    --batch-size 16 \
    --learning-rate 1e-5
```

The `Map: 0%|...` progress bar before training starts can sit at 0% for a
minute or two on a corpus this size -- `datasets.map()` only updates it once
an internal write-batch finishes. That's expected. If it never moves at all
and stays at exactly `0/1002 [00:00<?, ...]` indefinitely, check
`ps -eo pid,etime,pcpu,cmd | grep 3_finetune_whisper`: real progress shows
non-trivial `%CPU` accumulating over time. A genuinely frozen run (0% CPU,
no growth) was reproduced on a Python 3.14 box and traced to
`datasets.map()`'s internal multiprocessing worker pool -- passing
`num_proc=1` still spawns a worker and talks to it over an IPC pipe, and
that worker can silently die without ever replying, leaving the main
process blocked forever in `conn.recv()`. This script no longer passes
`num_proc` at all (so `map()` runs in-process, no forking, no IPC) --
if you're on an older checkout that still hangs here, `git pull` first.

Watch the logged `wer` metric each epoch — it should trend down from the
baseline. This should take well under an hour on an RTX 5090 for a corpus this
size. The best checkpoint (by validation WER) is saved to
`scripts/voice_finetuning/whisper-domain-finetuned/final/`.

### 5. Convert to CTranslate2 format

`faster-whisper` (what the app actually runs) requires CTranslate2 format, not
the raw HuggingFace checkpoint step 4 produces.

```bash
ct2-transformers-converter \
    --model scripts/voice_finetuning/whisper-domain-finetuned/final \
    --output_dir scripts/voice_finetuning/whisper-domain-finetuned-ct2 \
    --quantization int8
```

### 6. Evaluate: did it actually help?

Compares stock `tiny.en` vs. your fine-tuned model on the held-out validation
split, through the exact `faster_whisper.WhisperModel` API the app uses.

```bash
python scripts/voice_finetuning/4_evaluate_wer.py \
    --finetuned-model scripts/voice_finetuning/whisper-domain-finetuned-ct2 \
    --val-manifest scripts/voice_finetuning/manifest_val.jsonl
```

Only proceed to step 7 if the fine-tuned WER is meaningfully lower than
baseline. If it isn't, the corpus likely needs more data or more epochs before
this is worth deploying — don't wire in a model that isn't actually better.

### 7. Deploy the fine-tuned model

Copy `whisper-domain-finetuned-ct2/` to wherever the running app's process can
read it (e.g. alongside the backend deployment), then set:

```bash
export WHISPER_MODEL_PATH=/absolute/path/to/whisper-domain-finetuned-ct2
```

before starting the backend (`uvicorn main:app`). No code change is needed —
`ai/voice/stt.py` picks this up automatically and falls back to stock `tiny.en`
if the env var is unset or the path is missing.

To go back to the stock model, just unset `WHISPER_MODEL_PATH`.

## What was *not* trained, and why

Two other features surfaced as "AI" in the codebase were investigated as
possible training candidates and deliberately left alone:

- **`/ai/difficulty/next`** (`routes/ai_real.py`, "RL epsilon-greedy bandit"):
  reading `services/ai_client.py` shows this is a fixed-threshold heuristic
  plus `random.random() < epsilon` exploration — there's no Q-table, no
  persisted learned state, nothing that training would actually change.
- **`/ai/graph/next-topic`** ("Knowledge Graph AI"): deterministic graph
  traversal over a fixed topic graph, same story — no learned parameters.

Neither has real interaction-log data at any meaningful scale to learn from,
and inventing a "trained" model on top of a heuristic that already works would
just be adding fake ML-washing rather than a real improvement — which is
exactly what the project's own "no fabricated psychometric precision" design
ethic argues against. Leaving both as documented heuristics is the honest call.
