from kvcontinual.governance.qualification_stats import qualify_paired

def test_positive_effect_required():
    d=qualify_paired([0]*20,[1]*20,min_effect=.1,samples=200,seed=1);assert d.passed and d.effect.ci_low>0
