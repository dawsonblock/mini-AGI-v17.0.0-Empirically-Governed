from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os, subprocess, time, shutil, platform

@dataclass(frozen=True)
class SandboxPolicy:
    timeout_s:float=10.0
    max_memory_bytes:int=512*1024*1024
    max_cpu_s:int=5
    allow_network:bool=False
    allowed_env:tuple[str,...]=()

@dataclass(frozen=True)
class SandboxResult:
    returncode:int; stdout:str; stderr:str; elapsed_s:float; timed_out:bool=False

class LocalSubprocessSandbox:
    'Resource-limited reference boundary. Not a production network-isolation boundary.'
    def __init__(self,policy:SandboxPolicy): self.policy=policy
    def _run_argv(self,argv,cwd,env):
        def preexec():
            try:
                import resource
                resource.setrlimit(resource.RLIMIT_CPU,(self.policy.max_cpu_s,self.policy.max_cpu_s))
                resource.setrlimit(resource.RLIMIT_AS,(self.policy.max_memory_bytes,self.policy.max_memory_bytes))
                resource.setrlimit(resource.RLIMIT_NOFILE,(64,64))
            except Exception: pass
        start=time.monotonic()
        try:
            p=subprocess.run(argv,cwd=str(cwd),env=env,text=True,capture_output=True,timeout=self.policy.timeout_s,
                             preexec_fn=preexec if os.name=='posix' else None)
            return SandboxResult(p.returncode,p.stdout,p.stderr,time.monotonic()-start,False)
        except subprocess.TimeoutExpired as e:
            return SandboxResult(124,e.stdout or '',e.stderr or '',time.monotonic()-start,True)
    def run(self,argv:list[str],cwd:str|Path,*,network_requested:bool=False)->SandboxResult:
        if network_requested and not self.policy.allow_network: raise PermissionError('network capability denied')
        env={k:os.environ[k] for k in self.policy.allowed_env if k in os.environ}; env['PATH']=os.environ.get('PATH','/usr/bin:/bin')
        return self._run_argv(argv,cwd,env)

class HardenedSubprocessSandbox(LocalSubprocessSandbox):
    'OS-backed network-denial wrapper. In production mode it fails closed if no enforceable backend exists.'
    def __init__(self,policy:SandboxPolicy,*,require_hardened:bool=True,backend:str='auto'):
        super().__init__(policy); self.require_hardened=require_hardened; self.backend=backend
    def selected_backend(self)->str|None:
        if self.backend!='auto': return None if self.backend=='none' else self.backend
        if platform.system()=='Darwin' and shutil.which('sandbox-exec'): return 'sandbox-exec'
        if platform.system()=='Linux' and shutil.which('bwrap'): return 'bwrap'
        return None
    def _wrapped(self,argv:list[str],cwd:Path)->list[str]:
        backend=self.selected_backend()
        if self.policy.allow_network: return argv
        if backend=='sandbox-exec':
            return ['sandbox-exec','-p','(version 1) (allow default) (deny network*)',*argv]
        if backend=='bwrap':
            return ['bwrap','--die-with-parent','--unshare-net','--ro-bind','/','/','--bind',str(cwd),str(cwd),'--chdir',str(cwd),*argv]
        if self.require_hardened: raise RuntimeError('no hardened sandbox backend available; refusing untrusted execution')
        return argv
    def run(self,argv:list[str],cwd:str|Path,*,network_requested:bool=False)->SandboxResult:
        if network_requested and not self.policy.allow_network: raise PermissionError('network capability denied')
        cwd=Path(cwd).resolve(); env={k:os.environ[k] for k in self.policy.allowed_env if k in os.environ}; env['PATH']=os.environ.get('PATH','/usr/bin:/bin')
        return self._run_argv(self._wrapped(argv,cwd),cwd,env)
