# util/wiki_markdown.py
# A separate markdown-it-py instance for wiki article bodies, entirely
# independent of markdownit's own plain `{{ text|markdownit }}` template
# filter (main/models/slug.py's normal static-content rendering keeps using
# that, unmodified). Adds a `[[Page Name]]` / `[[Page Name|Display Text]]`
# inline rule, MediaWiki-style, that resolves to a link within a given
# wiki's page tree (see main.models.slug.Slug.wiki_root) - or to a
# distinctly-styled "missing page" link pointing at the create-page view
# when no such page exists yet.
#
# Written as a real markdown-it-py inline tokenizer rule (not a regex
# pre/post-pass) specifically so it inherits the parser's own code-span/
# fence handling for free: a `[[...]]`-shaped string inside a code span or
# fenced code block is never seen by this rule at all, since backticks/
# fences are consumed as their own tokens earlier in the same pass.
import re

from django.utils.text import slugify
from markdown_it import MarkdownIt
from markdown_it.common.utils import escapeHtml
from markdown_it.rules_inline import StateInline

# Group 1: target page name. Group 2 (optional): custom display text after
# a pipe, MediaWiki-style. Deliberately excludes '[', ']', '|', and
# newlines from the target/display text - a real second link/newline
# inside the brackets means this isn't a wikilink after all.
_WIKILINK_RE = re.compile(r"\[\[([^\[\]|\n]+)(?:\|([^\[\]\n]+))?\]\]")


def _wikilink_rule(state: StateInline, silent: bool) -> bool:
    pos = state.pos
    if state.src[pos:pos + 2] != "[[":
        return False

    match = _WIKILINK_RE.match(state.src, pos)
    if not match:
        return False

    if not silent:
        token = state.push("wikilink", "", 0)
        token.meta = {
            "target": match.group(1).strip(),
            "display": (match.group(2) or match.group(1)).strip(),
        }

    state.pos = match.end()
    return True


def _render_wikilink(self, tokens, idx, options, env):
    # `add_render_rule()` binds this as a method of the Renderer instance
    # (`function.__get__(self.renderer)`), matching the signature every
    # built-in render rule uses - `self` here is the Renderer, unused.
    """`env` carries the request-time context a pure text-transform rule
    can't know on its own: which wiki tree to resolve names against, and
    how to build the "create this page" URL for a name that doesn't
    resolve. Passed in via `render_wiki_markdown()` below, not hardcoded
    here, so this module has no dependency on how the wiki views build
    their own URLs.
    """
    token = tokens[idx]
    target = token.meta["target"]
    display = token.meta["display"]

    resolve_link = env.get("resolve_wikilink")
    if resolve_link is None:
        # No resolver configured - render inert, rather than guess a URL.
        return f'<span class="wiki-link wiki-link-unresolved">{escapeHtml(display)}</span>'

    url, exists = resolve_link(target)
    css_class = "wiki-link" if exists else "wiki-link wiki-link-missing"
    title_attr = "" if exists else f' title="This page doesn\'t exist yet - click to create it."'
    return f'<a class="{css_class}" href="{escapeHtml(url)}"{title_attr}>{escapeHtml(display)}</a>'


def get_wiki_markdown_renderer():
    """A fresh MarkdownIt instance with the wikilink rule installed -
    matches markdownit's own templatetag, which also instantiates fresh
    per render rather than sharing one module-level instance."""
    md = MarkdownIt()
    md.inline.ruler.before("link", "wikilink", _wikilink_rule)
    md.add_render_rule("wikilink", _render_wikilink)
    return md


def _extract_toc(tokens):
    """Walks the token stream for heading_open/inline/heading_close
    triples, assigns each heading a unique anchor id (set directly on the
    heading_open token, so the renderer below emits it as part of the
    normal HTML - no separate re-parse of the rendered output needed),
    and returns the table of contents as
    [{"level": 1-6, "text": ..., "anchor": ...}, ...] in document order.

    Uses the heading's raw source text (the inline token's .content) for
    both the anchor and the TOC label - if a heading itself contains
    markdown formatting (rare in practice), the TOC entry shows the raw
    markup rather than rendering it, a deliberate simplification rather
    than re-rendering nested inline content outside its normal HTML
    context.
    """
    toc = []
    used_anchors = set()
    for i, token in enumerate(tokens):
        if token.type != "heading_open":
            continue
        level = int(token.tag[1:])
        heading_text = tokens[i + 1].content.strip()

        anchor = slugify(heading_text) or "section"
        base_anchor, n = anchor, 2
        while anchor in used_anchors:
            anchor = f"{base_anchor}-{n}"
            n += 1
        used_anchors.add(anchor)

        token.attrSet("id", anchor)
        toc.append({"level": level, "text": heading_text, "anchor": anchor})
    return toc


def render_wiki_markdown(text, resolve_wikilink):
    """resolve_wikilink(target: str) -> (url: str, exists: bool). Returns
    (html, toc) - html is sanitized the same way markdownit's own filter
    is (nh3, allowing the extra class/title/id attributes the wikilink
    rule and heading anchors add - nh3's default allowlist strips them
    otherwise); toc is _extract_toc()'s heading list, empty if the
    article has no headings."""
    import nh3

    md = get_wiki_markdown_renderer()
    env = {"resolve_wikilink": resolve_wikilink}
    tokens = md.parse(text, env)
    toc = _extract_toc(tokens)
    html = md.renderer.render(tokens, md.options, env)

    clean_html = nh3.clean(
        html,
        attributes={
            **nh3.ALLOWED_ATTRIBUTES,
            "a": (nh3.ALLOWED_ATTRIBUTES.get("a", set()) | {"class", "title"}),
            "h1": {"id"}, "h2": {"id"}, "h3": {"id"}, "h4": {"id"}, "h5": {"id"}, "h6": {"id"},
        },
    )
    return clean_html, toc
