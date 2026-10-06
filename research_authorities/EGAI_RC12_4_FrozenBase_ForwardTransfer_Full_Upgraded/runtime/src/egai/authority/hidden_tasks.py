from __future__ import annotations
import base64, json, os
from dataclasses import dataclass, asdict
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from egai.bench.dataset import encode_cases, decode_cases
from egai.common.canonical import canonical_bytes, sha256_bytes, digest


@dataclass(frozen=True)
class SealedTaskSuite:
    suite_id: str
    generation: int
    algorithm: str
    nonce_b64: str
    ciphertext_b64: str
    aad_digest: str

    @property
    def sealed_digest(self) -> str:
        return digest(asdict(self))


class HiddenTaskVault:
    """Encrypted hidden-task container.

    The learner-facing object contains no plaintext cases. Production deployments should keep
    the AES key and the evaluator in a separate verifier process/OS account. This class provides
    the sealed artifact and strict binding semantics; process isolation remains an operational gate.
    """
    ALGORITHM="AES-256-GCM"

    @staticmethod
    def generate_key() -> bytes:
        return AESGCM.generate_key(bit_length=256)

    @classmethod
    def seal(cls, suite_id: str, generation: int, cases, key: bytes) -> SealedTaskSuite:
        if len(key) != 32:
            raise ValueError("AES-256-GCM requires 32-byte key")
        aad=canonical_bytes({"suite_id":suite_id,"generation":generation,"algorithm":cls.ALGORITHM})
        nonce=os.urandom(12)
        ct=AESGCM(key).encrypt(nonce,encode_cases(cases),aad)
        return SealedTaskSuite(suite_id,generation,cls.ALGORITHM,base64.b64encode(nonce).decode(),base64.b64encode(ct).decode(),sha256_bytes(aad))

    @staticmethod
    def open(sealed: SealedTaskSuite, key: bytes):
        if sealed.algorithm != HiddenTaskVault.ALGORITHM:
            raise ValueError("unsupported task-vault algorithm")
        aad=canonical_bytes({"suite_id":sealed.suite_id,"generation":sealed.generation,"algorithm":sealed.algorithm})
        if sha256_bytes(aad) != sealed.aad_digest:
            raise ValueError("hidden-suite AAD binding mismatch")
        pt=AESGCM(key).decrypt(base64.b64decode(sealed.nonce_b64),base64.b64decode(sealed.ciphertext_b64),aad)
        return decode_cases(pt)

    @staticmethod
    def write(path: str|Path, sealed: SealedTaskSuite) -> None:
        Path(path).write_text(json.dumps(asdict(sealed),sort_keys=True,separators=(",",":")),encoding="utf-8")

    @staticmethod
    def read(path: str|Path) -> SealedTaskSuite:
        return SealedTaskSuite(**json.loads(Path(path).read_text(encoding="utf-8")))
