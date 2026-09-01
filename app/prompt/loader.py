"""mtime-cached prompt loader — externalized, hot-reloading prompt templates.

Pattern-inherited from JARVIS ``app/prompt/loader.py``. Loads prompt text from
external ``*.md``/``*.txt`` files with ``{variable}`` placeholders, caching
parsed templates keyed by file modification time so edits hot-reload without a
server restart. Dependency-free (no Jinja2): ``{name}`` substitution covers
the prompt-externalization use case (the JARVIS value), with required-variable
introspection for safe rendering.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_VAR_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


class PromptTemplateError(ValueError):
    """Raised for prompt-template rendering/loading failures."""


class PromptLoader:
    """Loader + renderer for externalized prompt templates."""

    def __init__(self, prompts_dir: str | Path = "prompts") -> None:
        self.prompts_dir = Path(prompts_dir)
        self.prompts_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, tuple[float, str]] = {}

    def get_template(self, template_name: str) -> str:
        """Return the template source, refreshing cache when mtime changes."""
        file_path = self.prompts_dir / template_name
        if not file_path.exists():
            raise PromptTemplateError(f"Prompt template missing: {file_path}")
        mtime = file_path.stat().st_mtime
        cached = self._cache.get(template_name)
        if cached and cached[0] == mtime:
            return cached[1]
        source = file_path.read_text(encoding="utf-8")
        self._cache[template_name] = (mtime, source)
        logger.info("Loaded/refreshed prompt template %s (mtime %.3f)", template_name, mtime)
        return source

    def get_required_variables(self, template_name: str) -> set[str]:
        """Return the set of ``{variable}`` placeholders in a template."""
        source = self.get_template(template_name)
        return set(_VAR_RE.findall(source))

    def render(self, template_name: str, **kwargs: Any) -> str:
        """Render a template, substituting ``{var}`` with provided kwargs."""
        source = self.get_template(template_name)
        required = set(_VAR_RE.findall(source))
        missing = required - kwargs.keys()
        if missing:
            raise PromptTemplateError(
                f"Template '{template_name}' missing variables: {sorted(missing)}"
            )
        return _VAR_RE.sub(lambda m: str(kwargs[m.group(1)]), source)

    def exists(self, template_name: str) -> bool:
        return (self.prompts_dir / template_name).exists()


__all__ = ["PromptLoader", "PromptTemplateError"]
