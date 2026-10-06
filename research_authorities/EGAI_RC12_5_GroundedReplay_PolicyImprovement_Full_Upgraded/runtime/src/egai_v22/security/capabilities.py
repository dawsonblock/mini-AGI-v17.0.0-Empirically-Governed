from dataclasses import dataclass

@dataclass(frozen=True)
class Capability:
    name: str
    _nonce: object

class CapabilityAuthority:
    """Creates process-local unforgeable-ish object capabilities. Never serialize these tokens."""
    def __init__(self):
        self._nonce = object()
    def issue(self, name: str) -> Capability:
        return Capability(name, self._nonce)
    def validate(self, cap: Capability, expected: str) -> bool:
        return isinstance(cap, Capability) and cap.name == expected and cap._nonce is self._nonce
