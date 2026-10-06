from __future__ import annotations
from dataclasses import dataclass

RELEASE_VERSION='12.5.0'
RELEASE_NAME='EGAI_RC12_3_1_TargetMac_Qualification_Full_Upgraded'

@dataclass(frozen=True)
class ReleaseIdentity:
    version:str=RELEASE_VERSION
    name:str=RELEASE_NAME
    authority_model:str='cognitive-learning-verification-promotion-v1'
