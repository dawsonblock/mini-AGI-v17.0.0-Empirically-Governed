from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from egai.common.canonical import digest
@dataclass(frozen=True)
class TraceEvent:
    event_id:str; t:int; visible_at:int; kind:str; payload:dict[str,Any]; evidence_digest:str=''
@dataclass(frozen=True)
class CompiledPrefix:
    t:int; events:tuple[TraceEvent,...]; prefix_digest:str
@dataclass(frozen=True)
class CompiledReplayWorld:
    episode_id:str; prefixes:tuple[CompiledPrefix,...]; world_digest:str
class ReplayWorldCompiler:
    'Materializes exactly what could have been visible at each historical decision point.'
    def compile(self,episode_id:str,events:list[TraceEvent],max_t:int|None=None)->CompiledReplayWorld:
        if not events: raise ValueError('events required')
        if any(e.visible_at<0 or e.t<0 for e in events): raise ValueError('negative time')
        horizon=max(e.t for e in events) if max_t is None else max_t;prefixes=[]
        for t in range(horizon+1):
            visible=tuple(sorted((e for e in events if e.visible_at<=t and e.t<=t),key=lambda e:(e.visible_at,e.t,e.event_id)))
            prefixes.append(CompiledPrefix(t,visible,digest({'episode':episode_id,'t':t,'events':visible})))
        return CompiledReplayWorld(episode_id,tuple(prefixes),digest({'episode':episode_id,'prefixes':prefixes}))
