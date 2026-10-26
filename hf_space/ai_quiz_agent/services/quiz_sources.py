"""Choose short source sentences across a document for compact model prompts."""
import re

# Administrative text is not study material. This is source filtering, not
# question generation; the model still writes every question and its options.
_ADMIN = re.compile(r'^(?:this (?:authored )?(?:handout|document|paper)\b|'
                    r'generate \w+ .*questions\b|every answer must\b|'
                    r'this is not an official\b|(?:copyright|all rights reserved)\b)', re.I)


def select_sentences(text, count):
    normalized = ' '.join(text.split())
    sentences = re.split(r'(?<=[.!?\u06d4])\s+', normalized)
    candidates = list(dict.fromkeys(s.strip() for s in sentences
        if 25 <= len(s.strip()) <= 350 and not _ADMIN.search(s.strip())))
    if len(candidates) < count:
        raise ValueError(f'The document has only {len(candidates)} usable factual sentences. Request fewer questions or add more typed notes.')
    take = min(len(candidates), max(count, min(count * 2, 18)))
    chosen = [candidates[round(i * (len(candidates)-1) / max(take-1, 1))] for i in range(take)]
    # Keep whole quotes, never cut a sentence in the middle.
    while sum(map(len, chosen)) > 3600 and len(chosen) > count:
        chosen.pop(1)
    return chosen
