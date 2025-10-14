# conf.py

import os
import sys
# Añade la ruta raíz del proyecto para que Sphinx pueda encontrar tus módulos
sys.path.insert(0, os.path.abspath('../../'))

# Importa la versión desde tu paquete
from pyexamgenerator import __version__


# -- Project information -----------------------------------------------------
project = 'pyexamgenerator'
copyright = '2025, Daniel Sánchez-García'
author = 'Daniel Sánchez-García'


# La versión corta X.Y
version = '.'.join(__version__.split('.')[:2])
# La versión completa, incluyendo alpha/beta/rc tags
release = __version__

# -- General configuration ---------------------------------------------------
extensions = [
    'sphinx.ext.autodoc',      # Importa la documentación desde los docstrings
    'sphinx.ext.napoleon',     # Soporte para docstrings de estilo Google y NumPy
    'sphinx.ext.viewcode',     # Añade enlaces al código fuente
    'sphinx.ext.intersphinx',  # Enlaces a otra documentación
    'myst_parser',  # Construir markdown
]

templates_path = ['_templates']
exclude_patterns = []
language = 'es'

# -- Options for HTML output -------------------------------------------------
html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']