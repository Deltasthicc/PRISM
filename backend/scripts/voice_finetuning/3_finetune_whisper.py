"""Step 3 of the voice-model domain-adaptation pipeline.

Fine-tunes openai/whisper-tiny.en on the synthetic (audio, text) corpus built
by 1_prepare_domain_corpus.py + 2_synthesize_training_audio.py, using the
standard HuggingFace transformers/datasets/Seq2SeqTrainer recipe.

This step is GPU-heavy and is meant to be run on the user's own training
server (32GB RAM, RTX 5090), not in this environment. See
scripts/voice_finetuning/README.md for the exact command sequence, including
the one-time `pip install` of the extra training-only dependencies this
script needs (transformers, datasets, accelerate, evaluate, jiwer, torch,
librosa, soundfile) -- none of these are runtime dependencies of the deployed
app and are deliberately NOT added to backend/requirements.txt.

Usage (from backend/, after running steps 1 and 2):
    python scripts/voice_finetuning/3_finetune_whisper.py \
        --base-model openai/whisper-tiny.en \
        --output-dir scripts/voice_finetuning/whisper-domain-finetuned \
        --epochs 8 --batch-size 16
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-model", default="openai/whisper-tiny.en")
    parser.add_argument("--output-dir", default=os.path.join(HERE, "whisper-domain-finetuned"))
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=1e-5)
    parser.add_argument("--train-manifest", default=os.path.join(HERE, "manifest_train.jsonl"))
    parser.add_argument("--val-manifest", default=os.path.join(HERE, "manifest_val.jsonl"))
    args = parser.parse_args()

    # Imported lazily so this file can be read/lint-checked without the
    # heavy, training-only packages installed (they are not part of the
    # deployed app's dependency set -- see the module docstring).
    import evaluate
    import torch
    from datasets import Audio, Dataset
    from transformers import (
        Seq2SeqTrainer,
        Seq2SeqTrainingArguments,
        WhisperForConditionalGeneration,
        WhisperProcessor,
    )

    processor = WhisperProcessor.from_pretrained(args.base_model, language="en", task="transcribe")
    model = WhisperForConditionalGeneration.from_pretrained(args.base_model)
    model.generation_config.language = "en"
    model.generation_config.task = "transcribe"
    model.generation_config.forced_decoder_ids = None

    def to_dataset(manifest_path: str) -> Dataset:
        entries = load_manifest(manifest_path)
        manifest_dir = os.path.dirname(manifest_path)
        audio_paths = [os.path.join(manifest_dir, e["audio_path"]) for e in entries]
        texts = [e["text"] for e in entries]
        ds = Dataset.from_dict({"audio": audio_paths, "text": texts})
        return ds.cast_column("audio", Audio(sampling_rate=16000))

    train_ds = to_dataset(args.train_manifest)
    val_ds = to_dataset(args.val_manifest)
    print(f"Loaded {len(train_ds)} train / {len(val_ds)} val examples.")

    def prepare_example(batch):
        audio = batch["audio"]
        batch["input_features"] = processor.feature_extractor(
            audio["array"], sampling_rate=audio["sampling_rate"]
        ).input_features[0]
        batch["labels"] = processor.tokenizer(batch["text"]).input_ids
        return batch

    # No num_proc: passing num_proc=1 still makes datasets.map() spawn a
    # multiprocessing worker pool and talk to it over an IPC pipe (confirmed
    # via a real hang on a Python 3.14 GPU box: the main process blocked
    # forever in conn.recv() waiting on a worker that never replied, most
    # likely a fork/native-library interaction on that new an interpreter).
    # Leaving num_proc unset runs map() in-process with no forking and no
    # IPC at all -- for a corpus this size that's still fast, and it can't
    # hang on a worker that silently dies.
    #
    # A small writer_batch_size gives real incremental progress feedback --
    # datasets.map()'s default (1000) only updates the bar once a whole
    # write-batch finishes, so on a ~1000-row split it looks stuck at 0%
    # right up until the entire dataset is done.
    train_ds = train_ds.map(
        prepare_example, remove_columns=train_ds.column_names, writer_batch_size=50
    )
    val_ds = val_ds.map(
        prepare_example, remove_columns=val_ds.column_names, writer_batch_size=50
    )

    class DataCollatorSpeechSeq2Seq:
        def __call__(self, features):
            input_features = [{"input_features": f["input_features"]} for f in features]
            batch = processor.feature_extractor.pad(input_features, return_tensors="pt")

            label_features = [{"input_ids": f["labels"]} for f in features]
            labels_batch = processor.tokenizer.pad(label_features, return_tensors="pt")
            labels = labels_batch["input_ids"].masked_fill(labels_batch.attention_mask.ne(1), -100)
            batch["labels"] = labels
            return batch

    data_collator = DataCollatorSpeechSeq2Seq()
    wer_metric = evaluate.load("wer")

    def compute_metrics(pred):
        pred_ids = pred.predictions
        label_ids = pred.label_ids
        label_ids[label_ids == -100] = processor.tokenizer.pad_token_id

        pred_str = processor.tokenizer.batch_decode(pred_ids, skip_special_tokens=True)
        label_str = processor.tokenizer.batch_decode(label_ids, skip_special_tokens=True)
        wer = 100 * wer_metric.compute(predictions=pred_str, references=label_str)
        return {"wer": wer}

    training_args = Seq2SeqTrainingArguments(
        output_dir=args.output_dir,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        num_train_epochs=args.epochs,
        gradient_checkpointing=True,
        fp16=torch.cuda.is_available(),
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=2,
        predict_with_generate=True,
        generation_max_length=225,
        logging_steps=25,
        load_best_model_at_end=True,
        metric_for_best_model="wer",
        greater_is_better=False,
        report_to=[],
    )

    trainer = Seq2SeqTrainer(
        args=training_args,
        model=model,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
        # `tokenizer=` was removed in newer transformers releases in favor of
        # `processing_class=` (same value, just a renamed kwarg).
        processing_class=processor.feature_extractor,
    )

    trainer.train()

    final_dir = os.path.join(args.output_dir, "final")
    trainer.save_model(final_dir)
    processor.save_pretrained(final_dir)
    print(f"Saved fine-tuned model + processor to {final_dir}")


if __name__ == "__main__":
    main()
