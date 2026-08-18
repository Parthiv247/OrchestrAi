#!/usr/bin/env python3
"""
OrchestrAI — Master Benchmark Runner
=====================================
Runs all 3 pre-registered experiments and produces a consolidated summary.

Usage:
  python scripts/run_all_experiments.py           # simulation mode
  python scripts/run_all_experiments.py --live    # live mode

Author: Parthiv Patel | 2024AA05129 | OrchestrAI MTech Dissertation
"""
import json
import sys
import argparse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from experiment1_mttr  import run_experiment as run_exp1, print_results as pr1, save_results as sr1
from experiment2_nlsql import run_experiment as run_exp2, print_results as pr2, save_results as sr2
from experiment3_cost  import run_experiment as run_exp3, print_results as pr3, save_results as sr3

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--out", default="scripts/results")
    args = parser.parse_args()

    out_dir = Path(args.out)
    sim = not args.live

    print("\n" + "█" * 70)
    print("  OrchestrAI — Pre-Registered Experiment Suite")
    print("  MTech AI & ML Dissertation | BITS ZG628T | June 2026")
    print("█" * 70)

    # ── Experiment 1 ──────────────────────────────────────────────────────────
    print("\n\n▶ RUNNING EXPERIMENT 1: Self-Healing MTTR Reduction...")
    r1, records1 = run_exp1(simulation=sim)
    pr1(r1)
    sr1(r1, out_dir)

    # ── Experiment 2 ──────────────────────────────────────────────────────────
    print("\n\n▶ RUNNING EXPERIMENT 2: NL-to-SQL Accuracy...")
    r2 = run_exp2(simulation=sim)
    pr2(r2)
    sr2(r2, out_dir)

    # ── Experiment 3 ──────────────────────────────────────────────────────────
    print("\n\n▶ RUNNING EXPERIMENT 3: Query Cost Reduction...")
    r3 = run_exp3(simulation=sim)
    pr3(r3)
    sr3(r3, out_dir)

    # ── Consolidated Summary ──────────────────────────────────────────────────
    summary = {
        "project": "OrchestrAI — Autonomous Multi-Agent AI Platform for Self-Healing Data Pipelines",
        "student": "Parthiv Patel | 2024AA05129 | M.Tech AI & ML | BITS ZG628T",
        "date": datetime.utcnow().isoformat(),
        "mode": "simulation" if sim else "live",
        "experiments": {
            "E1_self_healing_mttr": {
                "description": "MTTR reduction vs rule-based baseline (paired t-test)",
                "result": f"{r1['primary_comparison']['orchestrai_vs_rule_based']['reduction_pct']}% MTTR reduction",
                "target": ">= 50%",
                "met": r1["target"]["met"],
                "p_value": r1["primary_comparison"]["orchestrai_vs_rule_based"]["p_value"],
                "cohen_d": r1["primary_comparison"]["orchestrai_vs_rule_based"]["cohen_d"],
                "orchestrai_mttr_min": r1["conditions"]["orchestrai"]["mean"],
                "rule_based_mttr_min": r1["conditions"]["rule_based"]["mean"],
                "detection_rate_pct": r1["detection_rate_pct"],
            },
            "E2_nl_to_sql_accuracy": {
                "description": "Component match accuracy on 100 Spider-representative questions",
                "result": f"{r2['overall_component_match_pct']}% component match",
                "target": ">= 65%",
                "met": r2["target"]["met"],
                "exact_match_pct": r2["exact_match_pct"],
                "weakest_clause": min(r2["clause_accuracy"].items(), key=lambda x: x[1]),
            },
            "E3_cost_reduction": {
                "description": "Avg cost reduction on 30 anti-pattern SQL queries",
                "result": f"{r3['avg_savings_pct']}% avg cost reduction",
                "target": ">= 30%",
                "met": r3["target"]["met"],
                "dollar_savings": r3["cost_summary"]["total_dollar_savings"],
                "detection_accuracy_pct": r3["anti_pattern_detection_accuracy_pct"],
            },
        },
        "all_targets_met": r1["target"]["met"] and r2["target"]["met"] and r3["target"]["met"],
    }

    out_path = out_dir / "benchmark_summary.json"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)

    print("\n\n" + "█" * 70)
    print("  CONSOLIDATED BENCHMARK RESULTS")
    print("█" * 70)
    print(f"\n  {'Experiment':<35} {'Result':<25} {'Target':<12} {'Status'}")
    print(f"  {'-'*80}")
    for eid, exp in summary["experiments"].items():
        status = "✅ MET" if exp["met"] else "❌ NOT MET"
        print(f"  {exp['description'][:34]:<35} {exp['result']:<25} {exp['target']:<12} {status}")

    overall = "✅ ALL TARGETS MET" if summary["all_targets_met"] else "⚠️  SOME TARGETS MISSED"
    print(f"\n  OVERALL: {overall}")
    print(f"\n  Summary → {out_path}")
    print("█" * 70)

    return 0 if summary["all_targets_met"] else 1


if __name__ == "__main__":
    sys.exit(main())
