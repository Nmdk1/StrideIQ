"""
Phase 1 foundation fix tests — broken links, dead router, correlation context.
"""
import inspect
import pytest


class TestCorrelationContextPersistedPath:
    """get_correlation_context must use persisted CorrelationFinding, not live engine."""

    def test_no_analyze_correlations_import(self):
        from routers.home import get_correlation_context
        src = inspect.getsource(get_correlation_context)
        assert "from services.correlation_engine" not in src
        assert "analyze_correlations" not in src

    def test_queries_correlation_finding_model(self):
        from routers.home import get_correlation_context
        src = inspect.getsource(get_correlation_context)
        assert "CorrelationFinding" in src
        assert "times_confirmed >= 3" in src or "times_confirmed >=3" in src


class TestLabResultsRouterRemoved:
    """Dead lab-results router must not be registered."""

    def test_lab_results_router_file_deleted(self):
        import importlib
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("routers.lab_results")

    def test_no_lab_results_in_app_routes(self):
        from main import app
        paths = [r.path for r in app.routes if hasattr(r, "path")]
        lab_paths = [p for p in paths if "lab-result" in p.lower() or "lab_result" in p.lower()]
        assert lab_paths == [], f"Dead lab-results routes still registered: {lab_paths}"


class TestBrokenFrontendLinksFixed:
    """Frontend link targets must exist or be removed."""

    def test_no_lab_results_references_in_frontend(self):
        import os
        web_root = os.path.join(os.path.dirname(__file__), "..", "..", "web")
        web_root = os.path.abspath(web_root)
        if not os.path.isdir(web_root):
            pytest.skip("web directory not available in test environment")

        for dirpath, _dirs, files in os.walk(web_root):
            for fname in files:
                if not fname.endswith((".tsx", ".ts", ".jsx", ".js")):
                    continue
                fpath = os.path.join(dirpath, fname)
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                assert "/lab-results" not in content, (
                    f"Broken /lab-results reference in {fpath}"
                )

    def test_privacy_page_has_ai_powered_insights_anchor(self):
        import os
        privacy_page = os.path.join(
            os.path.dirname(__file__), "..", "..", "web", "app", "privacy", "page.tsx"
        )
        privacy_page = os.path.abspath(privacy_page)
        if not os.path.isfile(privacy_page):
            pytest.skip("privacy page not available in test environment")

        with open(privacy_page, "r", encoding="utf-8") as f:
            content = f.read()
        assert 'id="ai-powered-insights"' in content

    def test_settings_page_has_runtoon_anchor(self):
        import os
        settings_page = os.path.join(
            os.path.dirname(__file__), "..", "..", "web", "app", "settings", "page.tsx"
        )
        settings_page = os.path.abspath(settings_page)
        if not os.path.isfile(settings_page):
            pytest.skip("settings page not available in test environment")

        with open(settings_page, "r", encoding="utf-8") as f:
            content = f.read()
        assert 'id="runtoon"' in content
