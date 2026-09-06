"""Offline regression: the ground-truth answer key can never reach AGENT input.

Closes the leak audited in docs/eval-ground-truth-leak-audit-2026-09-05.md
and fixed in docs/eval-ground-truth-leak-fix-2026-09-05.md (P0-A):

  Fix A — evals.run_evals.build_instruction must carry the customer pointer
          only; the SDK's "Original Task:" prefix forwards whatever the task
          is into every node, so the prefixed form must be clean too.
  Fix B — the four read tools must never return a '_'-prefixed (annotation)
          key, wherever the seed file happens to place one. The poisoned-seed
          test below is the real proof: today's clean returns were an accident
          of key placement, not an enforced invariant.
  Fix C — the TrajectoryEvaluator rubric must not reference data the judge
          never receives (installed compose_test_prompt embeds no metadata).

No model call, no network. evals.run_evals constructs the judge model at
import time, but the provider client is created lazily per request
(installed strands openai.py), so a dummy key makes the import safe AND a
live call impossible; a set environment variable wins over the repo .env
(agents/model.py:47-48).

The answer key itself (seed_scenario / expected_output) is NOT removed —
it stays frozen and byte-identical, pinned by the last test in this module;
only the channel that leaked it into agent input is gone.
"""

import json
import os

import pytest

# Must precede the evals.run_evals import: get_model() reads the env eagerly.
os.environ.setdefault("GROQ_API_KEY", "offline-test-never-used")

import evals.run_evals as run_evals  # noqa: E402
from evals.cases import test_cases  # noqa: E402

import tools.seed_data as seed_data  # noqa: E402
from tools.legacy_system import read_legacy_system  # noqa: E402
from tools.modern_system import read_modern_system  # noqa: E402
from tools.transactions import get_event_log, search_transactions  # noqa: E402

# All ten spellings of the five ground-truth labels, derived from the same
# source of truth the fix protects. Every assertion checks against ALL five
# cases' labels so cross-contamination (case N's instruction carrying case
# M's label) fails too, not just self-leakage.
LEAK_STRINGS = sorted(
    {case.input["seed_scenario"] for case in test_cases}
    | {case.expected_output for case in test_cases}
)

# Installed strands-agents 1.54.0, Graph._build_node_input
# (.venv/.../strands/multiagent/graph.py:1228-1244): every node with
# satisfied dependencies receives exactly these literal prefixes around the
# original task and its dependency results. The literals carry no case data,
# so the propagated form is label-free iff the task is — asserted anyway.
SDK_PROPAGATION_PREFIX = "Original Task: "

# Legitimate returned fields (values asserted by tests/test_tools.py; this
# module pins that NOTHING ELSE — in particular no '_'-prefixed annotation
# key — ever appears, at any nesting depth).
ALLOWED_FIELDS = {
    "legacy": {"CUSTOMER_ID", "BALANCE", "STATUS", "LAST_UPDATED"},
    "modern_record": {"customerId", "balance", "status", "lastUpdated"},
    "transaction_row": {"transaction_id", "type", "amount", "timestamp", "related_transaction_id"},
    "event_row": {"event_id", "event_type", "timestamp", "payload"},
}

# The frozen answer key, pinned byte-for-byte (P0-A constraint: the fix
# removes the leak CHANNEL, never the key itself — any drift here must fail
# loudly, not silently).
FROZEN_ANSWER_KEY = [
    ("reversal-not-propagated", "C-1001", "reversal_not_propagated", "REVERSAL_NOT_PROPAGATED"),
    ("duplicate-transaction", "C-1002", "duplicate_transaction", "DUPLICATE_TRANSACTION"),
    ("sync-lag-self-resolving", "C-1003", "sync_lag", "SYNC_LAG"),
    ("manual-override-not-reflected", "C-1004", "manual_override", "MANUAL_OVERRIDE"),
    ("data-entry-error", "C-1005", "data_entry_error", "DATA_ENTRY_ERROR"),
]


def _assert_no_leak(text: str, context: str) -> None:
    for leak in LEAK_STRINGS:
        assert leak not in text, f"{context}: ground-truth label {leak!r} present"


