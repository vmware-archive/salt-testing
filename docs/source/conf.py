# -*- coding: utf-8 -*-

# pylint: disable=invalid-name,missing-docstring
import os
import sys
from datetime import datetime


# -- General configuration ------------------------------------------------

# ----- Mocked Imports ---------------------------------------------------------------------------------------------->

# pylint: disable=R0903
class Mock(object):
    '''
    Mock out specified imports

    This allows autodoc to do its thing without having oodles of req'd
    installed libs. This doesn't work with ``import *`` imports.

    http://read-the-docs.readthedocs.org/en/latest/faq.html#i-get-import-errors-on-libraries-that-depend-on-c-modules
    '''
    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, *args, **kwargs):
        ret = Mock()
        # If mocked function is used as a decorator, expose decorated function.
        # if args and callable(args[-1]):
        #     functools.update_wrapper(ret, args[0])
        return ret

    @classmethod
    def __getattr__(cls, name):
        if name in ('__file__', '__path__'):
            return '/dev/null'
        else:
            return Mock()
# pylint: enable=R0903

mock_modules = [
    'pep8',
    'yaml',
    'pylint',
    'pylint.interfaces',
    'pylint.checkers',
    'pylint.checkers.utils',
    'pylint.__pkginfo__',
    'astroid',
    'logilab',
    'logilab.astng',
    'cherrypy',
    'cherrypy.lib',
    'cherrypy.lib.cpstats'
]

for mod_name in mock_modules:
    sys.modules[mod_name] = Mock()
# <---- Mocked Imports -----------------------------------------------------------------------------------------------

# ----- PYTHONPATH Tweaks ------------------------------------------------------------------------------------------->
try:
    docs_basepath = os.path.abspath(os.path.dirname(__file__))
except NameError:
    # sphinx-intl and six execute some code which will raise this NameError
    # assume we're in the doc/ directory
    docs_basepath = os.path.abspath(os.path.dirname('.'))

addtl_paths = (
    os.path.dirname(os.pardir),           # salt testing itself (for autodoc)
    os.path.join(docs_basepath, '_ext'),  # custom Sphinx extensions
)

for path in addtl_paths:
    sys.path.insert(0, os.path.abspath(os.path.join(docs_basepath, path)))


# We're now able to import salt-testing
import salttesting.version
# <---- PYTHONPATH Tweaks --------------------------------------------------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'saltconf',
    'sphinx.ext.autodoc',
    'sphinx.ext.doctest',
    'sphinx.ext.intersphinx',
    'sphinx.ext.todo',
    'sphinx.ext.coverage',
    'sphinx.ext.viewcode',
]

try:
    import sphinxcontrib.spelling  # pylint: disable=import-error
except ImportError:
    pass
else:
    extensions += ['sphinxcontrib.spelling']

try:
    import sphinxcontrib.email  # pylint: disable=import-error
except ImportError:
    pass
else:
    extensions += ['sphinxcontrib.email']

autosummary_generate = True

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix of source filenames.
source_suffix = '.rst'

# The encoding of source files.
source_encoding = 'utf-8-sig'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = u'Salt Testing'
copyright = u'{0}, Pedro Algarvio'.format(datetime.utcnow().strftime('%Y'))

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = salttesting.version.__version__
# The full version, including alpha/beta/rc tags.
release = version

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = []

# If true, '()' will be appended to :func: etc. cross-reference text.
add_function_parentheses = True

# If true, the current module name will be prepended to all description
# unit titles (such as .. function::).
add_module_names = False

# If true, sectionauthor and moduleauthor directives will be shown in the
# output. They are ignored by default.
show_authors = False

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# A list of ignored prefixes for module index sorting.
modindex_common_prefix = ['salttesting.']

# If true, keep warnings as "system message" paragraphs in the built documents.
#keep_warnings = False


# -- Options for HTML output ----------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
html_theme = 'saltstack'

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
#html_theme_options = {}

# Add any paths that contain custom themes here, relative to this directory.
html_theme_path = ['_themes']

# The name for this set of Sphinx documents.  If None, it defaults to
# "<project> v<release> documentation".
html_title = None

# A shorter title for the navigation bar.  Default is the same as html_title.
html_short_title = 'Salt Testing'

