#!/usr/bin/env python3
from __future__ import annotations

import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.request


def check(name: str, ok: bool, detail: str) -> bool:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    return ok


def _cmd(args: list[str]) -> str:
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT, timeout=5).strip()
    except Exception:
        return ""


def _version(pkg: str) -> str:
    try:
        return importlib.metadata.version(pkg)
    except Exception:
        return "-"


def main() -> int:
    results: list[bool] = []
    is_mac = platform.system() == "Darwin"
    is_arm = platform.machine().lower() in {"arm64", "aarch64"}
    results.append(check("OS", is_mac, f"{platform.system()} {platform.release()}"))
    results.append(check("CPU", is_arm, platform.machine()))
    chip = _cmd(["sysctl", "-n", "machdep.cpu.brand_string"]) or _cmd(["sysctl", "-n", "hw.model"])
    if chip:
        print(f"[INFO] Apple hardware: {chip}")

    mem = None
    if is_mac:
        try:
            mem = int(_cmd(["sysctl", "-n", "hw.memsize"]))
        except Exception:
            pass
    if mem:
        gib = mem / (1024 ** 3)
        results.append(check("Unified memory", gib >= 16, f"{gib:.1f} GiB"))
    else:
        print("[WARN] Unified memory: could not query hw.memsize")

    results.append(check("Python", sys.version_info >= (3, 11), sys.version.split()[0]))
    results.append(check("Native Python", is_arm and sys.maxsize > 2**32, f"machine={platform.machine()} bits={64 if sys.maxsize > 2**32 else 32}"))
    results.append(check("Xcode/Metal tools", bool(shutil.which("xcrun")), shutil.which("xcrun") or "-"))

    llama = shutil.which("llama-server")
    mlx_server = shutil.which("mlx_lm.server") or shutil.which("mlx_lm")
    results.append(check("Inference backend", bool(llama or mlx_server), f"llama-server={llama or '-'} mlx={mlx_server or '-'}"))
    print(f"[INFO] mlx={_version('mlx')} mlx-lm={_version('mlx-lm')}")
    if llama:
        v = _cmd([llama, "--version"]).splitlines()[:1]
        print(f"[INFO] llama-server version: {v[0] if v else 'unknown'}")

    endpoint = os.getenv("KVCONTINUAL_MODEL_ENDPOINT", "http://127.0.0.1:8080/v1")
    try:
        with urllib.request.urlopen(endpoint.rstrip("/") + "/models", timeout=2) as response:
            body = json.loads(response.read().decode("utf-8"))
            results.append(check("Backend API", response.status < 400, f"{endpoint} models={len(body.get('data', []))}"))
    except Exception as exc:
        print(f"[WARN] Backend API: not running at {endpoint}: {exc}")

    print("\nRC12.4 Apple profile priorities:")
    print("1. MLX or llama.cpp/Metal execution with quantized frozen weights.")
    print("2. Bounded prompt/memory injection to reduce prefill.")
    print("3. Streaming TTFT + decode-throughput benchmarking.")
    print("4. Feature-detected speculative decoding for llama.cpp when a draft model is explicitly configured.")
    print("5. Native GDN/Metal and HYPIC remain fail-closed for production until exact target-hardware differential qualification passes.")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