def _assert_no_annotation_keys(obj, path: str = "return") -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            assert not str(key).startswith("_"), (
                f"{path}: annotation key {key!r} reached a tool return"
            )
            _assert_no_annotation_keys(value, f"{path}.{key}")
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            _assert_no_annotation_keys(item, f"{path}[{index}]")


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    # tests/test_tools.py:23-27 convention: EVAL_MODE + tmp runtime store
    # (read_modern_system reads the overrides overlay from RUNTIME_DIR).
    monkeypatch.setenv("EVAL_MODE", "1")
    monkeypatch.setattr(seed_data, "RUNTIME_DIR", tmp_path)
    return tmp_path


# --- Fix A: the detector's user prompt (entry node gets the task verbatim) ---

@pytest.mark.parametrize("case", test_cases, ids=lambda c: c.name)
def test_instruction_carries_no_ground_truth_label(case):
    instruction = run_evals.build_instruction(case)
    # The legitimate function survives: the case is still identified.
    assert case.input["customer_id"] in instruction
    assert instruction.strip()
    # No label — this case's own or any of the other four's.
    _assert_no_leak(instruction, "detector instruction")
    assert "Seed scenario" not in instruction
    assert "seed_scenario" not in instruction


# --- Fix A: what the SDK forwards to the classifier and reporter ------------

@pytest.mark.parametrize("case", test_cases, ids=lambda c: c.name)
def test_sdk_original_task_propagation_carries_no_label(case):
    task = run_evals.build_instruction(case)
    # Exact block sequence the installed SDK assembles for any node with
    # satisfied dependencies (graph.py:1228-1244); the dependency-result
    # placeholder stands for agent-produced text, which the SDK passes
    # through without injecting case data.
    propagated = "".join([
        f"{SDK_PROPAGATION_PREFIX}{task}",
        "\nInputs from previous nodes:",
        "\nFrom detector_investigator:",
        "  - Agent: (evidence bundle produced by the run itself)\n",
    ])
    _assert_no_leak(propagated, "SDK-propagated node input")
    assert "Seed scenario" not in propagated


# --- Fix A at the run_case call site (P0-B Phase 0d direct evidence) --------


@pytest.mark.parametrize("case", test_cases, ids=lambda c: c.name)
def test_run_case_hands_the_clean_instruction_to_the_graph(case, monkeypatch):
    """The choke point every driver actually executes.

    All six eval drivers terminate at run_evals.run_case — directly, or
    via token_canary.run_one_case, which passes the case object through
    untouched (evals/token_canary.py:486). The two Fix A tests above pin
    build_instruction's OUTPUT; this one exercises run_case's BODY with
    the graph faked, capturing the exact string handed to graph(...) — so
    nothing between construction and invocation (a mutation, an append, a
    second call) can reintroduce the leak unseen.
    """
    captured: list[str] = []

    def fake_build_reconciliation_graph(trace_attributes=None):
        def fake_graph(instruction):
            captured.append(instruction)
            return "offline-fake-case-file"

        return fake_graph

    class _FakeExporter:
        def clear(self):
            pass

        def get_finished_spans(self):
            return []

    class _FakeTelemetry:
        in_memory_exporter = _FakeExporter()

    class _FakeMapper:
        def map_to_session(self, finished_spans, session_id=None):
            return "offline-fake-session"

    import orchestrator.graph as graph_module

    monkeypatch.setattr(
        graph_module, "build_reconciliation_graph", fake_build_reconciliation_graph
    )
    monkeypatch.setattr(run_evals, "telemetry", _FakeTelemetry())
    monkeypatch.setattr(run_evals, "StrandsInMemorySessionMapper", _FakeMapper)

    out = run_evals.run_case(case)

    # The graph ran exactly once, on the clean customer pointer.
    assert captured, "graph was never invoked"
    assert len(captured) == 1, f"graph invoked {len(captured)} times"
    assert case.input["customer_id"] in captured[0]
    _assert_no_leak(captured[0], "instruction at the graph call site")
    assert "Seed scenario" not in captured[0]
    assert "seed_scenario" not in captured[0]
    # run_case's packaging contract holds with the fakes in place.
    assert out == {
        "output": "offline-fake-case-file",
        "trajectory": "offline-fake-session",
    }


