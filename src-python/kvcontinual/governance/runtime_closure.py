from dataclasses import dataclass,asdict
from egai.common.canonical import digest,validate_digest
@dataclass(frozen=True)
class RuntimeClosure:
    runtime_id:str; base_model_digest:str; governance_qualification_digest:str; execution_deployment_binding_digest:str; hardware_qualification_digest:str; source_root_digest:str; artifact_root_digest:str; rollback_runtime_digest:str=''; policy_digest:str=''
    def __post_init__(self):
        for x in (self.base_model_digest,self.governance_qualification_digest,self.execution_deployment_binding_digest,self.hardware_qualification_digest,self.source_root_digest,self.artifact_root_digest): validate_digest(x)
        for x in (self.rollback_runtime_digest,self.policy_digest):
            if x: validate_digest(x)
    @property
    def digest(self): return digest(asdict(self))
def verify_runtime_closure(c,**expected):
    mapping={'expected_base':'base_model_digest','expected_governance':'governance_qualification_digest','expected_execution':'execution_deployment_binding_digest','expected_hardware':'hardware_qualification_digest','expected_source':'source_root_digest','expected_artifact':'artifact_root_digest'}
    return all(getattr(c,a)==expected[k] for k,a in mapping.items())
