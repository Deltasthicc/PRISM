"""Step 4 of the voice-model domain-adaptation pipeline.

Compares word error rate (WER) between the stock faster-whisper tiny.en
model and the fine-tuned model on the held-out validation split, so the
fine-tune's actual, measured improvement is documented rather than assumed.
Requires the CTranslate2-converted model directory (step 5's output) since
both models are loaded through the same faster_whisper.WhisperModel API the
app itself uses -- this evaluates exactly what the app will run.

Usage (from backend/, after step 5's conversion):
    python scripts/voice_finetuning/4_evaluate_wer.py \
        --finetuned-model scripts/voice_finetuning/whisper-domain-finetuned-ct2 \
        --val-manifest scripts/voice_finetuning/manifest_val.jsonl
"""
from __future__ import annotations

import argparse
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def load_manifest(path: str) -> list[dict]:
    entries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def transcribe_all(model_size_or_path: str, manifest_dir: str, entries: list[dict]) -> list[str]:
    from faster_whisper import WhisperModel

    model = WhisperModel(model_size_or_path, device="cpu", compute_type="int8")
    hypotheses = []
    for i, entry in enumerate(entries):
        audio_path = os.path.join(manifest_dir, entry["audio_path"])
        segments, _ = model.transcribe(audio_path, language="en", task="transcribe", beam_size=1)
        text = " ".join(s.text.strip() for s in segments if s.text.strip()).strip()
        hypotheses.append(text)
        if (i + 1) % 20 == 0:
            print(f"  transcribed {i + 1}/{len(entries)}")
    return hypotheses


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-model", default="tiny.en")
    parser.add_argument("--finetuned-model", required=True, help="Path to the CTranslate2-converted fine-tuned model directory")
    parser.add_argument("--val-manifest", default=os.path.join(HERE, "manifest_val.jsonl"))
    args = parser.parse_args()

    import jiwer

    entries = load_manifest(args.val_manifest)
    manifest_dir = os.path.dirname(args.val_manifest)
    references = [e["text"] for e in entries]
    print(f"Evaluating on {len(entries)} held-out validation examples.\n")

    print(f"Transcribing with baseline ({args.baseline_model})...")
    baseline_hyps = transcribe_all(args.baseline_model, manifest_dir, entries)
    baseline_wer = jiwer.wer(references, baseline_hyps)

    print(f"\nTranscribing with fine-tuned model ({args.finetuned_model})...")
    finetuned_hyps = transcribe_all(args.finetuned_model, manifest_dir, entries)
    finetuned_wer = jiwer.wer(references, finetuned_hyps)

    print("\n=== Results ===")
    print(f"Baseline  ({args.baseline_model}) WER: {baseline_wer * 100:.2f}%")
    print(f"Fine-tuned ({args.finetuned_model}) WER: {finetuned_wer * 100:.2f}%")
    relative = (baseline_wer - finetuned_wer) / baseline_wer * 100 if baseline_wer > 0 else 0.0
    print(f"Relative improvement: {relative:.1f}%")

    print("\n=== Sample mismatches (baseline vs fine-tuned vs reference) ===")
    shown = 0
    for ref, base_hyp, ft_hyp in zip(references, baseline_hyps, finetuned_hyps):
        if base_hyp.strip().lower() != ref.strip().lower() and shown < 10:
            print(f"  REF:       {ref}")
            print(f"  BASELINE:  {base_hyp}")
            print(f"  FINETUNED: {ft_hyp}")
            print()
            shown += 1


if __name__ == "__main__":
    main()