# --- Fix B: the four read tools against the REAL seed file ------------------

@pytest.mark.parametrize("case", test_cases, ids=lambda c: c.name)
def test_read_tool_returns_are_annotation_free(case):
    cid = case.input["customer_id"]
    payloads = [
        ("legacy", read_legacy_system(cid)),
        ("modern_record", read_modern_system(cid)),
        ("transaction_row", search_transactions(cid, "legacy", "2026-08-01T00:00:00Z", "2026-09-30T00:00:00Z")),
        ("transaction_row", search_transactions(cid, "modern", "2026-08-01T00:00:00Z", "2026-09-30T00:00:00Z")),
        ("event_row", get_event_log(cid, "legacy")),
        ("event_row", get_event_log(cid, "modern")),
    ]
    blob = []
    for kind, payload in payloads:
        rows = payload if isinstance(payload, list) else [payload]
        for row in rows:
            assert set(row) <= ALLOWED_FIELDS[kind], (kind, set(row) - ALLOWED_FIELDS[kind])
        _assert_no_annotation_keys(payload, kind)
        blob.append(json.dumps(payload, default=str))
    _assert_no_leak("\n".join(blob), "tool returns")


# --- Fix B: the FILTER is the invariant, not today's seed layout -------------

def test_key_filter_survives_a_poisoned_seed(tmp_path, monkeypatch):
    """With a _comment planted INSIDE records/rows/payload — where the
    pre-fix pass-throughs would have forwarded it verbatim to the agent —
    the tools must still return annotation-free data."""
    poisoned = tmp_path / "seed-poisoned.json"
    seed = json.loads(seed_data.SEED_PATH.read_text(encoding="utf-8"))
    note = "Reversal posted in legacy, never mirrored to modern."
    seed["legacy_system"]["C-1001"]["_comment"] = note
    seed["modern_system"]["C-1001"]["_comment"] = note
    seed["transactions"]["C-1001"]["legacy"][0]["_comment"] = note
    seed["event_log"]["C-1001"]["legacy"][0]["payload"]["_comment"] = note
    poisoned.write_text(json.dumps(seed), encoding="utf-8")
    monkeypatch.setattr(seed_data, "SEED_PATH", poisoned)
    seed_data._load_seed.cache_clear()
    try:
        for name, payload in (
            ("read_legacy_system", read_legacy_system("C-1001")),
            ("read_modern_system", read_modern_system("C-1001")),
            ("search_transactions", search_transactions(
                "C-1001", "legacy", "2026-08-01T00:00:00Z", "2026-09-30T00:00:00Z")),
            ("get_event_log", get_event_log("C-1001", "legacy")),
        ):
            _assert_no_annotation_keys(payload, name)
            assert note not in json.dumps(payload, default=str), name
    finally:
        # Restore the real seed for any later test in this process.
        seed_data._load_seed.cache_clear()


# --- Fix C: the trajectory rubric references only received data -------------

def test_trajectory_rubric_references_no_unsent_data():
    rubric = run_evals.trajectory_evaluator.rubric
    assert "(see case metadata)" not in rubric
    assert "metadata" not in rubric
    # The efficiency criterion itself survives, now judgeable from the
    # <Trajectory> block the judge actually receives.
    assert "get_event_log" in rubric
    assert "search_transactions" in rubric


# --- The answer key itself stays frozen (anti-drift pin) --------------------

def test_frozen_answer_key_is_byte_identical():
    observed = [
        (case.name, case.input["customer_id"], case.input["seed_scenario"], case.expected_output)
        for case in test_cases
    ]
    assert observed == FROZEN_ANSWER_KEY
    for case, (_, _, _, expected) in zip(test_cases, FROZEN_ANSWER_KEY):
        assert case.metadata["root_cause_category"] == expected
