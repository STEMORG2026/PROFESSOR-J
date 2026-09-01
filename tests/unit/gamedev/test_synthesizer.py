"""Unit and property tests for SystemSynthesizer, GameDevReasoner, and Cognitive Repair."""

import tempfile
from collections.abc import Generator
from typing import Any

import pytest

from app.domain.gamedev import (
    FileEdit,
    GameSystemCategory,
    RepairProposal,
)
from app.gamedev.reasoner import (
    CognitiveContext,
    ModelGameDevReasoner,
)
from app.gamedev.repair import CognitiveRepairEngine
from app.gamedev.synthesizer import SystemSynthesizer
from app.models.providers import LLMMessage, LLMProvider, LLMResult
from app.workspace.workspace import WorkspaceManager


@pytest.fixture
def temp_workspace() -> Generator[WorkspaceManager, None, None]:
    with tempfile.TemporaryDirectory() as tmpdir:
        yield WorkspaceManager(tmpdir)


@pytest.mark.asyncio
async def test_system_synthesizer_generation() -> None:
    """1. Synthesizer produces complete contracts, implementation and test suites."""
    synthesizer = SystemSynthesizer()
    spec, source_files, test_files = await synthesizer.synthesize_system(
        request="Create a dynamic stealth detection system with line of sight and alert meter"
    )

    assert spec.system_name != ""
    assert spec.category == GameSystemCategory.GAMEPLAY
    assert len(source_files) >= 2
    assert len(test_files) >= 1

    # Check contracts generated
    contract_file = next(k for k in source_files if "contracts.py" in k)
    assert "@dataclass" in source_files[contract_file]
    assert "State" in source_files[contract_file]

    # Check system implementation generated
    impl_file = next(k for k in source_files if "systems/" in k)
    assert "class " in source_files[impl_file]
    assert "dispatch(self, intent" in source_files[impl_file]

    # Check test file generated
    test_file = next(k for k in test_files if "tests/" in k)
    assert "def test_" in test_files[test_file]
    assert "assert system.dispatch" in test_files[test_file]


@pytest.mark.asyncio
async def test_reasoner_with_mock_llm_json() -> None:
    """2. ModelGameDevReasoner correctly parses structured JSON from LLMProvider."""
    json_response = """
    {
        "system_name": "CraftingSystem",
        "purpose": "Manages item recipes and crafting queue",
        "category": "gameplay",
        "state_fields": {"recipes_unlocked": "list[str]", "crafting_queue": "list[str]"},
        "state_defaults": {"recipes_unlocked": ["potion"], "crafting_queue": []},
        "intents": ["StartCraftingIntent", "CancelCraftingIntent"],
        "intent_parameters": {"StartCraftingIntent": {"recipe_id": "str"}},
        "events": ["ItemCraftedEvent"],
        "event_payloads": {"ItemCraftedEvent": {"item_id": "str"}},
        "dependencies": ["InventoryManager"],
        "invariants": ["Cannot craft locked recipes."],
        "public_operations": ["can_craft", "get_queue_length"]
    }
    """

    class JsonMockProvider(LLMProvider):
        name = "test_llm"
        model = "test_model"

        async def complete(self, messages: list[LLMMessage], **kwargs: Any) -> LLMResult:
            return LLMResult(text=json_response, provider=self.name, model=self.model)

    mock_provider = JsonMockProvider()
    reasoner = ModelGameDevReasoner(provider=mock_provider)
    spec = await reasoner.reason_synthesis("Crafting request", CognitiveContext("Crafting request"))

    assert spec.system_name == "CraftingSystem"
    assert "StartCraftingIntent" in spec.intents
    assert "ItemCraftedEvent" in spec.events
    assert spec.state_defaults["recipes_unlocked"] == ["potion"]


@pytest.mark.asyncio
async def test_repair_engine_rejects_non_implementation_files(
    temp_workspace: WorkspaceManager,
) -> None:
    """3. CognitiveRepairEngine strictly rejects proposals targeting test or config files."""
    repair_engine = CognitiveRepairEngine()

    temp_workspace.write("tests/test_rules.py", "def test_something(): pass")
    temp_workspace.write("pyproject.toml", "[tool.pytest]")
    temp_workspace.write("src/game.py", "class Game: pass")

    baseline_hashes = repair_engine.snapshot_protected_files(temp_workspace, "")

    # Proposal targeting test file must be rejected
    bad_proposal = RepairProposal(
        proposal_id="bad_prop",
        diagnosis="Try modifying test to pass",
        violated_invariant="None",
        root_cause="Test failure",
        target_files=("tests/test_rules.py",),
        edits=(FileEdit("tests/test_rules.py", "pass", "return True"),),
        rationale="Bad edit",
    )

    success, modified = await repair_engine.apply_atomic_proposal(
        temp_workspace, bad_proposal, baseline_hashes
    )
    assert success is False
    assert modified == ()

    # Assert test file remained unchanged
    res = temp_workspace.read("tests/test_rules.py")
    assert res["content"] == "def test_something(): pass"
