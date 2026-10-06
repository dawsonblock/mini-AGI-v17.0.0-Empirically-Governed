from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from .canonical import sha256_obj

class OriginClass(str, Enum):
    ENVIRONMENT='environment'; DETERMINISTIC_TOOL='deterministic_tool'; EXTERNAL_SOURCE='external_source'
    MODEL_INFERENCE='model_inference'; SIMULATION='simulation'; HUMAN='human'

class OutcomeType(str, Enum):
    OBSERVED='observed'; REPLAYED_OBSERVED='replayed_observed'; MODEL_PREDICTED='model_predicted'; COUNTERFACTUAL='counterfactual'

class ProposalKind(str, Enum):
    IGNORE='ignore'; BELIEF='belief'; SKILL='skill'; POLICY='policy'; COMPOSITION='composition'; ADAPTER='adapter'; NEW_MODULE='new_module'; SHARED_CONSOLIDATION='shared_consolidation'; ARCHITECTURE='architecture'

@dataclass(frozen=True)
class PredictionRecord:
    prediction: Any; confidence: float; made_at_step: int

@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id:str; timestamp:str; task_id:str; episode_id:str; observation:Any; action:Any; outcome:Any
    origin_class:OriginClass; outcome_type:OutcomeType; provenance:dict
    prediction:Optional[PredictionRecord]=None; parent_evidence:tuple[str,...]=(); artifacts:tuple[str,...]=(); trust:float=1.0
    def digest(self): return sha256_obj(self)
    @property
    def is_grounded(self): return self.outcome_type in {OutcomeType.OBSERVED, OutcomeType.REPLAYED_OBSERVED}

@dataclass
class Belief:
    belief_id:str; claim:str; confidence:float; supporting_evidence:list[str]=field(default_factory=list)
    contradicting_evidence:list[str]=field(default_factory=list); valid_from:Optional[str]=None; valid_to:Optional[str]=None; status:str='active'

@dataclass
class Hypothesis:
    hypothesis_id:str; claim:str; evidence_for:list[str]=field(default_factory=list); evidence_against:list[str]=field(default_factory=list)
    predicted_domains:list[str]=field(default_factory=list); confidence:float=.5; falsification_tests:list[str]=field(default_factory=list); status:str='active'

@dataclass(frozen=True)
class TaskModel:
    task_id:str; observations:tuple[str,...]; actions:tuple[str,...]; goal:str; dynamics:dict; constraints:tuple[str,...]; verifier:str
    def digest(self): return sha256_obj(self)

@dataclass(frozen=True)
class SkillManifest:
    skill_id:str; version:str; description:str; applicability_predicate:str; preconditions:tuple[str,...]; contraindications:tuple[str,...]
    procedure:tuple[str,...]; verifier:str; permissions:tuple[str,...]; resource_budget:dict; termination_conditions:tuple[str,...]
    supporting_evidence:tuple[str,...]; known_failures:tuple[str,...]=(); transfer_score:float=0.0; rollback_target:Optional[str]=None
    def digest(self): return sha256_obj(self)

@dataclass(frozen=True)
class LearningProposal:
    proposal_id:str; kind:ProposalKind; origin_evidence:tuple[str,...]; payload:dict; expected_forward_transfer:float
    predicted_interference:float; capacity_cost:float; risk:float; proposer_version:str; level:int
    def digest(self): return sha256_obj(self)

@dataclass(frozen=True)
class CandidateManifest:
    candidate_id:str; proposal_digest:str; source_digest:str; parent_runtime_digest:str; created_at:str
    def digest(self): return sha256_obj(self)

@dataclass(frozen=True)
class BuildManifest:
    build_id:str; candidate_digest:str; artifact_root_digest:str; builder_version:str; reproducible:bool
    def digest(self): return sha256_obj(self)

@dataclass(frozen=True)
class EvaluationBundle:
    build_digest:str; forward_transfer:float; transfer_breadth:float; learned_retention:float; foundation_retention:float
    calibration_error:float; security_regression:int; unauthorized_mutation:int; provenance_closure:float; compute_cost:float
    capacity_growth:float; ood_score:float; extrapolation_score:float; ablation_uplift:float; ring_scores:dict
    def digest(self): return sha256_obj(self)

@dataclass(frozen=True)
class QualificationRecord:
    build_digest:str; evaluation_digest:str; passed:bool; reasons:tuple[str,...]; policy_version:str; signer_public_key:str=''; signature:str=''
    def unsigned(self):
        d=self.__dict__.copy(); d['signature']=''; return d
    def digest(self): return sha256_obj(self)

@dataclass(frozen=True)
class PromotionDecision:
    build_digest:str; qualification_digest:str; decision:str; authority_version:str; rollback_target:Optional[str]=None
    signer_public_key:str=''; signature:str=''
    def unsigned(self):
        d=self.__dict__.copy(); d['signature']=''; return d
    def digest(self): return sha256_obj(self)

@dataclass(frozen=True)
class RuntimeManifest:
    runtime_id:str; promotion_digest:str; build_digest:str; artifact_root_digest:str; base_model_digest:str; enabled_levels:tuple[int,...]
    def digest(self): return sha256_obj(self)

@dataclass(frozen=True)
class ImprovementRecord:
    improvement_id:str; proposal_digest:str; qualification_digest:str; promotion_digest:str; predicted_forward_transfer:float
    observed_forward_transfer:float; counterfactual_baseline:float; causal_uplift:float; retention_delta:float; compute_delta:float; capacity_delta:float
