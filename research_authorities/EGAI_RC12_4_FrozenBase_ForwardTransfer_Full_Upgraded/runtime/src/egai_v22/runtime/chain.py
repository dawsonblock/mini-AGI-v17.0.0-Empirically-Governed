from egai_v22.core.models import RuntimeManifest
class ManifestChainVerifier:
    def verify(self,proposal,candidate,build,evaluation,qualification,promotion,runtime):
        checks={
            'candidate->proposal': candidate.proposal_digest==proposal.digest(),
            'build->candidate': build.candidate_digest==candidate.digest(),
            'evaluation->build': evaluation.build_digest==build.digest(),
            'qualification->build': qualification.build_digest==build.digest(),
            'qualification->evaluation': qualification.evaluation_digest==evaluation.digest(),
            'promotion->build': promotion.build_digest==build.digest(),
            'promotion->qualification': promotion.qualification_digest==qualification.digest(),
            'runtime->promotion': runtime.promotion_digest==promotion.digest(),
            'runtime->build': runtime.build_digest==build.digest(),
            'runtime->artifact': runtime.artifact_root_digest==build.artifact_root_digest,
            'approved': promotion.decision=='approve' and qualification.passed,
        }
        return all(checks.values()),checks
