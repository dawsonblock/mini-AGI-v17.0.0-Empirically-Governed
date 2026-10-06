from kvcontinual.execution.platforms.stream_provenance import canonicalize_openai_sse
def test_stream():
    lines=['data: {"choices":[{"delta":{"content":"hel"}}]}','data: {"choices":[{"delta":{"content":"lo"}}],"usage":{"completion_tokens":2}}','data: [DONE]']; a=canonicalize_openai_sse({"model":"x"},lines); b=canonicalize_openai_sse({"model":"x"},lines); assert a.assistant_text=="hello" and a.event_chain_digest==b.event_chain_digest and a.usage["completion_tokens"]==2
def test_malformed():
    t=canonicalize_openai_sse({"x":1},['data: nope','data: {"choices":[{"delta":{"content":"x"}}]}','data: [DONE]']); assert t.malformed_events==1 and t.assistant_text=="x"
