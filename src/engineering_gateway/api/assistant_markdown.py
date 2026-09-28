"""Render untrusted assistant Markdown for the portal with a narrow HTML allowlist."""

import bleach  # type: ignore[import-untyped]
from typing import cast
from markdown_it import MarkdownIt

_markdown = MarkdownIt("js-default")
_cleaner = bleach.Cleaner(
    tags={
        "p", "br", "strong", "em", "s", "del", "ul", "ol", "li", "blockquote",
        "pre", "code", "h1", "h2", "h3", "h4", "hr", "a", "table", "thead",
        "tbody", "tr", "th", "td",
    },
    attributes={"a": ["href", "title"]},
    protocols={"http", "https", "mailto"},
    strip=True,
)


def render_assistant_markdown(source: str) -> str:
    """Return only formatting and safe links; no model-supplied HTML or scripts."""
    return cast(str, _cleaner.clean(_markdown.render(source)))
