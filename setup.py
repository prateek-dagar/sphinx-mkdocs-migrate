from setuptools import setup, find_packages
from pathlib import Path

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8") if (this_directory / "README.md").exists() else ""

setup(
    name="sphinx-mkdocs-migrate",
    version="0.1.0b1",
    description="Deterministic, evidence-driven analyzer and migration engine from MkDocs to Sphinx + MyST",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Prateek Dagar",
    author_email="prateek0508dagar@gmail.com",
    url="https://github.com/prateek-dagar/sphinx-mkdocs-migrate",
    project_urls={
        "Homepage": "https://github.com/prateek-dagar/sphinx-mkdocs-migrate",
        "Documentation": "https://github.com/prateek-dagar/sphinx-mkdocs-migrate#readme",
        "Repository": "https://github.com/prateek-dagar/sphinx-mkdocs-migrate.git",
        "Issues": "https://github.com/prateek-dagar/sphinx-mkdocs-migrate/issues",
    },
    license="Apache-2.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.10",
    install_requires=[
        "pyyaml>=6.0",
        "rich>=13.0",
        "pydantic>=2.0",
        "click>=8.1",
        "markdown-it-py>=3.0.0",
        "mdit-py-plugins>=0.4.0",
        "Sphinx>=7.0.0",
        "myst-parser>=2.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "build>=1.0.0",
            "twine>=4.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "sphinx-migrate=sphinx_mkdocs_migrate.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Documentation",
        "Topic :: Software Development :: Documentation",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    keywords="sphinx mkdocs migration myst-parser documentation autodoc",
)
