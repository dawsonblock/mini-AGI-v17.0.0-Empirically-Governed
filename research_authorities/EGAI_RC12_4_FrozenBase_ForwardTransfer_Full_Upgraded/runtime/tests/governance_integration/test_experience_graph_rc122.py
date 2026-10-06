from kvcontinual.governance.experience_graph import ExperienceGraph

def test_graph_links_derived_objects(tmp_path):
    g=ExperienceGraph(tmp_path/'x.db');g.add_node('e','evidence',{'x':1});g.add_node('s','skill',{'name':'repair'});g.link('e','supports','s','sha256:'+'0'*64)
    n=g.neighbors('e','supports');assert n[0][1].node_id=='s'
