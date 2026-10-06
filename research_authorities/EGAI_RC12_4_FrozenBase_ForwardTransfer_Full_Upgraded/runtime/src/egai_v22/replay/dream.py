from egai_v22.replay.objective import ReplayObjective

class PolicyDreamEngine:
    """Evaluate candidate policies on grounded replay prefixes only.
    Policies receive immutable observable prefixes, never the world object or future outcomes.
    """
    def evaluate(self,world,policies,objective=None):
        objective=objective or ReplayObjective(beta_cost=0.0)
        out=[]; max_step=max((n.step for n in world.nodes.values()), default=-1)
        for name,policy in policies.items():
            qualities=[]; decisions=[]; attempts=0; rounds=0
            for step in range(max_step+1):
                prefix=tuple(world.observable_prefix(step))
                decision=policy(prefix); decisions.append(decision); rounds+=1
                if decision is None: continue
                ids=(decision,) if isinstance(decision,str) else tuple(decision) if isinstance(decision,(list,tuple)) else ()
                for node_id in ids:
                    if node_id in world.nodes and world.nodes[node_id].step<=step:
                        val=world.outcome(node_id,step); attempts+=1
                        if isinstance(val,(int,float)): qualities.append(float(val))
                        elif isinstance(val,dict) and isinstance(val.get('score'),(int,float)): qualities.append(float(val['score']))
            best=max(qualities) if qualities else 0.0
            out.append({'policy':name,'score':objective.score(best,attempts,rounds),'best_quality':best,'attempts':attempts,'rounds':rounds,'decisions':decisions})
        return sorted(out,key=lambda x:x['score'],reverse=True)
