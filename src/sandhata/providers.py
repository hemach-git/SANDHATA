"""Model provider interface. Ollama is the default; hosted providers are not enabled yet.

Providers only move text. Every caller validates the reply before using it.
"""
from dataclasses import dataclass
from typing import Protocol

import httpx

from .config import MODEL,MODEL_URL,MODEL_CONTEXT,AppError

DEFAULT_PROVIDER='ollama'

@dataclass(frozen=True)
class Reply:
    content: str
    input_tokens: int|None=None
    output_tokens: int|None=None

    @property
    def usage(self):
        return dict(input_tokens=self.input_tokens,output_tokens=self.output_tokens)

class ModelProvider(Protocol):
    name: str
    model: str
    def generate(self,system:str,user:str,schema:dict,max_tokens:int=6000)->Reply: ...

class OllamaProvider:
    name=DEFAULT_PROVIDER

    def __init__(self,model=MODEL,url=MODEL_URL,context=MODEL_CONTEXT,timeout=240,transport=None):
        self.model=model; self.url=url.rstrip('/'); self.context=context
        self.timeout=timeout; self.transport=transport

    def generate(self,system,user,schema,max_tokens=6000):
        """Return the structured reply text. Transport errors propagate to the caller, which words them safely."""
        with httpx.Client(timeout=self.timeout,transport=self.transport) as client:
            response=client.post(self.url+'/api/chat',json=dict(
                model=self.model,stream=False,format=schema,
                messages=[dict(role='system',content=system),dict(role='user',content=user)],
                options={'temperature':0,'num_ctx':self.context,'num_predict':max_tokens}))
            response.raise_for_status(); payload=response.json()
        return Reply(payload['message']['content'],payload.get('prompt_eval_count'),payload.get('eval_count'))

def get_provider(name=DEFAULT_PROVIDER,model=MODEL,timeout=240):
    """There is deliberately no fallback: an unavailable provider is an error, never a silent switch."""
    if name==DEFAULT_PROVIDER: return OllamaProvider(model=model,timeout=timeout)
    raise AppError('Only the local Ollama provider is enabled.')
