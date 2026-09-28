"""Assistant formatting must never turn model output into executable browser content."""

from engineering_gateway.api.assistant_markdown import render_assistant_markdown


def test_markdown_lists_emphasis_code_and_links_render_safely():
    result = render_assistant_markdown(
        "## Исходные вопросы\n\n1. **Назначение** БПЛА\n2. `Масса`\n\n"
        "[Документ](https://example.org/spec)"
    )
    assert "<h2>Исходные вопросы</h2>" in result
    assert "<ol>" in result and "<strong>Назначение</strong>" in result
    assert "<code>Масса</code>" in result
    assert 'href="https://example.org/spec"' in result


def test_raw_html_scripts_and_unsafe_links_are_not_active():
    result = render_assistant_markdown(
        '<img src=x onerror=alert(1)>\n\n<script>alert(2)</script>\n\n'
        '[click](javascript:alert(3)) and [safe](https://example.org)'
    )
    assert "<script" not in result and "<img" not in result
    assert "&lt;img src=x onerror=" in result and 'href="javascript:' not in result
    assert 'href="https://example.org"' in result
