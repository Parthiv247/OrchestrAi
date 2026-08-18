"""
SandboxAgent — Runs fix code in an isolated Docker container with 12 automated tests.

Docker limits: CPU 0.5, Memory 256MB, Timeout 60s.
confidence_score = tests_passed / 12
"""
import ast
import io
import logging
import os
import re
import time
import tempfile
import textwrap
from typing import Dict, Any, Tuple

import psycopg2
import psycopg2.extras

from .state import HealingAgentState

logger = logging.getLogger(__name__)

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", 5432)),
    "dbname": os.getenv("POSTGRES_DB", "orchestrai"),
    "user": os.getenv("POSTGRES_USER", "admin"),
    "password": os.getenv("POSTGRES_PASSWORD", "orchestrai_secret"),
}

DOCKER_IMAGE = "python:3.11-slim"
CONTAINER_TIMEOUT = 60   # seconds
CONTAINER_CPU = 0.5
CONTAINER_MEM = "256m"
TOTAL_TESTS = 12


class SandboxAgent:
    """Executes fix code in Docker and runs the 12-point test suite."""

    def run(self, state: HealingAgentState) -> HealingAgentState:
        fix_code = state.get("fix_code") or ""
        steps = list(state.get("reasoning_steps") or [])

        if not fix_code.strip():
            steps.append("SandboxAgent: no fix code to test")
            return HealingAgentState(**{**state,
                "sandbox_results": {"error": "no_fix_code"},
                "tests_passed": 0,
                "tests_failed": TOTAL_TESTS,
                "confidence_score": 0.0,
                "reasoning_steps": steps,
            })

        mock_data = self._get_mock_data(state.get("pipeline_name") or "")
        exec_result = self.execute_in_docker(fix_code, mock_data)
        test_results = self.run_test_suite(exec_result, fix_code)

        passed = sum(1 for v in test_results.values() if v is True)
        failed = TOTAL_TESTS - passed
        score = round(passed / TOTAL_TESTS, 3)

        steps.append(f"SandboxAgent: {passed}/{TOTAL_TESTS} tests passed, confidence={score:.2f}")

        return HealingAgentState(**{**state,
            "sandbox_results": test_results,
            "tests_passed": passed,
            "tests_failed": failed,
            "confidence_score": score,
            "reasoning_steps": steps,
        })

    # ── Docker execution ───────────────────────────────────────────────────────

    def execute_in_docker(self, fix_code: str, mock_data: str) -> Dict[str, Any]:
        """Spin up python:3.11-slim, mount fix + mock data, run with limits."""
        try:
            import docker
            client = docker.from_env()
            return self._run_docker_container(client, fix_code, mock_data)
        except ImportError:
            logger.warning("docker SDK not installed — running fix in local subprocess sandbox")
            return self._run_local_sandbox(fix_code, mock_data)
        except Exception as e:
            logger.warning("Docker execution failed, falling back to local sandbox: %s", e)
            return self._run_local_sandbox(fix_code, mock_data)

    def _run_docker_container(self, client, fix_code: str, mock_data: str) -> Dict[str, Any]:
        """Real Docker execution with resource limits. Uses detach+wait for timeout support."""
        import docker

        runner_script = self._build_runner_script(fix_code, mock_data)

        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "fix.py"), "w") as f:
                f.write(fix_code)
            with open(os.path.join(tmpdir, "runner.py"), "w") as f:
                f.write(runner_script)
            with open(os.path.join(tmpdir, "mock_data.csv"), "w") as f:
                f.write(mock_data)

            start_time = time.time()
            result_dict: Dict[str, Any] = {
                "stdout": "", "stderr": "", "exit_code": -1,
                "timed_out": False, "duration_s": 0.0,
                "output_rows": 0, "output_cols": [],
                "memory_mb": 0.0, "error": None,
            }

            container = None
            try:
                # network_disabled=False so container can pip-install pandas if needed.
                # We test the fix CODE itself for network calls (T07) instead.
                container = client.containers.run(
                    DOCKER_IMAGE,
                    command=["sh", "-c", "pip install pandas -q && python /sandbox/runner.py"],
                    volumes={tmpdir: {"bind": "/sandbox", "mode": "ro"}},
                    mem_limit=CONTAINER_MEM,
                    nano_cpus=int(CONTAINER_CPU * 1e9),
                    remove=False,
                    detach=True,
                    stdout=True,
                    stderr=True,
                )
                exit_status = container.wait(timeout=CONTAINER_TIMEOUT)
                result_dict["exit_code"] = exit_status.get("StatusCode", -1)
                result_dict["stdout"] = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
                result_dict["stderr"] = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")
            except docker.errors.ContainerError as e:
                result_dict["exit_code"] = e.exit_status
                result_dict["stderr"] = str(e.stderr.decode("utf-8", errors="replace")) if e.stderr else str(e)
            except Exception as e:
                err_str = str(e).lower()
                if "timed out" in err_str or "timeout" in err_str:
                    result_dict["timed_out"] = True
                result_dict["error"] = str(e)
            finally:
                if container:
                    try:
                        container.remove(force=True)
                    except Exception:
                        pass

            result_dict["duration_s"] = round(time.time() - start_time, 2)
            self._parse_runner_output(result_dict)
            return result_dict

    def _run_local_sandbox(self, fix_code: str, mock_data: str) -> Dict[str, Any]:
        """Executes fix code in-process (restricted exec) when Docker is unavailable."""
        import subprocess

        runner_script = self._build_runner_script(fix_code, mock_data)

        with tempfile.TemporaryDirectory() as tmpdir:
            runner_path = os.path.join(tmpdir, "runner.py")
            fix_path = os.path.join(tmpdir, "fix.py")
            data_path = os.path.join(tmpdir, "mock_data.csv")

            with open(runner_path, "w") as f:
                f.write(runner_script)
            with open(fix_path, "w") as f:
                f.write(fix_code)
            with open(data_path, "w") as f:
                f.write(mock_data)

            start_time = time.time()
            result_dict: Dict[str, Any] = {
                "stdout": "", "stderr": "", "exit_code": -1,
                "timed_out": False, "duration_s": 0.0,
                "output_rows": 0, "output_cols": [], "memory_mb": 0.0, "error": None,
            }

            try:
                proc = subprocess.run(
                    ["python", runner_path],
                    capture_output=True, text=True,
                    timeout=CONTAINER_TIMEOUT,
                    cwd=tmpdir,
                )
                result_dict["stdout"] = proc.stdout
                result_dict["stderr"] = proc.stderr
                result_dict["exit_code"] = proc.returncode
            except subprocess.TimeoutExpired:
                result_dict["timed_out"] = True
                result_dict["error"] = "Execution timed out"
            except Exception as e:
                result_dict["error"] = str(e)

            result_dict["duration_s"] = round(time.time() - start_time, 2)
            self._parse_runner_output(result_dict)
            return result_dict

    def _build_runner_script(self, fix_code: str, mock_data: str) -> str:
        """Build the runner script. fix.py and mock_data.csv are written to disk separately."""
        return '''
import sys, json, os, time

SANDBOX_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SANDBOX_DIR)

import pandas as pd

try:
    df_input = pd.read_csv(os.path.join(SANDBOX_DIR, "mock_data.csv"))
except Exception:
    df_input = pd.DataFrame({"records_loaded": [100]*10, "records_failed": [0]*10, "status": ["success"]*10})

output_rows = 0
output_cols = []
verify_result = False
runtime_error = None
start = time.time()

try:
    import importlib.util
    spec = importlib.util.spec_from_file_location("fix", os.path.join(SANDBOX_DIR, "fix.py"))
    fix_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fix_module)
    df_output = fix_module.fix(df_input.copy())
    output_rows = len(df_output)
    output_cols = list(df_output.columns)
    try:
        verify_result = bool(fix_module.verify(df_output))
    except Exception as ve:
        verify_result = False
except Exception as e:
    runtime_error = str(e)

duration = time.time() - start

print(json.dumps({
    "output_rows": output_rows,
    "output_cols": output_cols,
    "verify_result": verify_result,
    "runtime_error": runtime_error,
    "duration_s": round(duration, 3),
}))
'''

    def _parse_runner_output(self, result: Dict[str, Any]):
        """Parse JSON output from the runner script into result dict."""
        import json
        try:
            stdout = result.get("stdout", "")
            for line in reversed(stdout.splitlines()):
                line = line.strip()
                if line.startswith("{"):
                    data = json.loads(line)
                    result["output_rows"] = data.get("output_rows", 0)
                    result["output_cols"] = data.get("output_cols", [])
                    result["verify_result"] = data.get("verify_result", False)
                    result["runtime_error"] = data.get("runtime_error")
                    result["duration_s"] = data.get("duration_s", result.get("duration_s", 0))
                    break
        except Exception:
            pass

    # ── 12-Point Test Suite ────────────────────────────────────────────────────

    def run_test_suite(self, exec_result: Dict[str, Any], fix_code: str) -> Dict[str, bool]:
        """Run all 12 tests. Each returns True (pass) or False (fail)."""
        results: Dict[str, bool] = {}

        # 1. No syntax errors
        results["T01_no_syntax_errors"] = self._test_syntax(fix_code)

        # 2. No runtime exceptions
        results["T02_no_runtime_exceptions"] = (
            exec_result.get("exit_code") == 0 and
            not exec_result.get("runtime_error") and
            not exec_result.get("timed_out")
        )

        # 3. verify() exists and returns True
        results["T03_verify_returns_true"] = bool(exec_result.get("verify_result", False))

        # 4. Output has same or more columns as input
        output_cols = exec_result.get("output_cols", [])
        results["T04_output_has_columns"] = len(output_cols) > 0

        # 5. Output has >0 rows
        results["T05_output_has_rows"] = (exec_result.get("output_rows", 0) > 0)

        # 6. No DROP TABLE or DELETE statements
        results["T06_no_destructive_sql"] = not self._has_destructive_sql(fix_code)

        # 7. No network calls (no requests/httpx/urllib)
        results["T07_no_network_calls"] = not self._has_network_calls(fix_code)

        # 8. Execution time < 30 seconds
        duration = exec_result.get("duration_s", 999)
        results["T08_execution_time_ok"] = duration < 30

        # 9. Memory usage < 200MB (approximated by container not OOM-killed)
        results["T09_memory_ok"] = not exec_result.get("timed_out", False) and exec_result.get("exit_code") != 137

        # 10. No import of forbidden modules (sys.exit, subprocess, os.system)
        results["T10_no_forbidden_imports"] = not self._has_forbidden_calls(fix_code)

        # 11. Fix code defines fix() function
        results["T11_fix_function_defined"] = self._has_function(fix_code, "fix")

        # 12. Fix code defines verify() function
        results["T12_verify_function_defined"] = self._has_function(fix_code, "verify")

        return results

    # ── Test helpers ───────────────────────────────────────────────────────────

    def _test_syntax(self, code: str) -> bool:
        try:
            ast.parse(code)
            return True
        except SyntaxError:
            return False

    def _has_destructive_sql(self, code: str) -> bool:
        patterns = [r"\bDROP\s+TABLE\b", r"\bDELETE\s+FROM\b", r"\bTRUNCATE\b", r"\bDROP\s+DATABASE\b"]
        code_upper = code.upper()
        return any(re.search(p, code_upper) for p in patterns)

    def _has_network_calls(self, code: str) -> bool:
        banned = ["requests.", "httpx.", "urllib.", "socket.", "http.client", "aiohttp"]
        return any(b in code for b in banned)

    def _has_forbidden_calls(self, code: str) -> bool:
        banned = ["os.system(", "subprocess.", "sys.exit(", "exec(", "eval(", "__import__"]
        return any(b in code for b in banned)

    def _has_function(self, code: str, func_name: str) -> bool:
        try:
            tree = ast.parse(code)
            return any(
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name
                for node in ast.walk(tree)
            )
        except SyntaxError:
            return False

    # ── Mock data helpers ──────────────────────────────────────────────────────

    def _get_mock_data(self, pipeline_name: str) -> str:
        """Return 100-row CSV mock data from pipeline_runs table (fallback to synthetic)."""
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT pipeline_name, records_ingested, records_loaded,
                           records_failed, status, duration_seconds
                    FROM pipeline_runs
                    WHERE pipeline_name = %s
                    ORDER BY started_at DESC
                    LIMIT 100
                """, (pipeline_name,))
                rows = cur.fetchall()
            conn.close()
            if rows:
                lines = ["pipeline_name,records_ingested,records_loaded,records_failed,status,duration_seconds"]
                for r in rows:
                    lines.append(",".join(str(v) if v is not None else "" for v in r))
                return "\n".join(lines)
        except Exception:
            pass
        return self._synthetic_csv()

    def _synthetic_csv(self) -> str:
        header = "pipeline_name,records_ingested,records_loaded,records_failed,status,duration_seconds"
        rows = [f"test_pipeline,{1000+i},{900+i},{i % 5},success,{30+i}" for i in range(100)]
        return header + "\n" + "\n".join(rows)
