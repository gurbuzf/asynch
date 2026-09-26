# Sphinx configuration of the ASYNCH documentation (https://gurbuzf.github.io/asynch/).
#
# Build it locally:
#     pip install -r docs/requirements.txt        (and: sudo apt-get install doxygen, for the C API pages)
#     sphinx-build -b html docs docs/_build/html
#     then open docs/_build/html/index.html
#
# The pages are the guide (docs/guide/*.md, Markdown read by MyST), the reference manual (docs/*.rst), the Python
# API generated from the docstrings of python/asynch (autodoc), and the C API generated from the comments of the
# headers by Doxygen (breathe). GitHub Actions (.github/workflows/docs.yml) builds and publishes it on every push.
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "python"))     # autodoc imports asynch (the C library is not loaded)

# -- Project --------------------------------------------------------------------------------------------------------

project = "ASYNCH"
author = "Iowa Flood Center and contributors"
copyright = "2012-2026, " + author
with open(os.path.join(ROOT, "configure.ac")) as f:
    release = re.search(r"AC_INIT\(\[asynch\],\s*\[([^\]]+)\]", f.read()).group(1)
version = release
repository = "https://github.com/gurbuzf/asynch"
branch = "modernization"

# -- Extensions -----------------------------------------------------------------------------------------------------

extensions = [
    "myst_parser",                 # Markdown pages (the guide)
    "sphinx.ext.autodoc",          # Python API from docstrings
    "sphinx.ext.napoleon",         # NumPy-style docstring sections (Parameters, ...)
    "sphinx.ext.mathjax",
    "sphinx.ext.viewcode",         # links from the Python API to its source
    "sphinx_copybutton",           # a copy button on every code block
    "sphinx_design",               # cards and grids on the home page
    "sphinx.ext.autosectionlabel", # the reference manual links to sections by their title
]
autosectionlabel_maxdepth = 3

# Doxygen turns the comments of the C headers into XML, which breathe renders. Without Doxygen the C API pages show
# a note instead of failing the whole build.
HAVE_DOXYGEN = shutil.which("doxygen") is not None
if HAVE_DOXYGEN:
    extensions.append("breathe")
    breathe_projects = {"api": os.path.join(HERE, ".doxygen", "api"), "devel": os.path.join(HERE, ".doxygen", "devel")}
    breathe_default_project = "api"
    breathe_domain_by_extension = {"h": "c"}      # the headers are C, not C++
    for dox in ("api.dox", "devel.dox"):
        subprocess.run(["doxygen", dox], cwd=HERE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

source_suffix = {".rst": "restructuredtext", ".md": "markdown"}
root_doc = "index"
exclude_patterns = ["_build", ".doxygen", "Thumbs.db", ".DS_Store", "guide/README.md"]

myst_enable_extensions = ["colon_fence", "deflist", "dollarmath", "tasklist", "attrs_inline"]
myst_heading_anchors = 3           # links such as 01_setup.md#option-a-... work as on GitHub

autodoc_member_order = "bysource"
autodoc_default_options = {"members": True, "undoc-members": False, "show-inheritance": False}
autodoc_typehints = "none"
napoleon_numpy_docstring = True
napoleon_google_docstring = False

# several guide pages start with a level-2 heading after the title; the manual reuses some section titles (links go
# to the first one); its bibliography lists works not cited in the text
suppress_warnings = ["myst.header", "autosectionlabel.*", "ref.citation"]

# -- HTML -----------------------------------------------------------------------------------------------------------

html_theme = "furo"
html_title = "ASYNCH %s" % release
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_logo = "_static/logo.svg"
html_favicon = "_static/logo.svg"
html_show_sourcelink = False
html_theme_options = {
    "source_repository": repository,
    "source_branch": branch,
    "source_directory": "docs/",
    "light_css_variables": {"color-brand-primary": "#1f5fae", "color-brand-content": "#1f5fae"},
    "dark_css_variables": {"color-brand-primary": "#6ea8ec", "color-brand-content": "#6ea8ec"},
    "footer_icons": [{
        "name": "GitHub", "url": repository, "class": "",
        "html": '<svg stroke="currentColor" fill="currentColor" viewBox="0 0 16 16"><path fill-rule="evenodd" '
                'd="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01'
                '.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 '
                '1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02'
                '.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1'
                '.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93'
                '-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"></path></svg>',
    }],
}

# -- Adjustments of the Markdown sources ----------------------------------------------------------------------------

# The guide is also read on GitHub, where it links to files of the repository with relative paths. On the site those
# files are not pages: the links are pointed at the changelog page or at the file on GitHub.
REPO_LINK = re.compile(r"\]\((\.\./)+(?!docs/)([^)#\s]+)(#[^)\s]*)?\)")


def _rewrite_links(app, docname, source):
    if not docname.startswith("guide/"):
        return
    text = source[0].replace("](../../CHANGELOG.md)", "](../changelog.md)")

    def repl(m):
        path, anchor = m.group(2), m.group(3) or ""
        if path.endswith(".md") and not path.startswith(("src/", "tests/", "python/", "examples/", "tools/")):
            return m.group(0)
        return "](%s/blob/%s/%s%s)" % (repository, branch, path, anchor)
    source[0] = REPO_LINK.sub(repl, text)


def _no_doxygen_directives(app):
    """Without Doxygen, the breathe directives of c_api.rst become a note."""
    if HAVE_DOXYGEN:
        return
    import collections
    from docutils import nodes
    from docutils.parsers.rst import Directive, directives

    class Missing(Directive):
        required_arguments = 0
        optional_arguments = 10
        final_argument_whitespace = True
        has_content = True
        option_spec = collections.defaultdict(lambda: directives.unchanged)   # accept any option

        def run(self):
            return [nodes.note("", nodes.paragraph(text="(C reference of %s: built when Doxygen is installed.)"
                                                   % " ".join(self.arguments)))]

    for name in ("doxygenfunction", "doxygenstruct", "doxygentypedef", "doxygenfile", "doxygenenum", "doxygendefine"):
        app.add_directive(name, Missing)


def setup(app):
    app.connect("source-read", _rewrite_links)
    _no_doxygen_directives(app)
