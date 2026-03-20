import inspect


def test_knowledge_extraction_uses_model_resolver():
    from services.knowledge_extraction_ai import _call_ai

    source = inspect.getsource(_call_ai)
    assert "resolve_knowledge_model" in source
    assert "call_llm(" in source


def test_knowledge_extraction_no_hardcoded_sonnet_string():
    from services.knowledge_extraction_ai import _call_ai

    source = inspect.getsource(_call_ai)
    assert 'model="claude-sonnet-4-6"' not in source
    assert "model = \"claude-sonnet-4-6\"" not in source
