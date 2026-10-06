from .world import ReplayNode, GroundedReplayWorld
class ReplayWorldCompiler:
    def from_episode(self,evidence_records):
        nodes=[]
        for i,e in enumerate(evidence_records):
            if not e.is_grounded: continue
            nodes.append(ReplayNode(e.evidence_id,i,{'observation':e.observation},e.action,e.outcome,True,e.parent_evidence[-1] if e.parent_evidence else None))
        return GroundedReplayWorld(nodes)
