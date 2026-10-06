from kvcontinual.governance.transfer_rings import *
def test_rings():
 x=[RingScore(TransferRing.R1_NEW_INSTANCE,.4,.5,10),RingScore(TransferRing.R4_NEW_TASK_FAMILY,.4,.6,10)];assert forward_transfer(x)>0 and transfer_breadth(x)==1
