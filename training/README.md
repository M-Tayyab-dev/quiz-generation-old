# Training and evaluation

The included 8 training, 2 validation and 2 test examples are assistant-authored arithmetic fixtures. They verify that LoRA updates, checkpoint saving and inference work. They are not a CSS/PPSC past-paper corpus, are not human-reviewed, and cannot demonstrate exam readiness. Their shared template also makes held-out loss an optimistic technical check, not a generalization benchmark.

Train in Colab from the project directory:

```python
!python -m training.train_lora --steps 8
```

This saves a LoRA adapter, tokenizer and before/after loss report under `artifacts/quiz-lora-smoke`. Base weights are downloaded separately from `Qwen/Qwen2.5-1.5B-Instruct`. Set `HF_ADAPTER` to this directory before the inference provider is first loaded. Fine-tuning optimizes assistant-answer tokens only; source prompts and padding are masked from loss. Nothing is uploaded to Hugging Face.

## Real exam training

Curate authorized study passages and reviewed MCQs for English/Urdu, Pakistan Affairs, current affairs, Islamic Studies or Civics/Ethics, science, quantitative reasoning, computer skills and job-specific subjects. The exam profile is a practice label, not a verified official paper blueprint. Use the current advertisement/syllabus for each post. CSS written exam essays and descriptive answers are outside this MCQ workflow.

Each JSONL record needs `source_id`, `passage` and `question` matching the sample schema. Retain source URL/title, publication date, permission/license and reviewer metadata. Date current-affairs facts. Keep source documents and near-duplicate questions separate across train/validation/test. Have a subject reviewer verify the answer, explanation, source support, distractors and difficulty.

Train on the curated files by overriding `--train`, `--validation`, `--steps` and `--output`. Reserve the test set until development is complete. Compare pretrained and fine-tuned generation on the same held-out documents; report answer accuracy, factual support, ambiguity, distractor quality, duplicate rate, difficulty alignment, language quality and latency. A source-quote match is a useful check but does not prove that the answer follows from the quote.

Official syllabus starting points:
- https://www.fpsc.gov.pk/Syllabuses?section=GR+Syllabus
- https://www.fpsc.gov.pk/assets/media/2024-10-22-01-45-26-Syllabus_for_CE-2016_and_onwards.pdf
- https://www.ppsc.gop.pk/

Model: https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct
