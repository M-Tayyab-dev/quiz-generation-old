"""Lazy model providers: API on CPU, or Hugging Face on a Colab GPU."""
import json
import os
import threading
from .generation_control import remaining_seconds
from functools import lru_cache


def parse_json(text):
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Model must return a JSON object.")
    return data


class HuggingFaceProvider:
    def __init__(self, model_id=None, adapter=None):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        try:
            from transformers.cache_utils import DynamicCache
            if not hasattr(DynamicCache, "get_usable_length"):
                DynamicCache.get_usable_length = lambda self, n=0, l=0: self.get_seq_length(l)
            if not hasattr(DynamicCache, "seen_tokens"):
                DynamicCache.seen_tokens = property(lambda self: self.get_seq_length())
            if not hasattr(DynamicCache, "get_max_length"):
                DynamicCache.get_max_length = lambda self: getattr(self, "max_cache_len", None)
        except Exception:
            pass
        self.torch = torch
        self.lock = threading.Lock()
        self.model_id = model_id or os.getenv("HF_MODEL", "microsoft/Phi-3.5-mini-instruct")
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_id, trust_remote_code=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_id, torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            device_map="auto", attn_implementation="eager", trust_remote_code=True,
        )
        adapter = adapter or os.getenv("HF_ADAPTER")
        if adapter:
            from peft import PeftModel
            self.model = PeftModel.from_pretrained(self.model, adapter)
        self.model.eval()

    def complete(self, system, user, max_new_tokens=1800):
        with self.lock, self.torch.inference_mode():
            # Phi-3.5 uses <|user|> / <|assistant|> chat format via apply_chat_template.
            # Combine system+user into a single user message for broad model compatibility.
            combined = system + "\n\n" + user
            prompt = self.tokenizer.apply_chat_template(
                [{"role": "user", "content": combined}],
                tokenize=False, add_generation_prompt=True,
            )
            inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
            if inputs.input_ids.shape[1] + max_new_tokens > 32768:
                raise ValueError("Passage is too long for this quiz request; select a smaller section.")
            output = self.model.generate(**inputs, max_new_tokens=max_new_tokens,
                do_sample=True, temperature=0.3, top_p=0.9,
                pad_token_id=self.tokenizer.eos_token_id)
            text = self.tokenizer.decode(output[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
        return parse_json(text)


@lru_cache(maxsize=1)
def get_hf_provider():
    return HuggingFaceProvider()


def _generate_local_fallback(system, user, json_schema=None):
    import re
    sources_match = re.search(r'Sources:\s*(\{.*?\})\n', user)
    count_match = re.search(r'Create exactly (\d+)', user)
    
    if sources_match:
        try:
            sources = json.loads(sources_match.group(1))
        except Exception:
            sources = {}
        target_count = int(count_match.group(1)) if count_match else len(sources)
        items = []
        all_candidates = []
        
        verb_re = re.compile(r'^(.*?)\s+(?:is|are|was|were|has|have|had|converts|changes|causes|occurs|refers|means)\b', re.I)
        
        for idx_str in sorted(sources.keys(), key=lambda x: int(x)):
            s_text = sources[idx_str].strip()
            vm = verb_re.match(s_text)
            if vm and 1 <= len(vm.group(1).split()) <= 4:
                term = vm.group(1).strip().strip(',;:')
            else:
                caps = re.findall(r'\b[A-Z][a-zA-Z0-9_-]+\b', s_text)
                if caps:
                    term = caps[0]
                else:
                    words = [w for w in re.findall(r'\b[a-zA-Z]{4,}\b', s_text)
                             if w.lower() not in {'this', 'that', 'with', 'from', 'have', 'were', 'been', 'which', 'their', 'when', 'into'}]
                    term = words[0] if words else s_text.split()[0]
            all_candidates.append(term)
            
        unique_candidates = list(dict.fromkeys(c for c in all_candidates if c))
        
        for i in range(min(target_count, len(sources))):
            s_idx = i
            s_text = sources[str(i)].strip() if str(i) in sources else list(sources.values())[i].strip()
            
            ans = all_candidates[i] if i < len(all_candidates) and all_candidates[i] in s_text else None
            if not ans:
                for cand in unique_candidates:
                    if cand in s_text:
                        ans = cand
                        break
            if not ans:
                caps = [w for w in re.findall(r'\b[A-Za-z0-9_-]+\b', s_text) if w in s_text]
                ans = caps[0] if caps else s_text.split()[0]
                
            if s_text.startswith(ans):
                blanked = s_text[len(ans):].lstrip(' ,-:')
                q = f"Which subject completes this statement: \"_____ {blanked}\"?"
            else:
                q = f"According to the notes: \"{s_text.replace(ans, '_____')}\" — what fits the blank?"
                
            distractors = [c for c in unique_candidates if c.lower() != ans.lower() and c.lower() not in s_text.lower()]
            fallback_distractors = ["Alternative process", "Secondary component", "External variable", "Related concept", "Tertiary factor"]
            d_idx = 0
            while len(distractors) < 3:
                distractors.append(fallback_distractors[d_idx % len(fallback_distractors)])
                d_idx += 1
                
            items.append({
                "s": s_idx,
                "a": ans,
                "q": q,
                "d": distractors[:3]
            })
            
        return {"items": items}
        
    return {"questions": []}


def complete_json(system, user, model=None, max_new_tokens=1800, json_schema=None):
    provider = os.getenv("AI_PROVIDER", "huggingface").lower()
    if provider == "local":
        import httpx
        response = httpx.post(
            os.getenv("LOCAL_MODEL_URL", "http://127.0.0.1:8081/v1/chat/completions"),
            json={"model": "quiz-local", "messages": [
                {"role": "system", "content": system}, {"role": "user", "content": user}],
                "response_format": {"type": "json_object", **({"schema": json_schema} if json_schema else {})}, "temperature": 0,
                "max_tokens": max_new_tokens}, timeout=remaining_seconds(), trust_env=False)
        response.raise_for_status()
        choice = response.json()["choices"][0]
        if choice.get('finish_reason') == 'length':
            raise ValueError('Model reached the output limit before finishing the quiz.')
        return parse_json(choice["message"]["content"])
    if provider == "huggingface":
        try:
            return get_hf_provider().complete(system, user, max_new_tokens)
        except (ModuleNotFoundError, ImportError):
            return _generate_local_fallback(system, user, json_schema)
    if provider != "openai":
        raise ValueError("AI_PROVIDER must be local, huggingface or openai.")
    from .config import get_openai_client, settings
    response = get_openai_client().chat.completions.create(
        model=model or settings.OPENAI_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format={"type": "json_object"}, temperature=0.35,
    )
    return parse_json(response.choices[0].message.content)
