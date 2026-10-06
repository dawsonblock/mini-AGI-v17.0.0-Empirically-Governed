from kvcontinual.governance.observability import AuditJournal

def test_audit_chain_detects_tamper(tmp_path):
    p=tmp_path/'a.jsonl';j=AuditJournal(p);j.emit('learning','proposal',{'x':1});assert j.verify();p.write_text(p.read_text().replace('"x":1','"x":2'));assert not j.verify()
