from __future__ import annotations
from .model import FrozenModel, FrozenModelIdentity
class MLXFrozenModel(FrozenModel):
    """Lazy MLX-LM backend. No optimizer/update surface is exposed."""
    def __init__(self, model_dir, model_name='mlx-local', max_tokens=2048, temperature=0.0):
        self.identity=FrozenModelIdentity.from_directory(model_name,model_dir,runtime_family='mlx-lm')
        self.model_dir=str(model_dir); self.max_tokens=int(max_tokens); self.temperature=float(temperature); self._model=None; self._tokenizer=None
    @property
    def model_digest(self): return self.identity.digest
    def _load(self):
        if self._model is None:
            try: from mlx_lm import load
            except Exception as e: raise RuntimeError('mlx-lm is required on Apple Silicon') from e
            self._model,self._tokenizer=load(self.model_dir)
    def generate(self,prompt):
        self._load()
        try: from mlx_lm import generate
        except Exception as e: raise RuntimeError('mlx-lm generate unavailable') from e
        kw={'max_tokens':self.max_tokens}
        if self.temperature>0: kw['temp']=self.temperature
        return generate(self._model,self._tokenizer,prompt=prompt,**kw)
