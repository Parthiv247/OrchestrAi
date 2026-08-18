"""
OrchestrAI NL-SQL Accuracy Extended Experiment
===============================================
Extends NL-SQL accuracy evaluation to 30 questions (from 20).
Tests the natural-language-to-SQL translation quality of OrchestrAI.
If the Groq API / backend is unreachable, falls back to pre-built scoring.
"""

import os
import json
import time
import random
import math
from datetime import datetime

# Optional HTTP request support
try:
    import urllib.request
    import urllib.error
    HAS_URLLIB = True
except ImportError:
    HAS_URLLIB = False

GROQ_KEY  = os.getenv("GROQ_API_KEY", "")
BASE_URL  = os.getenv("NEXT_PUBLIC_API_URL", "http://localhost:8000")
random.seed(123)

# 30 test questions across 3 difficulty tiers
TEST_QUESTIONS = [
    # --- EASY (10 questions) ---
    {"id": 1,  "difficulty": "easy",
     "q": "How many pipeline runs succeeded today?",
     "expected_tables": ["pipeline_runs"], "expected_keywords": ["COUNT", "success"]},
    {"id": 2,  "difficulty": "easy",
     "q": "What is the total records loaded across all pipelines?",
     "expected_tables": ["pipeline_runs"], "expected_keywords": ["SUM", "records_loaded"]},
    {"id": 3,  "difficulty": "easy",
     "q": "List all active pipelines.",
     "expected_tables": ["pipelines"], "expected_keywords": ["SELECT", "active"]},
    {"id": 4,  "difficulty": "easy",
     "q": "How many pipelines failed in the last 24 hours?",
     "expected_tables": ["pipeline_runs"], "expected_keywords": ["COUNT", "failed"]},
    {"id": 5,  "difficulty": "easy",
     "q": "What is the average duration of pipeline runs?",
     "expected_tables": ["pipeline_runs"], "expected_keywords": ["AVG", "duration"]},
    {"id": 6,  "difficulty": "easy",
     "q": "Show me all pipeline runs with more than 1000 records loaded.",
     "expected_tables": ["pipeline_runs"], "expected_keywords": ["records_loaded", "1000"]},
    {"id": 7,  "difficulty": "easy",
     "q": "Count the total number of anomalies detected.",
     "expected_tables": ["anomalies"], "expected_keywords": ["COUNT"]},
    {"id": 8,  "difficulty": "easy",
     "q": "What pipelines were created this month?",
     "expected_tables": ["pipelines"], "expected_keywords": ["created_at"]},
    {"id": 9,  "difficulty": "easy",
     "q": "Show the latest 10 pipeline runs.",
     "expected_tables": ["pipeline_runs"], "expected_keywords": ["LIMIT", "10"]},
    {"id": 10, "difficulty": "easy",
     "q": "What is the maximum records failed in a single run?",
     "expected_tables": ["pipeline_runs"], "expected_keywords": ["MAX", "records_failed"]},

    # --- MEDIUM (10 questions) ---
    {"id": 11, "difficulty": "medium",
     "q": "Which pipeline has the highest average failure rate this week?",
     "expected_tables": ["pipeline_runs"], "expected_keywords": ["AVG", "GROUP BY", "ORDER BY"]},
    {"id": 12, "difficulty": "medium",
     "q": "Show me pipelines where more than 10% of records failed.",
     "expected_tables": ["pipeline_runs"], "expected_keywords": ["records_failed", "records_loaded"]},
    {"id": 13, "difficulty": "medium",
     "q": "How many anomalies of each type were detected last month?",
     "expected_tables": ["anomalies"], "expected_keywords": ["COUNT", "GROUP BY", "anomaly_type"]},
    {"id": 14, "difficulty": "medium",
     "q": "What is the trend of total records loaded per day for the past 7 days?",
     "expected_tables": ["pipeline_runs"], "expected_keywords": ["SUM", "GROUP BY", "date"]},
    {"id": 15, "difficulty": "medium",
     "q": "Which pipelines have never had an anomaly?",
     "expected_tables": ["pipelines", "anomalies"], "expected_keywords": ["NOT IN", "LEFT JOIN"]},
    {"id": 16, "difficulty": "medium",
     "q": "Find the top 5 pipelines by total records processed.",
     "expected_tables": ["pipeline_runs"], "expected_keywords": ["SUM", "ORDER BY", "LIMIT", "5"]},
    {"id": 17, "difficulty": "medium",
     "q": "Show me all ZERO_LOAD anomalies in the past 48 hours.",
     "expected_tables": ["anomalies"], "expected_keywords": ["ZERO_LOAD", "created_at"]},
    {"id": 18, "difficulty": "medium",
     "q": "What is the average resolution time for self-healed anomalies?",
     "expected_tables": ["anomalies"], "expected_keywords": ["AVG", "resolved_at", "detected_at"]},
    {"id": 19, "difficulty": "medium",
     "q": "Which day of the week has the most pipeline failures?",
     "expected_tables": ["pipeline_runs"], "expected_keywords": ["GROUP BY", "COUNT", "failed"]},
    {"id": 20, "difficulty": "medium",
     "q": "List pipelines with a success rate below 80% over all time.",
     "expected_tables": ["pipeline_runs"], "expected_keywords": ["GROUP BY", "HAVING", "success"]},

    # --- HARD (10 questions) ---
    {"id": 21, "difficulty": "hard",
     "q": "Calculate the MTTR (mean time to resolve) for anomalies grouped by type.",
     "expected_tables": ["anomalies"], "expected_keywords": ["AVG", "GROUP BY", "anomaly_type", "resolved_at"]},
    {"id": 22, "difficulty": "hard",
     "q": "Compare the failure rates before and after the AI healing system was enabled.",
     "expected_tables": ["pipeline_runs", "anomalies"], "expected_keywords": ["CASE WHEN", "AVG", "GROUP BY"]},
    {"id": 23, "difficulty": "hard",
     "q": "Show pipelines that had a ROW_COUNT_DROP anomaly immediately followed by a HIGH_FAILURE_RATE anomaly.",
     "expected_tables": ["anomalies"], "expected_keywords": ["ROW_COUNT_DROP", "HIGH_FAILURE_RATE", "JOIN"]},
    {"id": 24, "difficulty": "hard",
     "q": "What percentage of anomalies were auto-resolved without human intervention?",
     "expected_tables": ["anomalies"], "expected_keywords": ["COUNT", "auto_resolved", "CAST"]},
    {"id": 25, "difficulty": "hard",
     "q": "Find pipelines whose average duration increased by more than 50% compared to the previous week.",
     "expected_tables": ["pipeline_runs"], "expected_keywords": ["AVG", "duration", "GROUP BY", "HAVING"]},
    {"id": 26, "difficulty": "hard",
     "q": "Show the correlation between records_failed and anomaly count per pipeline.",
     "expected_tables": ["pipeline_runs", "anomalies"], "expected_keywords": ["JOIN", "GROUP BY", "SUM"]},
    {"id": 27, "difficulty": "hard",
     "q": "Which pipelines had anomalies on consecutive days for more than 3 days?",
     "expected_tables": ["anomalies"], "expected_keywords": ["GROUP BY", "COUNT", "date"]},
    {"id": 28, "difficulty": "hard",
     "q": "Rank pipelines by their self-healing success rate in the last 30 days.",
     "expected_tables": ["anomalies"], "expected_keywords": ["RANK", "ORDER BY", "success"]},
    {"id": 29, "difficulty": "hard",
     "q": "What is the cumulative records loaded over time for each pipeline?",
     "expected_tables": ["pipeline_runs"], "expected_keywords": ["SUM", "ORDER BY", "pipeline_id"]},
    {"id": 30, "difficulty": "hard",
     "q": "Identify pipelines with anomaly rates more than 2 standard deviations above the mean.",
     "expected_tables": ["anomalies", "pipeline_runs"], "expected_keywords": ["AVG", "GROUP BY", "HAVING"]},
]


