"""Small Sphinx extension for the ASYNCH documentation.

Diagrams: an image whose file is in a ``diagrams/`` folder and ends in ``.svg`` is written *inline* in the HTML page,
inside ``<figure class="diagram">``, with its alt text as caption. Inline, the drawing uses the colour variables of
``_static/custom.css`` and therefore follows the light/dark theme of the site; on GitHub the same Markdown line
``![caption](diagrams/name.svg)`` shows the file as an ordinary image with its own (light) colours.
"""
import html
import os
import re

from docutils import nodes

XML_HEADER = re.compile(r"^\s*<\?xml[^>]*\?>\s*", re.S)
VIEWBOX = re.compile(r'viewBox="\s*[-\d.]+\s+[-\d.]+\s+([\d.]+)\s+([\d.]+)"')


def _inline_diagrams(app, doctree, docname):
    if app.builder.format != "html":
        return
    for img in list(doctree.findall(nodes.image)):
        uri = img.get("uri", "")
        if not uri.endswith(".svg") or "diagrams/" not in uri:
            continue
        path = os.path.join(app.srcdir, uri)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            svg = XML_HEADER.sub("", f.read())
        caption = img.get("alt", "")
        m = VIEWBOX.search(svg)
        wide = m is not None and float(m.group(1)) > 760
        if caption:
            svg = svg.replace("<svg ", '<svg role="img" aria-label="%s" ' % html.escape(caption, quote=True), 1)
        out = '<figure class="diagram%s"><div class="diagram-frame">%s</div>%s</figure>' % (
            " wide" if wide else "", svg,
            "<figcaption>%s</figcaption>" % html.escape(caption) if caption else "")
        raw = nodes.raw("", out, format="html")
        parent = img.parent
        # an image alone in its paragraph (Markdown) or inside a reference: replace that container
        while isinstance(parent, (nodes.paragraph, nodes.reference)) and len(parent.children) == 1:
            img, parent = parent, parent.parent
        img.replace_self(raw)


def setup(app):
    app.connect("doctree-resolved", _inline_diagrams)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
