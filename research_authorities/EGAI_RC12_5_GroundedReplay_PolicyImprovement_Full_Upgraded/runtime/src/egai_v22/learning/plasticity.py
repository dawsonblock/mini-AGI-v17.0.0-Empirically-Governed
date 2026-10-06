from egai_v22.core.models import LearningProposal, ProposalKind
LEVEL={ProposalKind.IGNORE:0,ProposalKind.BELIEF:2,ProposalKind.SKILL:3,ProposalKind.POLICY:4,ProposalKind.COMPOSITION:5,ProposalKind.ADAPTER:6,ProposalKind.NEW_MODULE:7,ProposalKind.SHARED_CONSOLIDATION:8,ProposalKind.ARCHITECTURE:9}

class DeterministicPlasticityProposer:
    def __init__(self,version='rule-v2.1',max_enabled_level=5): self.version=version; self.max_enabled_level=max_enabled_level
    def propose(self,proposal_id,origin_evidence,gap,*,memory_sufficient=False,skill_sufficient=False,composition_sufficient=False,diagnosis=None,expected_transfer=0,predicted_interference=0,capacity_cost=0,risk=0):
        if memory_sufficient: kind=ProposalKind.BELIEF
        elif skill_sufficient: kind=ProposalKind.SKILL
        elif composition_sufficient: kind=ProposalKind.COMPOSITION
        elif diagnosis and diagnosis.genuine_capacity_candidate: kind=ProposalKind.ADAPTER
        else: kind=ProposalKind.SKILL
        if LEVEL[kind]>self.max_enabled_level: kind=ProposalKind.SKILL
        return LearningProposal(proposal_id,kind,tuple(origin_evidence),{'capability_gap':gap},expected_transfer,predicted_interference,capacity_cost,risk,self.version,LEVEL[kind])
