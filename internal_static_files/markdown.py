from markdown_it import MarkdownIt


_renderer = MarkdownIt("gfm-like2", {
    "breaks": True,
    "html": True
}).enable("table")


def render_markdown(markdown_text: str) -> str:
    return _renderer.render(markdown_text)