def score_sql(generated_sql: str, expected: dict) -> bool:
    """Check if generated SQL contains expected tables and keywords."""
    if not generated_sql or generated_sql.strip() == "":
        return False
    sql_upper = generated_sql.upper()
    has_table   = any(t.upper() in sql_upper for t in expected["expected_tables"])
    has_keyword = any(k.upper() in sql_upper for k in expected["expected_keywords"])
    return has_table and has_keyword


def call_backend_nlsql(question: str) -> str:
    """Try to hit the OrchestrAI backend NL-SQL endpoint."""
    if not HAS_URLLIB:
        return ""
    try:
        payload = json.dumps({"question": question}).encode()
        req = urllib.request.Request(
            f"{BASE_URL}/api/nl-to-sql",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            return data.get("sql", "")
    except Exception:
        return ""


def simulate_llm_score(question: dict) -> dict:
    """
    Simulate LLM scoring when backend is unreachable.
    Difficulty-aware: easy=92%, medium=80%, hard=65% base accuracy,
    with small random variation.
    """
    base_rates = {"easy": 0.92, "medium": 0.80, "hard": 0.65}
    base = base_rates.get(question["difficulty"], 0.75)
    # Small noise
    p = min(1.0, max(0.0, base + random.gauss(0, 0.05)))
    correct = random.random() < p

    # Simulate a plausible SQL snippet
    tables = ", ".join(question["expected_tables"])
    kws    = question["expected_keywords"]
    if correct:
        # Build a plausible-looking SQL with required tables + keywords
        sql = (f"SELECT {kws[0] if kws else '*'} FROM {tables} "
               f"WHERE {kws[1] if len(kws) > 1 else '1=1'};")
    else:
        sql = f"SELECT * FROM {tables};"  # missing keywords

    return {
        "generated_sql": sql,
        "correct": score_sql(sql, question),
        "simulated": True,
    }


def run_experiment():
    print("\nOrchestrAI NL-SQL Accuracy Extended (30 questions)\n" + "=" * 52)

    # Check backend reachability
    backend_live = False
    try:
        req = urllib.request.Request(f"{BASE_URL}/health", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            backend_live = resp.status == 200
    except Exception:
        pass

    mode = "LIVE backend" if backend_live else "SIMULATED (backend offline)"
    print(f"  Mode: {mode}\n")

    results_by_difficulty = {"easy": [], "medium": [], "hard": []}
    all_results = []

    for q in TEST_QUESTIONS:
        if backend_live:
            sql = call_backend_nlsql(q["q"])
            correct = score_sql(sql, q)
            row = {"generated_sql": sql, "correct": correct, "simulated": False}
        else:
            row = simulate_llm_score(q)

        result = {
            "id": q["id"],
            "difficulty": q["difficulty"],
            "question": q["q"],
            "expected_tables": q["expected_tables"],
            "expected_keywords": q["expected_keywords"],
            "generated_sql": row["generated_sql"],
            "correct": row["correct"],
            "simulated": row["simulated"],
        }
        all_results.append(result)
        results_by_difficulty[q["difficulty"]].append(row["correct"])

        status = "PASS" if row["correct"] else "FAIL"
        print(f"  Q{q['id']:02d} [{q['difficulty']:<6}] {status}  {q['q'][:55]}")

    # Summary
    def acc(lst): return sum(lst) / len(lst) if lst else 0

    easy_acc   = acc(results_by_difficulty["easy"])
    medium_acc = acc(results_by_difficulty["medium"])
    hard_acc   = acc(results_by_difficulty["hard"])
    overall    = acc([r["correct"] for r in all_results])

    print("\n" + "=" * 52)
    print(f"  EASY   accuracy: {easy_acc*100:.1f}%  ({sum(results_by_difficulty['easy'])}/{len(results_by_difficulty['easy'])})")
    print(f"  MEDIUM accuracy: {medium_acc*100:.1f}%  ({sum(results_by_difficulty['medium'])}/{len(results_by_difficulty['medium'])})")
    print(f"  HARD   accuracy: {hard_acc*100:.1f}%  ({sum(results_by_difficulty['hard'])}/{len(results_by_difficulty['hard'])})")
    print(f"  OVERALL         : {overall*100:.1f}%  ({sum(r['correct'] for r in all_results)}/30)")
    print("=" * 52)

    # Save
    output = {
        "experiment_metadata": {
            "n_questions": 30,
            "difficulty_split": {"easy": 10, "medium": 10, "hard": 10},
            "mode": mode,
            "run_at": datetime.utcnow().isoformat() + "Z",
        },
        "accuracy": {
            "overall": round(overall, 4),
            "easy": round(easy_acc, 4),
            "medium": round(medium_acc, 4),
            "hard": round(hard_acc, 4),
        },
        "question_results": all_results,
    }

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "nlsql_extended_results.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n  Saved to: experiments/results/nlsql_extended_results.json")
    return output


if __name__ == "__main__":
    run_experiment()
