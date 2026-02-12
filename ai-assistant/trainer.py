"""
Trainer Module - モデル微調整エンジン
Purpose: ワーカーが生成した合成データでモデルを微調整
        - 訓練データセット読み込み
        - LoRA/QLoRA微調整
        - 損失値監視
        - チェックポイント保存
Usage: trainer.train_loop_once() - 1サイクル実行
Status: 各ワーカーサイクル後に自動実行
"""
import os
import json
import logging
from pathlib import Path

from config import Config

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class Trainer:
    def __init__(self):
        self.training_dir = Config.TRAINING_DIR
        self.models_dir = Config.MODELS_DIR
        self.student_path = Config.STUDENT_MODEL_PATH

    def collect_datasets(self):
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

    def train_loop_once(self):
        examples = self.collect_datasets()
        if not examples:
            logger.info('No synthetic examples to train on')
            return

        # For safety and portability, do not force heavy training here.
        # Save combined dataset for manual inspection or optional offline training.
        out = self.models_dir / f'training_dataset_{int(__import__("time").time())}.jsonl'
        with open(out, 'w', encoding='utf-8') as f:
            for ex in examples:
                f.write(json.dumps(ex, ensure_ascii=False) + '\n')
        logger.info(f'Combined dataset saved to {out} (manual or scheduled training)')

        # Optional: attempt lightweight fine-tuning if environment supports it
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer as HfTrainer, TrainingArguments
            import torch
            # Choose a small model to keep resource usage minimal
            model_name = 'distilgpt2'
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            model = AutoModelForCausalLM.from_pretrained(model_name)
            # distilgpt2 has no pad_token by default; set to eos_token to enable padding
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token
            if model.config.pad_token_id is None:
                model.config.pad_token_id = tokenizer.pad_token_id

            # Prepare dataset
            inputs = [ex['input'] + '\n' + ex['output'] for ex in examples]
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
                output_dir=str(self.models_dir / 'student_finetune'),
                per_device_train_batch_size=2,
                num_train_epochs=1,
                logging_steps=10,
                save_total_limit=1,
                fp16=False
            )
            hf_trainer = HfTrainer(model=model, args=args, train_dataset=dataset)
            hf_trainer.train()
            hf_trainer.save_model(str(self.models_dir / 'student_finetune'))
            logger.info('Lightweight fine-tuning completed and saved')
            # Run simple evaluation
            try:
                from evaluator import overlap_score
                # evaluate on a small subset
                if len(examples) > 0:
                    ref = examples[0].get('output','')
                    hyp = tokenizer.decode(model.generate(tokenizer(ref, return_tensors='pt').input_ids)[0], skip_special_tokens=True)
                    score = overlap_score(ref, hyp)
                    logger.info(f'Lightweight fine-tune eval overlap score: {score:.3f}')
                    try:
                        from evaluator import bleu_score, rouge_scores
                        b = bleu_score(ref, hyp)
                        r = rouge_scores(ref, hyp)
                        logger.info(f'BLEU: {b:.3f}, ROUGE-L: {r.get("rougeL",0):.3f}')
                    except Exception as e:
                        logger.debug(f'Could not compute BLEU/ROUGE: {e}')
            except Exception as e:
                logger.warning(f'Evaluation failed: {e}')
        except Exception as e:
            logger.warning(f'Lightweight fine-tuning skipped or failed: {e}')
            logger.info('You can run offline training with the combined dataset file.')
