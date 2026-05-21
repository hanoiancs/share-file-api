from markdown_it import MarkdownIt


_renderer = MarkdownIt("commonmark", {"html": False})


def render_markdown(markdown_text: str) -> str:
    return _renderer.render(markdown_text)
