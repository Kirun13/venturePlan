from app.config import Settings
from app.graph.workflow import build_graph

def test_mock_graph_compiles():
    assert build_graph("mock") is not None

def test_openai_graph_compiles_without_key():
    assert build_graph("openai") is not None

def test_settings_do_not_require_key_in_mock_mode():
    assert Settings(agent_mode="mock", openai_api_key=None).agent_mode == "mock"
