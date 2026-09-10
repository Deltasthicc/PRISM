"""Step 2 of the voice-model domain-adaptation pipeline.

Synthesizes one WAV file per corpus.txt sentence using Piper TTS (already a
project dependency -- backend/requirements.txt's piper-tts==1.8.0, the same
package ai/voice/tts.py uses for the live assistant), rotating across
several different voice models for speaker diversity. A model fine-tuned on
one single synthetic voice tends to overfit to that voice's specific
pronunciation quirks rather than learning the vocabulary generally -- using
several different real Piper voices makes the fine-tune generalize to real
human speakers much better than one voice would.

Piper voice models are NOT bundled with this repo (same reason
PIPER_MODEL_PATH isn't committed -- see the README's Voice AI section) --
download_voices() below fetches a small, fixed set of free voices from
rhasspy/piper-voices on first run and caches them locally.

Run from backend/: python scripts/voice_finetuning/2_synthesize_training_audio.py
Writes scripts/voice_finetuning/audio/*.wav and
scripts/voice_finetuning/manifest_train.jsonl / manifest_val.jsonl.
"""
from __future__ import annotations

import json
import os
import random
import urllib.request
import wave

from piper import PiperVoice

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS_PATH = os.path.join(HERE, "corpus.txt")
AUDIO_DIR = os.path.join(HERE, "audio")
VOICES_DIR = os.path.join(HERE, "voices")
VAL_FRACTION = 0.08
RANDOM_SEED = 42

# A handful of free, distinct English Piper voices (different speakers,
# accents, and training data) for real speaker diversity -- all hosted on
# the same public rhasspy/piper-voices HuggingFace repo Piper's own docs
# point to.
VOICES = [
    ("en_US-lessac-medium", "en/en_US/lessac/medium"),
    ("en_US-amy-medium", "en/en_US/amy/medium"),
    ("en_GB-alan-medium", "en/en_GB/alan/medium"),
    ("en_US-joe-medium", "en/en_US/joe/medium"),
]
BASE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main"


def download_voices() -> list[tuple[str, str, str]]:
    """Returns [(voice_name, onnx_path, config_path), ...], downloading any
    voice not already cached in VOICES_DIR."""
    os.makedirs(VOICES_DIR, exist_ok=True)
    resolved = []
    for name, remote_subpath in VOICES:
        onnx_path = os.path.join(VOICES_DIR, f"{name}.onnx")
        config_path = os.path.join(VOICES_DIR, f"{name}.onnx.json")
        if not os.path.exists(onnx_path):
            print(f"Downloading voice {name}...")
            urllib.request.urlretrieve(f"{BASE_URL}/{remote_subpath}/{name}.onnx", onnx_path)
        if not os.path.exists(config_path):
            urllib.request.urlretrieve(f"{BASE_URL}/{remote_subpath}/{name}.onnx.json", config_path)
        resolved.append((name, onnx_path, config_path))
    return resolved


def main() -> None:
    with open(CORPUS_PATH, encoding="utf-8") as f:
        sentences = [line.strip() for line in f if line.strip()]

    os.makedirs(AUDIO_DIR, exist_ok=True)
    voice_paths = download_voices()
    print(f"Loading {len(voice_paths)} voice models...")
    loaded_voices = [
        (name, PiperVoice.load(onnx_path, config_path=config_path))
        for name, onnx_path, config_path in voice_paths
    ]

    entries = []
    for i, sentence in enumerate(sentences):
        voice_name, voice = loaded_voices[i % len(loaded_voices)]
        audio_filename = f"{i:05d}_{voice_name}.wav"
        audio_path = os.path.join(AUDIO_DIR, audio_filename)
        with wave.open(audio_path, "wb") as wav_file:
            voice.synthesize_wav(sentence, wav_file)
        entries.append({"audio_path": os.path.join("audio", audio_filename), "text": sentence, "voice": voice_name})
        if (i + 1) % 100 == 0:
            print(f"  synthesized {i + 1}/{len(sentences)}")

    random.Random(RANDOM_SEED).shuffle(entries)
    n_val = max(1, int(len(entries) * VAL_FRACTION))
    val_entries = entries[:n_val]
    train_entries = entries[n_val:]

    with open(os.path.join(HERE, "manifest_train.jsonl"), "w", encoding="utf-8") as f:
        for e in train_entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    with open(os.path.join(HERE, "manifest_val.jsonl"), "w", encoding="utf-8") as f:
        for e in val_entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    print(f"Wrote {len(train_entries)} train / {len(val_entries)} val entries.")


if __name__ == "__main__":
    main()
