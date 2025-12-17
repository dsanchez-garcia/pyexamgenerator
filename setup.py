from setuptools import setup, find_packages
import os
import re

# Función para leer la versión desde __init__.py sin importar el paquete
def get_version():
    version_file = os.path.join('pyexamgenerator', '__init__.py')
    with open(version_file, 'r', encoding='utf-8') as f:
        version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", f.read(), re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("No se puede encontrar la cadena de versión.")
# Para leer la descripción larga desde el archivo README.md
with open('README.md', 'r', encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='pyexamgenerator',
    version=get_version(),
    author='Daniel Sánchez-García',
    author_email='daniel.sanchezgarcia@uca.es',  # Opcional: añade tu email de contacto
    description='Una herramienta de escritorio para generar exámenes desde PDFs usando IA.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/dsanchez-garcia/pyexamgenerator',  # URL del repositorio de tu proyecto
    packages=find_packages(),
    install_requires=[
        'google-genai',
        'PyPDF2',
        'python-docx',
        'pandas',
        'openpyxl',
        'ttkwidgets',
        'importlib-metadata; python_version < "3.8"',
    ],
    entry_points={
        'console_scripts': [
            'pyexamgenerator=pyexamgenerator.main_app:main',
        ],
    },
    python_requires='>=3.8',  # Especifica la versión mínima de Python compatible
    keywords=['exam', 'generator', 'ai', 'gemini', 'pdf', 'moodle', 'quiz', 'education', 'test'],
    license='GPL-3.0-or-later',
    classifiers=[
        # Estado de desarrollo del paquete
        'Development Status :: 4 - Beta',

        # A quién va dirigido el paquete
        'Intended Audience :: Education',
        'Intended Audience :: Developers',

        # Tema del paquete
        'Topic :: Education',
        'Topic :: Text Processing',
        'Topic :: Utilities',

        # Versiones de Python soportadas
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',

        # Sistema operativo
        'Operating System :: OS Independent',
    ],
)