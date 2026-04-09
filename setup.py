"""Setup script for ECTHR Translator."""

from setuptools import setup, find_packages

setup(
    name="ecthr-translator",
    version="0.1.0",
    description="Translation service for European Court of Human Rights legal documents",
    author="ECTHR Translator Team",
    packages=find_packages(),
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "ecthr-translator=src.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Legal Industry",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
