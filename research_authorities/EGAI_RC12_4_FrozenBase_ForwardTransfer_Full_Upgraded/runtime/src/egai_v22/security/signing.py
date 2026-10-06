import base64
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization
from egai_v22.core.canonical import canonical_json

class ReceiptSigner:
    def __init__(self, private_key=None): self._sk=private_key or Ed25519PrivateKey.generate()
    @property
    def public_key_b64(self):
        raw=self._sk.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        return base64.b64encode(raw).decode()
    def sign_obj(self,obj):
        return base64.b64encode(self._sk.sign(canonical_json(obj).encode())).decode()

class ReceiptVerifier:
    @staticmethod
    def verify_obj(public_key_b64, obj, signature_b64):
        try:
            pk=Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64))
            pk.verify(base64.b64decode(signature_b64), canonical_json(obj).encode())
            return True
        except Exception:
            return False
