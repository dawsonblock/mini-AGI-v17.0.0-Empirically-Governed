class SkillGraph:
    def __init__(self): self.skills={}; self.edges={}
    def add(self,skill): self.skills[skill.skill_id]=skill; self.edges.setdefault(skill.skill_id,set())
    def relate(self,a,b):
        if a not in self.skills or b not in self.skills: raise KeyError('unknown skill')
        self.edges[a].add(b)
    def compose(self,ids):
        ss=[self.skills[i] for i in ids]
        return {'components':list(ids),'procedure':[s for x in ss for s in x.procedure],'verifiers':[x.verifier for x in ss], 'permissions':sorted(set(p for x in ss for p in x.permissions))}
