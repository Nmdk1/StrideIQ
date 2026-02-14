"""Performance Tests for run stream analysis — AC-5.

Marker-gated: run with `pytest -m perf`.

Measurement context (from AC-5):
    - Docker env (equivalent compute)
    - 3.6k points, 7 channels
    - Warm run (first invocation discarded)
    - 100 invocations
    - numpy.percentile for p95/p99

Budgets:
    - p95 <= 200ms at 3.6k points
    - p99 <= 350ms at 3.6k points
"""
import sys
import time
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fixtures.stream_fixtures import make_easy_run_stream

pytestmark = pytest.mark.perf


class TestAnalysisLatency:
    """AC-5: Tool latency budget."""

    def _run_benchmark(self, stream, n_runs=100):
        """Run analysis n_runs times and return timings in ms."""
        from services.run_stream_analysis import analyze_stream

        channels = list(stream.keys())

        # Warm-up (discarded)
        analyze_stream(stream, channels)

        timings = []
        for _ in range(n_runs):
            start = time.perf_counter()
            analyze_stream(stream, channels)
            elapsed_ms = (time.perf_counter() - start) * 1000
            timings.append(elapsed_ms)

        return timings

    def test_p95_under_200ms_3600_points(self):
        """3.6k points, 7 channels → p95 <= 200ms."""
        import numpy as np

        stream = make_easy_run_stream(duration_s=3600)
        timings = self._run_benchmark(stream, n_runs=100)

        p95 = np.percentile(timings, 95)
        p99 = np.percentile(timings, 99)

        assert p95 <= 200.0, f"p95={p95:.1f}ms exceeds 200ms budget"
        assert p99 <= 350.0, f"p99={p99:.1f}ms exceeds 350ms budget"

    def test_p99_under_350ms_3600_points(self):
        """Explicit p99 check at 3.6k points."""
        import numpy as np

        stream = make_easy_run_stream(duration_s=3600)
        timings = self._run_benchmark(stream, n_runs=100)

        p99 = np.percentile(timings, 99)
        assert p99 <= 350.0, f"p99={p99:.1f}ms exceeds 350ms budget"

    def test_7200_points_within_2x_budget(self):
        """7.2k points → p99 <= 700ms (2x budget, fail threshold)."""
        import numpy as np

        stream = make_easy_run_stream(duration_s=7200)
        timings = self._run_benchmark(stream, n_runs=50)

        p99 = np.percentile(timings, 99)
        assert p99 <= 700.0, f"p99={p99:.1f}ms exceeds 700ms (2x budget)"

    def test_no_oom_on_large_stream(self):
        """7.2k points → no memory errors or crashes."""
        from services.run_stream_analysis import analyze_stream

        stream = make_easy_run_stream(duration_s=7200)
        channels = list(stream.keys())

        # Should complete without exception
        result = analyze_stream(stream, channels)
        assert result is not None
        assert result.point_count == 7200
