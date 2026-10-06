from __future__ import annotations
from dataclasses import dataclass, asdict
import hashlib, json
from typing import Any, Iterable

def _canon(obj: Any) -> bytes:
    return json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")

def sha256_obj(obj: Any) -> str:
    return "sha256:"+hashlib.sha256(_canon(obj)).hexdigest()

@dataclass(frozen=True)
class StreamTranscript:
    request_digest:str
    event_count:int
    assistant_text:str
    assistant_text_digest:str
    usage:dict[str,Any]
    event_chain_digest:str
    malformed_events:int=0
    def to_dict(self): return asdict(self)

def canonicalize_openai_sse(request_body:dict[str,Any],lines:Iterable[str|bytes])->StreamTranscript:
    prev="sha256:"+"0"*64
    parts=[]; usage={}; count=0; malformed=0
    for raw in lines:
        line=raw.decode("utf-8","replace") if isinstance(raw,bytes) else str(raw)
        line=line.strip()
        if not line.startswith("data:"): continue
        payload=line[5:].strip()
        if payload=="[DONE]": break
        try: event=json.loads(payload)
        except json.JSONDecodeError:
            malformed+=1; continue
        count+=1
        prev=sha256_obj({"prev":prev,"event_index":count,"event":event})
        try:
            content=(event["choices"][0].get("delta") or {}).get("content") or ""
            if isinstance(content,str) and content: parts.append(content)
        except Exception: pass
        if isinstance(event.get("usage"),dict) and event["usage"]: usage=event["usage"]
    text="".join(parts)
    return StreamTranscript(sha256_obj(request_body),count,text,"sha256:"+hashlib.sha256(text.encode()).hexdigest(),usage,prev,malformed)
