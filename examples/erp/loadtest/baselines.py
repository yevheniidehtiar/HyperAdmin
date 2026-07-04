"""Record and compare Locust load-test baselines for regression detection.

Parses Locust's ``*_stats.csv`` into a structured per-endpoint baseline (p50/p95/p99,
throughput, error rate), stores it as JSON, and on later runs compares against it. A run is a
**regression** if, for any endpoint, the p95 exceeds ``--p95-factor`` times the baseline p95, or
the error rate exceeds ``--max-error-rate``. Pure stdlib — no ``locust`` import — so it runs in
CI without the load-test extra.

CLI::

    python -m examples.erp.loadtest.baselines --stats run_stats.csv             # compare
    python -m examples.erp.loadtest.baselines --stats run_stats.csv --update-baseline
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_BASELINE = Path(__file__).parent / "baselines" / "baseline.json"
DEFAULT_P95_FACTOR = 2.0
DEFAULT_MAX_ERROR_RATE = 0.01


@dataclass(frozen=True)
class EndpointStats:
    name: str
    count: int
    error_rate: float
    p50: float
    p95: float
    p99: float
    throughput: float


def parse_locust_stats(csv_text: str) -> dict[str, EndpointStats]:
    """Parse a Locust ``*_stats.csv`` into ``{endpoint_name: EndpointStats}``."""
    reader = csv.DictReader(io.StringIO(csv_text))
    stats: dict[str, EndpointStats] = {}
    for row in reader:
        name = (row.get("Name") or "").strip()
        if not name:
            continue
        count = int(float(row.get("Request Count", 0) or 0))
        failures = int(float(row.get("Failure Count", 0) or 0))
        error_rate = failures / count if count else 0.0
        stats[name] = EndpointStats(
            name=name,
            count=count,
            error_rate=error_rate,
            p50=_num(row.get("50%")),
            p95=_num(row.get("95%")),
            p99=_num(row.get("99%")),
            throughput=_num(row.get("Requests/s")),
        )
    return stats


def _num(value: str | None) -> float:
    try:
        return float(value) if value not in (None, "", "N/A") else 0.0
    except (TypeError, ValueError):
        return 0.0


def save_baseline(path: Path, stats: dict[str, EndpointStats]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {name: asdict(s) for name, s in stats.items()}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def load_baseline(path: Path) -> dict[str, EndpointStats]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {name: EndpointStats(**fields) for name, fields in data.items()}


@dataclass(frozen=True)
class Regression:
    name: str
    kind: str  # "p95" or "error_rate"
    baseline: float
    current: float
    threshold: float


def compare(
    baseline: dict[str, EndpointStats],
    current: dict[str, EndpointStats],
    *,
    p95_factor: float = DEFAULT_P95_FACTOR,
    max_error_rate: float = DEFAULT_MAX_ERROR_RATE,
) -> list[Regression]:
    """Return the list of regressions; empty means the run passed."""
    regressions: list[Regression] = []
    for name, cur in current.items():
        if cur.error_rate > max_error_rate:
            regressions.append(Regression(name, "error_rate", 0.0, cur.error_rate, max_error_rate))
        base = baseline.get(name)
        if base and base.p95 > 0:
            limit = base.p95 * p95_factor
            if cur.p95 > limit:
                regressions.append(Regression(name, "p95", base.p95, cur.p95, limit))
    return regressions


def render_table(
    baseline: dict[str, EndpointStats],
    current: dict[str, EndpointStats],
    regressions: list[Regression],
) -> str:
    """Render a plain-text comparison table (no external deps)."""
    flagged = {(r.name, r.kind) for r in regressions}
    header = f"{'Endpoint':<48} {'base p95':>9} {'cur p95':>9} {'err%':>7}  status"
    lines = [header, "-" * len(header)]
    for name in sorted(current):
        cur = current[name]
        base = baseline.get(name)
        base_p95 = f"{base.p95:.0f}" if base else "—"
        status = "OK"
        if (name, "p95") in flagged:
            status = "REGRESSED p95"
        elif (name, "error_rate") in flagged:
            status = "REGRESSED errors"
        elif base is None:
            status = "NEW"
        lines.append(
            f"{name[:48]:<48} {base_p95:>9} {cur.p95:>9.0f} {cur.error_rate * 100:>6.2f}%  {status}"
        )
    return "\n".join(lines)


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare a Locust run against a baseline.")
    parser.add_argument("--stats", required=True, type=Path, help="Locust *_stats.csv path")
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--update-baseline", action="store_true", help="overwrite the baseline")
    parser.add_argument("--p95-factor", type=float, default=DEFAULT_P95_FACTOR)
    parser.add_argument("--max-error-rate", type=float, default=DEFAULT_MAX_ERROR_RATE)
    args = parser.parse_args(argv)

    current = parse_locust_stats(args.stats.read_text(encoding="utf-8"))
    if not current:
        print(f"error: no endpoint rows parsed from {args.stats}", file=sys.stderr)
        return 1

    if args.update_baseline:
        save_baseline(args.baseline, current)
        print(f"baseline updated: {args.baseline} ({len(current)} endpoints)")
        return 0

    if not args.baseline.exists():
        # First run establishes the baseline, but the error-rate gate still applies so a
        # broken PR (all 5xx) cannot quietly record a bad baseline and pass.
        save_baseline(args.baseline, current)
        regressions = compare({}, current, max_error_rate=args.max_error_rate)
        print(render_table({}, current, regressions))
        if regressions:
            print(f"\nFAILED: {len(regressions)} regression(s) despite no prior baseline:")
            for r in regressions:
                print(f"  - {r.name}: {r.kind} {r.current:.3f} > threshold {r.threshold:.3f}")
            return 1
        print(f"\nno baseline found — recorded current run as baseline: {args.baseline}")
        return 0

    baseline = load_baseline(args.baseline)
    regressions = compare(
        baseline, current, p95_factor=args.p95_factor, max_error_rate=args.max_error_rate
    )
    print(render_table(baseline, current, regressions))
    if regressions:
        print(f"\nFAILED: {len(regressions)} regression(s) detected:")
        for r in regressions:
            print(f"  - {r.name}: {r.kind} {r.current:.3f} > threshold {r.threshold:.3f}")
        return 1
    print("\nPASSED: no regressions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
