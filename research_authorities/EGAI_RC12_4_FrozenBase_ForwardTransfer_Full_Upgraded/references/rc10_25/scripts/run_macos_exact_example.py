#!/usr/bin/env python3
"""Minimal exact-replay example for Apple Silicon.

Usage after setup:
  python scripts/run_macos_exact_example.py /path/to/local/model

The script uses a tiny two-segment prompt encoded with the model tokenizer,
then runs exact selected replay on MPS when available. It intentionally does
not claim HYPIC acceleration.
"""
from __future__ import annotations
import sys
from transformers import AutoTokenizer
from kvcontinual.backends import TransformersMPSReplayBackend
from kvcontinual.source import SourceSegment, SourceSegmentStore

if len(sys.argv) != 2:
    raise SystemExit("usage: run_macos_exact_example.py <model-name-or-local-path>")
model_path=sys.argv[1]
tok=AutoTokenizer.from_pretrained(model_path)
store=SourceSegmentStore(":memory:")
a=SourceSegment(tok.encode("The selected context begins here. ", add_special_tokens=False), "example:a")
b=SourceSegment(tok.encode("Answer from exactly these selected tokens.", add_special_tokens=False), "example:b")
store.put(a); store.put(b)
backend=TransformersMPSReplayBackend.from_pretrained(store, model_path)
state=backend.exact_selected_replay([a.id,b.id])
print({"device":state.device,"input_tokens":len(state.input_ids),"vocab":int(state.last_logits.shape[0])})
