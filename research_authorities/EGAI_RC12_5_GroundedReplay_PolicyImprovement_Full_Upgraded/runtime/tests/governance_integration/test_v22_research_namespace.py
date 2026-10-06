def test_v22_research_modules_import():
 from egai_v22.replay.dream import PolicyDreamEngine
 from egai_v22.replay.selective import TransferSelectiveReplay
 from egai_v22.learning.capacity_probe import CapacityProbe
 from egai_v22.learning.hypotheses import HypothesisRegistry
 assert PolicyDreamEngine and TransferSelectiveReplay and CapacityProbe and HypothesisRegistry
