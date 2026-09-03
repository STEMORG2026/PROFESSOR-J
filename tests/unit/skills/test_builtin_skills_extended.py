"""Extended tests for built-in skills (project automation + MCP integration).

Covers the HardcodedCommandExecutionSkill (ProjectBuildSkill), GitExtendedSkill,
FileTemplateSkill, and MCPSkill validation / branch behaviour. These tests avoid
spawning real subprocesses or real MCP servers: command-execution methods are tested
on their failure/validation branches, and FileTemplateSkill writes to tmp_path.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from app.mcp import MCPResource, MCPTool
from app.skills.builtin import (
    BUILTIN_SKILLS,
    FileTemplateSkill,
    GitExtendedSkill,
    MCPSkill,
    ProjectBuildSkill,
    register_builtin_skills,
)
from app.skills.registry import SkillRegistry


class TestRegistryExtended:
    """Registry wiring for the project-automation skills."""

    def test_builtin_skills_has_fifteen(self) -> None:
        # Original 6 + 3 project automation + 6 ecosystem development agent = 15
        assert len(BUILTIN_SKILLS) == 15
        for name in (
            "filesystem",
            "git",
            "web_search",
            "code_execution",
            "lhstem_knowledge",
            "memory",
            "project_build",
            "git_extended",
            "file_template",
            "grounded_citations",
            "arxiv",
            "workspace_synthesis",
            "github_auth",
            "github_code_review",
            "github_pr_workflow",
        ):
            assert name in BUILTIN_SKILLS

    def test_mcp_skill_not_auto_registered(self) -> None:
        # MCPSkill lives alongside the built-ins but is deliberately not part of
        # the auto-registered BUILTIN_SKILLS set (it needs a config path / manager).
        assert "mcp" not in BUILTIN_SKILLS
        assert MCPSkill not in BUILTIN_SKILLS.values()

    def test_register_builtin_skills_extends(self, tmp_path: Path) -> None:
        registry = SkillRegistry(skills_dir=tmp_path / "skills")
        count = register_builtin_skills(registry)
        assert count == 15
        assert registry.get("project_build") is not None
        assert registry.get("git_extended") is not None
        assert registry.get("file_template") is not None
        # Ecosystem development agent skills
        assert registry.get("grounded_citations") is not None
        assert registry.get("arxiv") is not None
        assert registry.get("workspace_synthesis") is not None
        assert registry.get("github_auth") is not None
        assert registry.get("github_code_review") is not None
        assert registry.get("github_pr_workflow") is not None

    @pytest.mark.parametrize(
        "name,cls",
        [
            ("project_build", ProjectBuildSkill),
            ("git_extended", GitExtendedSkill),
            ("file_template", FileTemplateSkill),
        ],
    )
    def test_new_skill_metadata(self, name: str, cls: type[Any]) -> None:
        skill = cls()
        assert skill.metadata.name == name
        assert skill.metadata.category == "automation"


class TestProjectBuildSkill:
    """ProjectBuildSkill (hardcoded command execution) — failure branches only.

    The success path would spawn real build commands (pip, pnpm, cargo, go), so it
    is exercised on its validation/unknown-type branches plus a fake subprocess.run.
    """

    def test_validate_params_rejects_unknown_operation(self) -> None:
        skill = ProjectBuildSkill()
        assert skill.validate_params(operation="build") is True
        assert skill.validate_params(operation="deploy") is False

    async def test_unknown_project_type_fails(self) -> None:
        skill = ProjectBuildSkill()
        result = await skill(operation="build", project_type="cobol")
        assert result.status.value == "failed"
        assert "Unknown project type" in (result.error or "")

    async def test_auto_detect_unknown_without_manifest(self, tmp_path: Path) -> None:
        # No pyproject.toml / package.json etc. -> auto-detect yields "unknown".
        skill = ProjectBuildSkill()
        result = await skill(operation="test", project_path=str(tmp_path))
        assert result.status.value == "failed"
        assert "Unknown project type" in (result.error or "")

    async def test_success_with_fake_subprocess(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class FakeResult:
            returncode = 0
            stdout = "ok\n"
            stderr = ""

        monkeypatch.setattr(subprocess, "run", lambda *a, **k: FakeResult())
        skill = ProjectBuildSkill()
        result = await skill(operation="build", project_type="python", project_path=str(tmp_path))
        assert result.status.value == "success"
        assert result.data is not None
        assert result.data["project_type"] == "python"
        assert result.data["operations"]["build"]["status"] == "success"

    async def test_subprocess_exception_recorded_as_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _boom(*a: Any, **k: Any) -> Any:
            raise RuntimeError("boom")

        monkeypatch.setattr(subprocess, "run", _boom)
        skill = ProjectBuildSkill()
        result = await skill(operation="test", project_type="go", project_path=str(tmp_path))
        assert result.status.value == "success"  # operation failure is captured, not raised
        assert result.data is not None
        assert result.data["operations"]["test"]["status"] == "error"
        assert result.data["operations"]["test"]["error"] == "boom"


class TestGitExtendedSkill:
    """GitExtendedSkill — only branches that do NOT spawn real git commands."""

    def test_validate_params(self) -> None:
        skill = GitExtendedSkill()
        assert skill.validate_params(operation="status") is True
        assert skill.validate_params(operation="squash") is False

    async def test_not_a_git_repository_fails(self, tmp_path: Path) -> None:
        skill = GitExtendedSkill()
        result = await skill(operation="status", repo_path=str(tmp_path))
        assert result.status.value == "failed"
        assert "Not a git repository" in (result.error or "")

    async def test_unknown_operation_fails(self, tmp_path: Path) -> None:
        # Bypass __call__ validation (execute directly) so we reach the
        # "operation not in commands" branch without spawning git. The .git guard
        # must pass first, so seed a .git directory.
        git_dir = tmp_path / ".git"
        git_dir.mkdir(parents=True, exist_ok=True)
        skill = GitExtendedSkill()
        result = await skill.execute(operation="cherry_pick", repo_path=str(tmp_path))
        assert result.status.value == "failed"
        assert "Unknown operation" in (result.error or "")

    async def test_invalid_operation_rejected_by_validate(self, tmp_path: Path) -> None:
        skill = GitExtendedSkill()
        result = await skill(operation="squash", repo_path=str(tmp_path))
        assert result.status.value == "failed"
        assert "Invalid parameters" in (result.error or "")


class TestFileTemplateSkill:
    """FileTemplateSkill — template materialization into tmp_path."""

    def test_validate_params(self) -> None:
        skill = FileTemplateSkill()
        assert skill.validate_params(operation="generate") is True
        assert skill.validate_params(operation="init") is False

    async def test_list_templates(self) -> None:
        skill = FileTemplateSkill()
        result = await skill(operation="list")
        assert result.status.value == "success"
        assert result.data is not None
        for name in ("python_cli", "python_fastapi", "react_component"):
            assert name in result.data["templates"]

    async def test_generate_python_cli(self, tmp_path: Path) -> None:
        skill = FileTemplateSkill()
        result = await skill(
            operation="generate",
            template_name="python_cli",
            output_path=str(tmp_path),
            variables={"project_name": "demo", "description": "A demo CLI"},
        )
        assert result.status.value == "success"
        assert result.data is not None
        assert result.data["template"] == "python_cli"
        assert len(result.data["created_files"]) == 3
        assert (tmp_path / "pyproject.toml").exists()
        content = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
        assert 'name = "demo"' in content
        assert "A demo CLI" in content

    async def test_generate_python_fastapi(self, tmp_path: Path) -> None:
        skill = FileTemplateSkill()
        result = await skill(
            operation="generate",
            template_name="python_fastapi",
            output_path=str(tmp_path),
            variables={"project_name": "mysvc"},
        )
        assert result.status.value == "success"
        assert (tmp_path / "pyproject.toml").exists()
        assert (tmp_path / "tests" / "test_main.py").exists()

    async def test_generate_react_component(self, tmp_path: Path) -> None:
        skill = FileTemplateSkill()
        result = await skill(
            operation="generate",
            template_name="react_component",
            output_path=str(tmp_path),
            variables={"component_name": "Button", "class_name": "btn"},
        )
        assert result.status.value == "success"
        assert result.data is not None
        assert len(result.data["created_files"]) == 3
        # NOTE: the implementation substitutes variables into file *content* only;
        # the file *names* keep the literal {{component_name}} placeholder.
        tsx = tmp_path / "{{component_name}}.tsx"
        assert tsx.exists()
        assert "Button" in tsx.read_text(encoding="utf-8")

    async def test_generate_unknown_template_fails(self, tmp_path: Path) -> None:
        skill = FileTemplateSkill()
        result = await skill(operation="generate", template_name="nope", output_path=str(tmp_path))
        assert result.status.value == "failed"
        assert "not found" in (result.error or "")

    async def test_create_custom(self, tmp_path: Path) -> None:
        skill = FileTemplateSkill()
        result = await skill(
            operation="create_custom",
            template_name="my_tpl",
            output_path=str(tmp_path),
            template_content='{"files": {}}',
        )
        assert result.status.value == "success"
        saved = tmp_path / ".professor-templates" / "my_tpl.json"
        assert saved.exists()
        assert json.loads(saved.read_text(encoding="utf-8")) == {"files": {}}

    async def test_create_custom_missing_content_fails(self, tmp_path: Path) -> None:
        skill = FileTemplateSkill()
        result = await skill(
            operation="create_custom", template_name="my_tpl", output_path=str(tmp_path)
        )
        assert result.status.value == "failed"
        assert "template_content required" in (result.error or "")

    async def test_unknown_operation_fails(self) -> None:
        skill = FileTemplateSkill()
        result = await skill.execute(operation="init")
        assert result.status.value == "failed"
        assert "Unknown operation" in (result.error or "")


class TestMCPSkill:
    """MCPSkill — validation and branch coverage without real MCP servers."""

    @pytest.fixture
    def config_file(self, tmp_path: Path) -> Path:
        cfg = tmp_path / "mcp_servers.json"
        cfg.write_text(
            json.dumps(
                {
                    "servers": [
                        {
                            "server_id": "srv1",
                            "name": "Server One",
                            "transport": "stdio",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        return cfg

    async def test_list_servers_happy(self, config_file: Path) -> None:
        skill = MCPSkill()
        result = await skill(operation="list_servers", config_path=str(config_file))
        assert result.status.value == "success"
        assert result.data is not None
        assert result.data["servers"] == [
            {"server_id": "srv1", "name": "Server One", "transport": "stdio"}
        ]

    async def test_list_servers_missing_file_returns_empty(self, tmp_path: Path) -> None:
        skill = MCPSkill()
        result = await skill(operation="list_servers", config_path=str(tmp_path / "missing.json"))
        assert result.status.value == "success"
        assert result.data is not None
        assert result.data["servers"] == []

    async def test_list_servers_invalid_json_fails(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text("not json", encoding="utf-8")
        skill = MCPSkill()
        result = await skill(operation="list_servers", config_path=str(bad))
        assert result.status.value == "failed"
        assert "Failed to read config" in (result.error or "")

    async def test_connect_server_missing_server_id(self, tmp_path: Path) -> None:
        # Nonexistent config -> empty manager (create_mcp_manager_from_config won't raise).
        skill = MCPSkill()
        result = await skill(operation="connect_server", config_path=str(tmp_path / "nope.json"))
        assert result.status.value == "failed"
        assert "server_id required" in (result.error or "")

    async def test_import_error_guard(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class _ImportErrorModule:
            def __getattr__(self, name: str) -> Any:
                raise ImportError(f"No module named {name}")

        monkeypatch.setitem(sys.modules, "app.mcp", _ImportErrorModule())
        skill = MCPSkill()
        result = await skill(operation="list_tools")
        assert result.status.value == "failed"
        assert "MCP module not available" in (result.error or "")

    def test_validate_params(self) -> None:
        skill = MCPSkill()
        assert skill.validate_params(operation="call_tool") is True
        assert skill.validate_params(operation="spawn") is False

    async def test_unknown_operation_fails(self) -> None:
        skill = MCPSkill()
        result = await skill.execute(operation="teleport")
        assert result.status.value == "failed"
        assert "Unknown operation" in (result.error or "")


class TestMCPSkillWithFakeManager:
    """MCPSkill deeper branches using a fake MCPClientManager (no real servers)."""

    @pytest.fixture
    def skill(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> MCPSkill:
        fake = FakeMCPManager()
        monkeypatch.setattr("app.mcp.create_mcp_manager_from_config", lambda _: fake)
        return MCPSkill()

    async def test_connect_server_success(self, skill: MCPSkill) -> None:
        result = await skill(operation="connect_server", server_id="srv1")
        assert result.status.value == "success"
        assert result.data is not None
        assert result.data["connected"] is True

    async def test_connect_server_not_connected(self, skill: MCPSkill) -> None:
        result = await skill(operation="connect_server", server_id="srv_ghost")
        assert result.status.value == "success"
        assert result.data is not None
        assert result.data["connected"] is False

    async def test_disconnect_server_missing_id(self, skill: MCPSkill) -> None:
        result = await skill(operation="disconnect_server")
        assert result.status.value == "failed"
        assert "server_id required" in (result.error or "")

    async def test_disconnect_server_found(self, skill: MCPSkill) -> None:
        result = await skill(operation="disconnect_server", server_id="srv1")
        assert result.status.value == "success"
        assert result.data is not None
        assert result.data["disconnected"] is True

    async def test_disconnect_server_not_found(self, skill: MCPSkill) -> None:
        result = await skill(operation="disconnect_server", server_id="srv_missing")
        assert result.status.value == "failed"
        assert "Server not found" in (result.error or "")

    async def test_list_tools_missing_server_id(self, skill: MCPSkill) -> None:
        result = await skill(operation="list_tools")
        assert result.status.value == "failed"
        assert "server_id required" in (result.error or "")

    async def test_list_tools_connect_failure(self, skill: MCPSkill) -> None:
        result = await skill(operation="list_tools", server_id="srv_unreachable")
        assert result.status.value == "failed"
        assert "Failed to connect" in (result.error or "")

    async def test_list_tools_success(self, skill: MCPSkill) -> None:
        result = await skill(operation="list_tools", server_id="srv1")
        assert result.status.value == "success"
        assert result.data is not None
        names = [t["name"] for t in result.data["tools"]]
        assert names == ["read_file"]  # only srv1 tool

    async def test_call_tool_missing_server_id(self, skill: MCPSkill) -> None:
        result = await skill(operation="call_tool", tool_name="x")
        assert result.status.value == "failed"
        assert "server_id required" in (result.error or "")

    async def test_call_tool_missing_tool_name(self, skill: MCPSkill) -> None:
        result = await skill(operation="call_tool", server_id="srv1")
        assert result.status.value == "failed"
        assert "tool_name required" in (result.error or "")

    async def test_call_tool_success(self, skill: MCPSkill) -> None:
        result = await skill(
            operation="call_tool", server_id="srv1", tool_name="read_file", arguments={"p": "a"}
        )
        assert result.status.value == "success"
        assert result.data is not None
        assert result.data["result"] == {"ok": True}

    async def test_call_tool_exception(self, skill: MCPSkill) -> None:
        result = await skill(operation="call_tool", server_id="srv1", tool_name="boom")
        assert result.status.value == "failed"
        assert "kaboom" in (result.error or "")

    async def test_list_resources_success(self, skill: MCPSkill) -> None:
        result = await skill(operation="list_resources", server_id="srv1")
        assert result.status.value == "success"
        assert result.data is not None
        assert result.data["resources"] == [
            {"uri": "res://a", "name": "A", "description": "desc", "mime_type": "text/plain"}
        ]

    async def test_list_resources_filter(self, skill: MCPSkill) -> None:
        # srv_none connects but owns no resources -> filtered list is empty.
        result = await skill(operation="list_resources", server_id="srv_none")
        assert result.status.value == "success"
        assert result.data is not None
        assert result.data["resources"] == []

    async def test_read_resource_missing_uri(self, skill: MCPSkill) -> None:
        result = await skill(operation="read_resource", server_id="srv1")
        assert result.status.value == "failed"
        assert "resource_uri required" in (result.error or "")

    async def test_read_resource_missing_server_id(self, skill: MCPSkill) -> None:
        result = await skill(operation="read_resource", resource_uri="res://a")
        assert result.status.value == "failed"
        assert "server_id required" in (result.error or "")

    async def test_read_resource_success(self, skill: MCPSkill) -> None:
        result = await skill(operation="read_resource", server_id="srv1", resource_uri="res://a")
        assert result.status.value == "success"
        assert result.data is not None
        assert result.data["result"] == {"uri": "res://a"}

    async def test_read_resource_exception(self, skill: MCPSkill) -> None:
        result = await skill(operation="read_resource", server_id="srv1", resource_uri="res://boom")
        assert result.status.value == "failed"
        assert "kaboom" in (result.error or "")


class FakeMCPManager:
    """Stands in for app.mcp.MCPClientManager.

    srv1 connects successfully and exposes one tool + one resource. srv_unreachable
    fails to connect. Everything else connects but is just absent from _clients.
    """

    def __init__(self) -> None:
        self._connected = {"srv1": True, "srv_missing": True, "srv_other": True, "srv_none": True}
        self._clients = {"srv1": FakeClient()}

    async def connect_all(self) -> dict[str, bool]:
        return {sid: sid != "srv_unreachable" for sid in self._connected}

    def list_tools(self) -> list[MCPTool]:
        return [
            MCPTool(
                name="read_file",
                description="Read a file",
                input_schema={"type": "object"},
                server_id="srv1",
            ),
            MCPTool(
                name="other_tool",
                description="Other",
                input_schema={"type": "object"},
                server_id="srv_other",
            ),
        ]

    def list_resources(self) -> list[MCPResource]:
        return [
            MCPResource(
                uri="res://a",
                name="A",
                description="desc",
                mime_type="text/plain",
                server_id="srv1",
            ),
            MCPResource(
                uri="res://b",
                name="B",
                description="other",
                mime_type=None,
                server_id="srv_other",
            ),
        ]

    async def call_tool(
        self, server_id: str, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        if tool_name == "boom":
            raise RuntimeError("kaboom")
        return {"ok": True}

    async def read_resource(self, server_id: str, uri: str) -> dict[str, Any]:
        if uri == "res://boom":
            raise RuntimeError("kaboom")
        return {"uri": uri}


class FakeClient:
    async def disconnect(self) -> None:
        return None
