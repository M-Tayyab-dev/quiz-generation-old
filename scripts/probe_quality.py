"""Probe whether the local model detects ambiguous alternatives."""
import os
import sys
import json
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ['AI_PROVIDER']='local'
from ai_quiz_agent.providers import complete_json
items=[
 {'q':'Which device is an input device?', 'options':['keyboard','Mouse','Monitor','Printer']},
 {'q':'Which process changes liquid water into water vapour?', 'options':['Evaporation','Freezing','Condensation','Collection']},
 {'q':'What does evaporation change liquid water into?', 'options':['water vapour','steam','ice','snow']},
]
started=time.perf_counter()
r=complete_json('You check exam questions for ambiguity.',
 'For each question, list ALL option indices (zero-based) that can correctly answer it. '
 'There may be more than one correct answer. Include synonyms and overlapping answers. '
 'Evaluate the wording literally, using general knowledge. Do not assume the first option is the only answer. '
 'Return {"answers":[[indices for first question],[indices for second],[indices for third]]}. '
 +json.dumps(items),max_new_tokens=120,
 json_schema={'type':'object','properties':{'answers':{'type':'array','minItems':3,'maxItems':3,
 'items':{'type':'array','minItems':0,'maxItems':4,'items':{'type':'integer','minimum':0,'maximum':3}}}},
 'required':['answers'],'additionalProperties':False})
print(json.dumps({'seconds':round(time.perf_counter()-started,2),'result':r}),flush=True)