# The name of an image file (relative to this directory) to place at the top
# of the sidebar.
html_logo = None  # Specified in layout.html

# The name of an image file (within the static path) to use as favicon of the
# docs.  This file should be a Windows icon file (.ico) being 16x16 or 32x32
# pixels large.
html_favicon = 'favicon.ico'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

# Add any extra paths that contain custom files (such as robots.txt or
# .htaccess) here, relative to this directory. These files are copied
# directly to the root of the documentation.
#html_extra_path = []

# If not '', a 'Last updated on:' timestamp is inserted at every page bottom,
# using the given strftime format.
html_last_updated_fmt = '%b %d, %Y'

# If true, SmartyPants will be used to convert quotes and dashes to
# typographically correct entities.
# html_use_smartypants = True

html_default_sidebars = [
    'searchbox.html',
#    'version.html',
    'localtoc.html',
#    'relations.html',
#    'sourcelink.html',
    'saltstack.html',
]

html_context = {
    'html_default_sidebars': html_default_sidebars,
    'github_base': 'https://github.com/saltstack/salt-testing',
    'github_issues': 'https://github.com/saltstack/salt-testing/issues',
    'github_downloads': 'https://github.com/saltstack/salt-testing/downloads',
}

# Custom sidebar templates, maps document names to template names.
#html_sidebars = {}

# Additional templates that should be rendered to pages, maps page names to
# template names.
html_additional_pages = {
    '404': '404.html'
}

# If false, no index is generated.
html_use_index = True

# If true, links to the reST sources are added to the pages.
html_show_sourcelink = False

# If true, "Created using Sphinx" is shown in the HTML footer. Default is True.
html_show_sphinx = True

# If true, "(C) Copyright ..." is shown in the HTML footer. Default is True.
html_show_copyright = True

# If true, an OpenSearch description file will be output, and all pages will
# contain a <link> tag referring to it.  The value of this option must be the
# base URL from which the finished HTML is served.
#html_use_opensearch = ''

# Output file base name for HTML help builder.
htmlhelp_basename = 'SaltTestingDoc'


# -- Options for LaTeX output ---------------------------------------------

latex_elements = {
# The paper size ('letterpaper' or 'a4paper').
#'papersize': 'letterpaper',

# The font size ('10pt', '11pt' or '12pt').
#'pointsize': '10pt',

# Additional stuff for the LaTeX preamble.
#'preamble': '',
}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title,
#  author, documentclass [howto, manual, or own class]).
latex_documents = [
  ('index', 'SaltTesting.tex', u'Salt Testing Documentation',
   u'Pedro Algarvio', 'manual'),
]

# The name of an image file (relative to this directory) to place at the top of
# the title page.
#latex_logo = None

# For "manual" documents, if this is true, then toplevel headings are parts,
# not chapters.
#latex_use_parts = False

# If true, show page references after internal links.
#latex_show_pagerefs = False

# If true, show URL addresses after external links.
#latex_show_urls = False

# Documents to append as an appendix to all manuals.
#latex_appendices = []

# If false, no module index is generated.
#latex_domain_indices = True


# -- Options for manual page output ---------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [
    ('index', 'salttesting', u'Salt Testing Documentation',
     [u'Pedro Algarvio'], 1)
]

# If true, show URL addresses after external links.
#man_show_urls = False


# -- Options for Texinfo output -------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
  ('index', 'Salt Testing', u'Salt Testing Documentation',
   u'Pedro Algarvio', 'Salt Testing', 'SaltStack\' Testing Companion Project.',
   'Miscellaneous'),
]

# Documents to append as an appendix to all manuals.
#texinfo_appendices = []

# If false, no module index is generated.
#texinfo_domain_indices = True

# How to display URL addresses: 'footnote', 'no', or 'inline'.
#texinfo_show_urls = 'footnote'

# If true, do not generate a @detailmenu in the "Top" node's menu.
#texinfo_no_detailmenu = False


# Example configuration for intersphinx: refer to the Python standard library.
intersphinx_mapping = {
    'python2': ('http://docs.python.org/2', None),
    'python3': ('http://docs.python.org/3', None),
       'salt': ('https://docs.saltstack.com', None),
       'mock': ('http://www.voidspace.org.uk/python/mock/', None)
}
