from egai.cognition.mlx_backend import MLXFrozenModel
def test_identity(tmp_path):
 (tmp_path/'config.json').write_text('{}');(tmp_path/'tokenizer.json').write_text('{}');m=MLXFrozenModel(tmp_path);assert m.model_digest.startswith('sha256:')
