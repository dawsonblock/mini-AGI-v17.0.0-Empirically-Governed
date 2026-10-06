from egai_v22.core.models import OriginClass, OutcomeType

class EvidenceAdmissionPolicy:
    def validate(self, record):
        if not 0 <= record.trust <= 1: raise ValueError('trust must be in [0,1]')
        if record.outcome_type in {OutcomeType.MODEL_PREDICTED, OutcomeType.COUNTERFACTUAL}:
            raise ValueError('imagined/counterfactual outcomes are not admissible as authoritative evidence')
        if record.origin_class in {OriginClass.MODEL_INFERENCE, OriginClass.SIMULATION} and record.outcome_type==OutcomeType.OBSERVED:
            raise ValueError('model/simulation origin cannot self-certify an observed outcome')
        if not isinstance(record.provenance,dict) or not record.provenance:
            raise ValueError('provenance required')
        return True
