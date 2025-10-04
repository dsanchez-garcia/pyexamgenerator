from setuptools import setup, find_packages

# Para leer la descripción larga desde el archivo README.md
with open('README.md', 'r', encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='examgenerator',
    version='0.1.0',
    author='Daniel Sánchez-García',
    author_email='daniel.sanchezgarcia@uca.es',  # Opcional: añade tu email de contacto
    description='Una herramienta de escritorio para generar exámenes desde PDFs usando IA.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/dsanchez-garcia/examgenerator',  # URL del repositorio de tu proyecto
    packages=find_packages(),
    install_requires=[
        'google-generativeai',
        'PyPDF2',
        'python-docx',
        'pandas',
        'openpyxl',
        'ttkwidgets',
        'importlib-metadata; python_version < "3.8"',
    ],
    entry_points={
        'console_scripts': [
            'examgenerator=examgenerator.main_app:main',
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

        # Licencia (debe coincidir con el campo 'license')
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',

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