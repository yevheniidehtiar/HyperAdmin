"""Unit tests for load-test baseline parsing and regression comparison (#263)."""

from examples.erp.loadtest import baselines as bl

_HEADER = (
    "Type,Name,Request Count,Failure Count,Median Response Time,Average Response Time,"
    "Min Response Time,Max Response Time,Average Content Size,Requests/s,Failures/s,"
    "50%,66%,75%,80%,90%,95%,98%,99%,99.9%,99.99%,100%"
)


def _row(name, *, count=100, failures=0, p50=10, p95=100, p99=120, rps=5.0, typ="GET"):
    cells = [typ, name, count, failures, p50, 12, 3, 200, 0, rps, 0]
    cells += [p50, 30, 40, 50, 80, p95, 110, p99, 200, 220, 250]
    return ",".join(str(c) for c in cells)


def _csv(*rows):
    return "\n".join([_HEADER, *rows, ""])


class TestParse:
    def test_parses_rows_into_stats(self):
        text = _csv(_row("GET /admin/contact [list]", count=200, failures=2, p95=90, rps=12.5))
        stats = bl.parse_locust_stats(text)
        s = stats["GET /admin/contact [list]"]
        assert s.count == 200
        assert s.error_rate == 0.01
        assert s.p95 == 90
        assert s.throughput == 12.5

    def test_blank_name_rows_skipped(self):
        text = _csv(_row("", count=500), _row("GET /admin/invoice [list]"))
        stats = bl.parse_locust_stats(text)
        assert list(stats) == ["GET /admin/invoice [list]"]

    def test_zero_count_yields_zero_error_rate(self):
        text = _csv(_row("GET /x", count=0, failures=0))
        assert bl.parse_locust_stats(text)["GET /x"].error_rate == 0.0


class TestCompare:
    def test_no_regression_when_within_thresholds(self):
        base = bl.parse_locust_stats(_csv(_row("a", p95=100)))
        cur = bl.parse_locust_stats(_csv(_row("a", p95=150)))  # 150 < 2*100
        assert bl.compare(base, cur) == []

    def test_p95_regression_when_over_factor(self):
        base = bl.parse_locust_stats(_csv(_row("a", p95=100)))
        cur = bl.parse_locust_stats(_csv(_row("a", p95=250)))  # 250 > 2*100
        regs = bl.compare(base, cur)
        assert len(regs) == 1
        assert regs[0].kind == "p95"
        assert regs[0].threshold == 200.0

    def test_error_rate_regression(self):
        base = bl.parse_locust_stats(_csv(_row("a", count=100, failures=0, p95=100)))
        cur = bl.parse_locust_stats(_csv(_row("a", count=100, failures=2, p95=100)))  # 2%>1%
        regs = bl.compare(base, cur)
        assert [r.kind for r in regs] == ["error_rate"]

    def test_new_endpoint_is_not_a_regression(self):
        base = bl.parse_locust_stats(_csv(_row("a", p95=100)))
        cur = bl.parse_locust_stats(_csv(_row("a", p95=120), _row("b", p95=9999)))
        # 'b' has no baseline -> no p95 regression; only error-rate could flag it (it won't).
        assert bl.compare(base, cur) == []

    def test_custom_thresholds_respected(self):
        base = bl.parse_locust_stats(_csv(_row("a", p95=100)))
        cur = bl.parse_locust_stats(_csv(_row("a", p95=130)))
        assert bl.compare(base, cur, p95_factor=1.2) != []  # 130 > 1.2*100


class TestRoundTripAndTable:
    def test_save_load_roundtrip(self, tmp_path):
        stats = bl.parse_locust_stats(_csv(_row("a", p95=100), _row("b", p95=80)))
        path = tmp_path / "baseline.json"
        bl.save_baseline(path, stats)
        loaded = bl.load_baseline(path)
        assert loaded == stats

    def test_render_table_marks_regression(self):
        base = bl.parse_locust_stats(_csv(_row("a", p95=100)))
        cur = bl.parse_locust_stats(_csv(_row("a", p95=300)))
        regs = bl.compare(base, cur)
        table = bl.render_table(base, cur, regs)
        assert "REGRESSED p95" in table


class TestCli:
    def test_update_baseline_writes_and_exits_zero(self, tmp_path):
        stats_csv = tmp_path / "run_stats.csv"
        stats_csv.write_text(_csv(_row("a", p95=100)))
        baseline = tmp_path / "baseline.json"
        rc = bl.run(["--stats", str(stats_csv), "--baseline", str(baseline), "--update-baseline"])
        assert rc == 0
        assert baseline.exists()

    def test_first_run_records_baseline(self, tmp_path):
        stats_csv = tmp_path / "run_stats.csv"
        stats_csv.write_text(_csv(_row("a", p95=100)))
        baseline = tmp_path / "baseline.json"
        rc = bl.run(["--stats", str(stats_csv), "--baseline", str(baseline)])
        assert rc == 0
        assert baseline.exists()

    def test_compare_detects_regression_exit_1(self, tmp_path):
        baseline = tmp_path / "baseline.json"
        bl.save_baseline(baseline, bl.parse_locust_stats(_csv(_row("a", p95=100))))
        stats_csv = tmp_path / "run_stats.csv"
        stats_csv.write_text(_csv(_row("a", p95=400)))
        rc = bl.run(["--stats", str(stats_csv), "--baseline", str(baseline)])
        assert rc == 1

    def test_compare_passes_exit_0(self, tmp_path):
        baseline = tmp_path / "baseline.json"
        bl.save_baseline(baseline, bl.parse_locust_stats(_csv(_row("a", p95=100))))
        stats_csv = tmp_path / "run_stats.csv"
        stats_csv.write_text(_csv(_row("a", p95=120)))
        rc = bl.run(["--stats", str(stats_csv), "--baseline", str(baseline)])
        assert rc == 0

    def test_first_run_with_errors_still_fails(self, tmp_path):
        # A broken PR must not quietly record a bad baseline and pass.
        stats_csv = tmp_path / "run_stats.csv"
        stats_csv.write_text(_csv(_row("a", count=100, failures=50, p95=100)))  # 50% errors
        baseline = tmp_path / "baseline.json"
        rc = bl.run(["--stats", str(stats_csv), "--baseline", str(baseline)])
        assert rc == 1
        assert baseline.exists()  # baseline is still recorded for next time

    def test_empty_stats_exits_1(self, tmp_path):
        stats_csv = tmp_path / "empty.csv"
        stats_csv.write_text(_HEADER + "\n")
        rc = bl.run(["--stats", str(stats_csv), "--baseline", str(tmp_path / "b.json")])
        assert rc == 1
