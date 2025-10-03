from setuptools import setup, find_packages

setup(
    name='examgenerator',
    version='0.1.15',
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
            'examgenerator=examgenerator.main_app:main',  # 'mi_app' será el comando, 'tu_paquete.main_app' es el módulo, 'main' es la función a ejecutar
        ],
    },
)