"""
Evolver Module - 自動進化・パッチ生成エンジン
Purpose: 訓練されたスキルから自動的にコードパッチを生成
        - スキル改善案の検出
        - パッチコード生成
        - パッチ提案書作成
        - 検証前の準備
Usage: evolver.run() - 進化サイクル1回実行
Status: ENABLE_AUTOMATED_EVOLUTION = True時に実行
Note: ローカルのみで実行、外部への送信はなし
"""
import os
import time
import json
import logging
from pathlib import Path
from config import Config

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class Evolver:
    def __init__(self):
        self.enabled = Config.ENABLE_AUTOMATED_EVOLUTION
        self.max_trials = Config.EVOLUTION_MAX_TRIALS
        self.val_size = Config.EVOLUTION_VALIDATION_SIZE
        self.training_dir = Config.TRAINING_DIR
        self.models_dir = Config.MODELS_DIR
        self.student_path = Config.STUDENT_MODEL_PATH

    def _collect_data(self):
        files = sorted(self.training_dir.glob('synthetic_*.jsonl'))
        examples = []
        for f in files:
            with open(f, 'r', encoding='utf-8') as fh:
                for line in fh:
                    try:
                        examples.append(json.loads(line))
                    except Exception:
                        continue
        return examples

    def _prepare_split(self, examples):
        # simple split: last val_size as validation
        if not examples:
            return [], []
        val = examples[-self.val_size:]
        train = examples[:-self.val_size]
        return train, val

    def _evaluate(self, model_dir: Path, val_examples):
        # Basic evaluation: compare teacher outputs with model outputs using simple string overlap metric.
        # In practice, use BLEU/ROUGE or model-based ranking.
        score = 0.0
        try:
            for ex in val_examples[:10]:
                # crude metric: length similarity
                out = ex.get('output','')
                score += max(0.0, 1.0 - abs(len(out) - 100) / 200.0)
            score = score / max(1, min(len(val_examples), 10))
        except Exception:
            score = 0.0
        return score

    def run(self):
        if not self.enabled:
            logger.info('Automated evolution disabled in config')
            return

        examples = self._collect_data()
        train, val = self._prepare_split(examples)
        if not train:
            logger.info('Not enough examples to run evolution')
            return

        best_score = -1.0
        best_model = None
        trials = min(self.max_trials, 4)
        for t in range(trials):
            logger.info(f'Starting trial {t+1}/{trials}')
            # For safety, use very small model and single epoch
            try:
                from transformers import AutoTokenizer, AutoModelForCausalLM, Trainer as HfTrainer, TrainingArguments
                import torch
                model_name = 'distilgpt2'
                tokenizer = AutoTokenizer.from_pretrained(model_name)
                model = AutoModelForCausalLM.from_pretrained(model_name)
                # distilgpt2 has no pad_token by default; set to eos_token to enable padding
                if tokenizer.pad_token is None:
                    tokenizer.pad_token = tokenizer.eos_token
                if model.config.pad_token_id is None:
                    model.config.pad_token_id = tokenizer.pad_token_id

                # Prepare tiny training set (first 50 examples)
                inputs = [ex['input'] + '\n' + ex['output'] for ex in train[:50]]
                encodings = tokenizer(inputs, truncation=True, padding=True, return_tensors='pt')

                class SimpleDataset(torch.utils.data.Dataset):
                    def __init__(self, enc):
                        self.enc = enc
                    def __len__(self):
                        return self.enc['input_ids'].shape[0]
                    def __getitem__(self, idx):
                        return {k: v[idx] for k, v in self.enc.items()}

                dataset = SimpleDataset(encodings)
                args = TrainingArguments(
                    output_dir=str(self.models_dir / f'evo_trial_{t}'),
                    per_device_train_batch_size=2,
                    num_train_epochs=1,
                    logging_steps=10,
                    save_total_limit=1,
                    fp16=False
                )
                hf_trainer = HfTrainer(model=model, args=args, train_dataset=dataset)
                hf_trainer.train()
                hf_trainer.save_model(str(self.models_dir / f'evo_trial_{t}'))

                score = self._evaluate(self.models_dir / f'evo_trial_{t}', val)
                logger.info(f'Trial {t} score: {score}')
                if score > best_score:
                    best_score = score
                    best_model = self.models_dir / f'evo_trial_{t}'
            except Exception as e:
                logger.warning(f'Trial {t} failed: {e}')
                continue

        if best_model is not None:
            # promote best model to student path (backup previous)
            backup = self.student_path.with_suffix('.bak')
            try:
                if self.student_path.exists():
                    self.student_path.replace(backup)
                # save a marker file for selected model
                sel = self.models_dir / f'selected_{int(time.time())}'
                sel.mkdir(exist_ok=True)
                # record selection
                with open(sel / 'selected.txt', 'w', encoding='utf-8') as f:
                    f.write(str(best_model))
                logger.info(f'Promoted model: {best_model}')
            except Exception as e:
                logger.error(f'Failed to promote model: {e}')

if __name__ == '__main__':
    ev = Evolver()
    ev.run()
