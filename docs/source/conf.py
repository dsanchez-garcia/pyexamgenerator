# conf.py

import os
import sys
# Añade la ruta raíz del proyecto para que Sphinx pueda encontrar tus módulos
sys.path.insert(0, os.path.abspath('../../'))

# -- Project information -----------------------------------------------------
project = 'examgenerator'
copyright = '2025, Daniel Sánchez-García'
author = 'Daniel Sánchez-García'

# Intenta obtener la versión del paquete para mostrarla en la documentación
try:
    from examgenerator import __version__
    release = __version__
except ImportError:
    # Si no se puede importar, usa la versión de setup.py o una por defecto
    try:
        import pkg_resources
        release = pkg_resources.get_distribution('examgenerator').version
    except:
        # Como último recurso
        release = '0.1.8'


# -- General configuration ---------------------------------------------------
extensions = [
    'sphinx.ext.autodoc',      # Importa la documentación desde los docstrings
    'sphinx.ext.napoleon',     # Soporte para docstrings de estilo Google y NumPy
    'sphinx.ext.viewcode',     # Añade enlaces al código fuente
    'sphinx.ext.intersphinx',  # Enlaces a otra documentación
]

templates_path = ['_templates']
exclude_patterns = []
language = 'es'

# -- Options for HTML output -------------------------------------------------
html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']