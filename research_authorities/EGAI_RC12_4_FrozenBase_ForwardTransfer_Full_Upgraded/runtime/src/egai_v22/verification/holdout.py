from egai_v22.core.canonical import sha256_obj

class FreshTaskAuthority:
    """Commits to hidden tasks before release and allows each task to be issued once."""
    def __init__(self,tasks):
        self._tasks=dict(tasks); self._released=set()
        self.commitments={k:sha256_obj(v) for k,v in self._tasks.items()}
        self.root_commitment=sha256_obj(self.commitments)
    def issue(self,task_id):
        if task_id not in self._tasks: raise KeyError(task_id)
        if task_id in self._released: raise RuntimeError('fresh task already released')
        self._released.add(task_id); return self._tasks[task_id]
    def has_been_released(self,task_id): return task_id in self._released
    def verify_released(self,task_id,task): return self.commitments.get(task_id)==sha256_obj(task)
