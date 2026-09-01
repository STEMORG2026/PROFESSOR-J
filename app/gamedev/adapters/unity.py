"""UnityEngineAdapter — Presentation Engine Adapter for Unity.

Generates Unity presentation layers, CoreBridge event sinks, Input adapters, State presenters,
and Entity views that consume engine-neutral GameCore domain rules without contaminating
the GameCore with UnityEngine dependencies.
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path
from typing import Any

from app.domain.gamedev import (
    EngineTarget,
    GameArchitecturePattern,
    GameComponentSpec,
    GameProjectSpec,
    GameTestReport,
    GameValidationReport,
)
from app.gamedev.base import GameEngineAdapter
from app.gamedev.validator import GameArchitectureValidator
from app.workspace.workspace import WorkspaceManager

logger = logging.getLogger(__name__)


class UnityEngineAdapter(GameEngineAdapter):
    """Engine adapter for Unity presentation layers."""

    @property
    def engine_target(self) -> EngineTarget:
        return EngineTarget.UNITY

    @property
    def supported_languages(self) -> tuple[str, ...]:
        return ("csharp", "python")

    def scaffold_project(
        self,
        spec: GameProjectSpec,
        workspace: WorkspaceManager,
        project_dir: str | None = None,
    ) -> list[str]:
        """Scaffold a Unity presentation project with decoupled pure domain rules."""
        base_dir = (project_dir or spec.title.lower().replace(" ", "_")).strip("/")
        generated: list[str] = []

        # 1. Scaffolding README / Architecture Manifest
        readme_content = f"""# {spec.title} — Unity Presentation Client

