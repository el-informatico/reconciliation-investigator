"""Environment smoke test (Ares V2 python-strands profile).

Proves the pinned toolchain installed and imports cleanly. This is NOT
an application test: the application's own tests arrive with its
implementation tasks (the build contract governs those —
docs/build-contract.md).
"""

from strands import Agent, tool
import strands_evals


def test_strands_sdk_imports() -> None:
    # The pinned strands-agents distribution exposes the Agent
    # constructor and the @tool decorator at the top level (verified
    # against the pinned version's documented quickstart shape).
    assert callable(Agent)
    assert callable(tool)


def test_evals_package_imports() -> None:
    # strands-agents-evals imports under the name strands_evals.
    assert strands_evals is not None
