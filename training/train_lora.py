"""LoRA fine-tuning on validated passage/MCQ JSONL; smoke run is not an exam model."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    train_default = "training/data/diverse_train.jsonl" if Path("training/data/diverse_train.jsonl").exists() else "training/data/smoke_train.jsonl"
    val_default = "training/data/diverse_validation.jsonl" if Path("training/data/diverse_validation.jsonl").exists() else "training/data/smoke_validation.jsonl"
    parser.add_argument("--train", default=train_default)
    parser.add_argument("--validation", default=val_default)
    parser.add_argument("--output", default="artifacts/quiz-lora-phi35")
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--model", default="microsoft/Phi-3.5-mini-instruct")
    args = parser.parse_args()
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, Trainer, TrainingArguments, DataCollatorForSeq2Seq
    from peft import LoraConfig, get_peft_model
    from ai_quiz_agent.agents.quiz_generation_agent import SYSTEM_PROMPT, _build_user_prompt
    from ai_quiz_agent.schemas.models import Difficulty, QuestionType, Question

    if not torch.cuda.is_available():
        raise RuntimeError("Select a GPU runtime in Colab before training.")
    def read(path):
        rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
        if not rows:
            raise ValueError("Training/validation data is empty.")
        for row in rows:
            q = Question(**row["question"])
            if not q.options or not q.source_quote or q.source_quote not in row["passage"]:
                raise ValueError("Every example must have an MCQ and supporting source quote.")
        return rows
    train, validation = read(args.train), read(args.validation)
    if {r["source_id"] for r in train} & {r["source_id"] for r in validation}:
        raise ValueError("Training and validation source documents must be separate.")
    if {r["passage"] for r in train} & {r["passage"] for r in validation}:
        raise ValueError("Duplicate passages across training and validation.")
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    def encode(row):
        q = row["question"]
        messages = [{"role":"user", "content": SYSTEM_PROMPT + "\n\n" + _build_user_prompt(row["passage"], Difficulty(q["difficulty"]), 1, QuestionType.MCQ)}]
        prompt = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
        all_ids = tokenizer.apply_chat_template(messages + [{"role":"assistant", "content":json.dumps({"questions":[q]}, ensure_ascii=False)}], tokenize=True)
        if len(all_ids) > 2048:
            raise ValueError("Example exceeds 2048 tokens; shorten the passage without dropping the answer.")
        labels = [-100]*len(prompt) + all_ids[len(prompt):]
        return {"input_ids":all_ids, "attention_mask":[1]*len(all_ids), "labels":labels}
    train_data, valid_data = [encode(r) for r in train], [encode(r) for r in validation]
    model = AutoModelForCausalLM.from_pretrained(args.model, torch_dtype=torch.float16,
                                                attn_implementation="eager", trust_remote_code=True).to("cuda")
    model.config.use_cache = False
    is_phi = "phi" in args.model.lower()
    target_mods = ["qkv_proj", "o_proj"] if is_phi else ["q_proj", "v_proj"]
    model = get_peft_model(model, LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05,
        target_modules=target_mods, task_type="CAUSAL_LM"))
    model.print_trainable_parameters()
    trainer = Trainer(model=model, args=TrainingArguments(output_dir=args.output,
        max_steps=args.steps, per_device_train_batch_size=1, per_device_eval_batch_size=1,
        gradient_accumulation_steps=2, learning_rate=2e-4, fp16=True,
        gradient_checkpointing=True, gradient_checkpointing_kwargs={"use_reentrant":False},
        logging_steps=1, save_strategy="no", eval_strategy="no", report_to="none", seed=42),
        train_dataset=train_data, eval_dataset=valid_data,
        data_collator=DataCollatorForSeq2Seq(tokenizer, padding=True, label_pad_token_id=-100))
    before = trainer.evaluate()
    trained = trainer.train()
    after = trainer.evaluate()
    model.save_pretrained(args.output)
    tokenizer.save_pretrained(args.output)
    report = {"base_model":args.model, "steps":args.steps, "training_examples":len(train),
              "validation_examples":len(validation), "before":before, "after":after,
              "training":trained.metrics,
              "scope":"Pipeline smoke test on authored practice examples; not an evaluated CSS/PPSC model."}
    Path(args.output, "training_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