> **Architecture:** Pure GameCore + Unity Presentation Adapter
> **Target Engine:** Unity (C# / WebGL / Desktop)
> **Determinism:** {'Strictly Deterministic' if spec.is_deterministic else 'Non-deterministic'}
> **Max Players:** {spec.max_players}

## Architecture Invariants
1. **One-Way Dependency**: Unity presentation depends on GameCore; GameCore NEVER imports engine.
2. **Authoritative Truth**: GameCore owns state, rules, intents, and event calculations.
3. **Presentation View**: Unity MonoBehaviours are views, event sinks, and input translators only.
4. **Frame-Rate Independence**: Fixed accumulation drives simulation ticks deterministically.
"""
        readme_path = f"{base_dir}/README.md"
        workspace.write(readme_path, readme_content)
        generated.append(readme_path)

        # 2. Project metadata
        version_txt = (
            "m_EditorVersion: 2022.3.20f1\n"
            "m_EditorVersionWithRevision: 2022.3.20f1 (e30c45167f2e)\n"
        )
        version_path = f"{base_dir}/ProjectSettings/ProjectVersion.txt"
        workspace.write(version_path, version_txt)
        generated.append(version_path)

        # 3. Pure C# Domain Layer (zero UnityEngine)
        domain_csproj = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
    <RootNamespace>GameCore.Domain</RootNamespace>
  </PropertyGroup>
</Project>
"""
        domain_csproj_path = f"{base_dir}/Assets/Scripts/Domain/GameCore.Domain.csproj"
        workspace.write(domain_csproj_path, domain_csproj)
        generated.append(domain_csproj_path)

        # Domain Contracts
        domain_contracts_cs = """namespace GameCore.Domain
{
    public interface IGameIntent {}
    public interface IGameEvent {}

    public record IntentResult(bool Success, string? Error = null);
    public record StepResult(int Tick, float DeltaTime);
}
"""
        contracts_path = f"{base_dir}/Assets/Scripts/Domain/Contracts.cs"
        workspace.write(contracts_path, domain_contracts_cs)
        generated.append(contracts_path)

        # 4. CoreBridge & Presenters
        core_bridge_cs = """using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Events;

namespace GamePresentation.CoreBridge
{
    /// <summary>
    /// CoreBridge — the ONLY connection between GameCore and Unity.
    /// Listens to domain events and dispatches UnityEvents for animations, SFX, VFX, and UI.
    /// </summary>
    public class CoreBridge : MonoBehaviour
    {
        [Header("Event Sinks")]
        public UnityEvent<string> OnDomainEventEmitted = new UnityEvent<string>();

        private readonly Queue<object> _pendingEvents = new Queue<object>();

        public void EnqueueEvent(object domainEvent)
        {
            _pendingEvents.Enqueue(domainEvent);
        }

        public void DrainEvents(Action<object> eventHandler)
        {
            while (_pendingEvents.Count > 0)
            {
                var ev = _pendingEvents.Dequeue();
                eventHandler?.Invoke(ev);
                OnDomainEventEmitted?.Invoke(ev.ToString() ?? "");
            }
        }
    }
}
"""
        bridge_path = f"{base_dir}/Assets/Scripts/CoreBridge/CoreBridge.cs"
        workspace.write(bridge_path, core_bridge_cs)
        generated.append(bridge_path)

        # UnityGameRunner (Fixed-timestep simulation driver)
        runner_cs = """using UnityEngine;
using GamePresentation.CoreBridge;

namespace GamePresentation
{
    public class UnityGameRunner : MonoBehaviour
    {
        [SerializeField] private CoreBridge _bridge = null!;
        [SerializeField] private float _fixedTimestep = 1f / 60f;

        private float _accumulator = 0f;

        private void Update()
        {
            _accumulator += Time.deltaTime;
            while (_accumulator >= _fixedTimestep)
            {
                // Drive fixed-timestep simulation tick
                _accumulator -= _fixedTimestep;
            }

            _bridge.DrainEvents(OnEventReceived);
        }

        private void OnEventReceived(object domainEvent)
        {
            // Presentation event handling
        }
    }
}
"""
        runner_path = f"{base_dir}/Assets/Scripts/Presentation/UnityGameRunner.cs"
        workspace.write(runner_path, runner_cs)
        generated.append(runner_path)

        # Input Adapter
        input_adapter_cs = """using UnityEngine;

namespace GamePresentation.Input
{
    public class UnityInputAdapter : MonoBehaviour
    {
        public Vector2 GetMovementInput()
        {
            float horizontal = UnityEngine.Input.GetAxisRaw("Horizontal");
            float vertical = UnityEngine.Input.GetAxisRaw("Vertical");
            return new Vector2(horizontal, vertical);
        }

        public bool IsAttackPressed()
        {
            var key = UnityEngine.Input.GetKeyDown(KeyCode.Space);
            var mouse = UnityEngine.Input.GetMouseButtonDown(0);
            return key || mouse;
        }
    }
}
"""
        input_path = f"{base_dir}/Assets/Scripts/Input/UnityInputAdapter.cs"
        workspace.write(input_path, input_adapter_cs)
        generated.append(input_path)

        # Entity View
        entity_view_cs = """using UnityEngine;

namespace GamePresentation.Views
{
    public class UnityEntityView : MonoBehaviour
    {
        public string EntityId { get; set; } = "";

        public void SyncPosition(float x, float y, float z = 0f)
        {
            transform.position = new Vector3(x, y, z);
        }

        public void PlayAnimation(string triggerName)
        {
            var animator = GetComponent<Animator>();
            if (animator != null)
            {
                animator.SetTrigger(triggerName);
            }
        }
    }
}
"""
        view_path = f"{base_dir}/Assets/Scripts/Presentation/UnityEntityView.cs"
        workspace.write(view_path, entity_view_cs)
        generated.append(view_path)

        # 5. Tests
        test_csproj = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
    <IsPackable>false</IsPackable>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.NET.Test.Sdk" Version="17.8.0" />
    <PackageReference Include="NUnit" Version="3.14.0" />
    <PackageReference Include="NUnit3TestAdapter" Version="4.5.0" />
  </ItemGroup>
  <ItemGroup>
    <ProjectReference Include="../Assets/Scripts/Domain/GameCore.Domain.csproj" />
  </ItemGroup>
</Project>
"""
        test_csproj_path = f"{base_dir}/Tests/GameCore.Tests.csproj"
        workspace.write(test_csproj_path, test_csproj)
        generated.append(test_csproj_path)

        test_cs = """using NUnit.Framework;
using GameCore.Domain;

namespace GameCore.Tests
{
    [TestFixture]
    public class DomainTests
    {
        [Test]
        public void TestDomainContractsInitialization()
        {
            var result = new IntentResult(true);
            Assert.That(result.Success, Is.True);
        }
    }
}
"""
        test_path = f"{base_dir}/Tests/DomainTests.cs"
        workspace.write(test_path, test_cs)
        generated.append(test_path)

        return generated

    def generate_component(
        self,
        spec: GameComponentSpec,
        project: GameProjectSpec,
    ) -> dict[str, str]:
        """Generate presentation views or pure domain component files."""
        files: dict[str, str] = {}
        comp_name = spec.name

        # If it's a domain component, generate pure C# in Assets/Scripts/Domain/
        domain_cs = f"""namespace GameCore.Domain
{{
    public class {comp_name}
    {{
        public string Name => "{comp_name}";
    }}
}}
"""
        files[f"Assets/Scripts/Domain/{comp_name}.cs"] = domain_cs

        # Generate corresponding Unity View in Assets/Scripts/Presentation/
        view_cs = f"""using UnityEngine;

namespace GamePresentation.Views
{{
    public class {comp_name}View : MonoBehaviour
    {{
        public string ComponentName => "{comp_name}";
    }}
}}
"""
        files[f"Assets/Scripts/Presentation/{comp_name}View.cs"] = view_cs
        return files

    def validate_codebase(
        self,
        workspace: WorkspaceManager,
        project_dir: str,
    ) -> GameValidationReport:
        """Validate architectural purity of domain layer and structure of presentation layer."""
        return GameArchitectureValidator.validate_workspace(
            workspace=workspace,
            project_dir=project_dir,
            pattern=GameArchitecturePattern.PURE_CORE_HEADLESS,
            target=EngineTarget.UNITY,
        )

    def get_build_command(self, project_dir: str) -> list[str]:
        p = Path(project_dir)
        if p.exists() and list(p.glob("**/*.py")) and not list(p.glob("**/*.csproj")):
            return [sys.executable, "-m", "compileall", project_dir]
        return ["dotnet", "build", project_dir]

    def get_test_command(self, project_dir: str) -> list[str]:
        p = Path(project_dir)
        if p.exists() and list(p.glob("**/*.py")) and not list(p.glob("**/*.csproj")):
            return [sys.executable, "-m", "pytest", project_dir]
        return ["dotnet", "test", project_dir]

    def parse_test_output(self, result: Any) -> GameTestReport:
        """Parse raw sandbox test execution result into structured GameTestReport."""
        stdout = getattr(result, "stdout", "")
        stderr = getattr(result, "stderr", "")
        exit_code = getattr(result, "exit_code", 1)
        timed_out = getattr(result, "timed_out", False)
        duration_ms = getattr(result, "duration_ms", 0.0)
        success = getattr(result, "success", False)

        passed_count = 0
        failed_count = 0
        failed_tests: list[str] = []
        failure_details: list[dict[str, Any]] = []

        # Pytest output match
        py_passed_match = re.search(r"(\d+)\s+passed", stdout)
        py_failed_match = re.search(r"(\d+)\s+failed", stdout)
        if py_passed_match:
            passed_count = int(py_passed_match.group(1))
        if py_failed_match:
            failed_count = int(py_failed_match.group(1))

        # NUnit output match (e.g. "Passed: 5, Failed: 1")
        nunit_passed_match = re.search(r"Passed:\s*(\d+)", stdout)
        nunit_failed_match = re.search(r"Failed:\s*(\d+)", stdout)
        if nunit_passed_match:
            passed_count = max(passed_count, int(nunit_passed_match.group(1)))
        if nunit_failed_match:
            failed_count = max(failed_count, int(nunit_failed_match.group(1)))

        for py_fail in re.finditer(r"FAILED\s+([^\s:]+)::([^\s]+)", stdout):
            test_file = py_fail.group(1)
            test_name = py_fail.group(2)
            failed_tests.append(test_name)
            failure_details.append(
                {"test_name": test_name, "file": test_file, "framework": "pytest"}
            )

        if exit_code == 0 and failed_count == 0 and not timed_out:
            success = True

        return GameTestReport(
            success=success,
            exit_code=exit_code,
            passed_count=passed_count,
            failed_count=failed_count,
            duration_ms=duration_ms,
            stdout=stdout,
            stderr=stderr,
            error=stderr if not success and stderr else None,
            timed_out=timed_out,
            failed_tests=tuple(failed_tests),
            failure_details=tuple(failure_details),
        )


__all__ = ["UnityEngineAdapter"]
