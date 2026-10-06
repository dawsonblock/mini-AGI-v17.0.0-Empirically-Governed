from kvcontinual.governance.replay_compiler import *

def test_prefix_compiler_excludes_future():
    w=ReplayWorldCompiler().compile('ep',[TraceEvent('a',0,0,'obs',{'x':0}),TraceEvent('b',2,2,'result',{'future':1})])
    assert [e.event_id for e in w.prefixes[0].events]==['a']
    assert [e.event_id for e in w.prefixes[1].events]==['a']
