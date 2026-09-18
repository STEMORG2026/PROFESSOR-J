"""Tests for Phase 11 SOTA parity tools."""

from __future__ import annotations

import pytest

from app.tools.browser import BrowserControl, create_browser
from app.tools.computer_use import ComputerUse, create_computer_use
from app.tools.web import WebSearch, create_web_search


class TestWebSearch:
    """Test web search."""

    @pytest.fixture
    def web(self) -> WebSearch:
        return create_web_search()

    @pytest.mark.asyncio
    async def test_search(self, web: WebSearch) -> None:
        results = await web.search("python tutorial")
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_fetch(self, web: WebSearch) -> None:
        result = await web.fetch("https://example.com")
        assert result.url == "https://example.com"


class TestBrowser:
    """Test browser control."""

    @pytest.fixture
    def browser(self) -> BrowserControl:
        return create_browser()

    @pytest.mark.asyncio
    async def test_navigate(self, browser: BrowserControl) -> None:
        result = await browser.navigate("https://example.com")
        assert result.success is True
        assert result.url == "https://example.com"

    @pytest.mark.asyncio
    async def test_screenshot(self, browser: BrowserControl) -> None:
        await browser.navigate("https://example.com")
        result = await browser.screenshot("/tmp/test.png")
        assert result.success is True
        assert result.screenshot_path == "/tmp/test.png"


class TestComputerUse:
    """Test computer use."""

    @pytest.fixture
    def desktop(self) -> ComputerUse:
        return create_computer_use()

    @pytest.mark.asyncio
    async def test_launch(self, desktop: ComputerUse) -> None:
        result = await desktop.launch("echo hello")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_focus(self, desktop: ComputerUse) -> None:
        result = await desktop.focus("terminal")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_move(self, desktop: ComputerUse) -> None:
        result = await desktop.move("window", 100, 200)
        assert result.success is True
