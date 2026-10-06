from egai_v22.core.models import *
from egai_v22.storage.sqlite_store import SQLiteAuthorityStore
from egai_v22.evidence.service import EvidenceAdmissionService
from egai_v22.learning.capacity_probe import CapacityProbe
from egai_v22.learning.plasticity import DeterministicPlasticityProposer
from egai_v22.replay.world import ReplayNode,GroundedReplayWorld
from egai_v22.replay.dream import PolicyDreamEngine
from egai_v22.verification.qualify import QualificationPolicy
from egai_v22.security.signing import ReceiptSigner
from egai_v22.promotion.authority import PromotionAuthority
from egai_v22.runtime.chain import ManifestChainVerifier


def main():
    store=SQLiteAuthorityStore(); admission=EvidenceAdmissionService(store)
    ev=EvidenceRecord('E1','2026-10-05T00:00:00Z','debug','ep1',{'test':'fail'},{'action':'isolate_dependency'},{'score':1},OriginClass.DETERMINISTIC_TOOL,OutcomeType.OBSERVED,{'tool':'tests','exit':0})
    admission.admit(ev)
    world=GroundedReplayWorld([ReplayNode('n0',0,{'test':'fail'},'isolate',{'score':1},True)])
    dream=PolicyDreamEngine().evaluate(world,{'reuse-known':lambda prefix:'n0'})
    diagnosis=CapacityProbe().diagnose(procedure_failure=False,representation_bottleneck=False,repeated_verified_count=1)
    proposal=DeterministicPlasticityProposer().propose('P1',['E1'],'dependency-debug',skill_sufficient=True,diagnosis=diagnosis,expected_transfer=.10)
    candidate=CandidateManifest('C1',proposal.digest(),'sha256:'+'1'*64,'sha256:'+'2'*64,'2026-10-05T00:00:00Z')
    build=BuildManifest('B1',candidate.digest(),'sha256:'+'3'*64,'builder-v2.2',True)
    evaluation=EvaluationBundle(build.digest(),.10,.25,.995,.997,.03,0,0,1.0,.02,0,.08,.03,.07,{'R1':.12,'R2':.08,'R3':.03})
    q=QualificationPolicy().qualify(build,evaluation,ReceiptSigner())
    d=PromotionAuthority().decide(build,evaluation,q,store,'skill:dependency-debug',{'procedure':['isolate','test','compare','rollback']})
    runtime=RuntimeManifest('R1',d.digest(),build.digest(),build.artifact_root_digest,'sha256:'+'4'*64,(0,1,2,3,4,5))
    ok,checks=ManifestChainVerifier().verify(proposal,candidate,build,evaluation,q,d,runtime)
    print({'version':'2.2.0','evidence_chain':store.verify_chains(),'dream':dream[0]['score'],'qualified':q.passed,'promoted':d.decision,'manifest_chain':ok,'runtime_checks':checks})
if __name__=='__main__': main()
