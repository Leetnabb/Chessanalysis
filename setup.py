from setuptools import setup, find_packages

setup(
    name="chess-db",
    version="1.0.0",
    description="Chess PGN Database - Import, search, and analyze chess games",
    packages=find_packages(),
    python_requires=">=3.10",
    entry_points={
        "console_scripts": [
            "chess-db=chess_db.cli:main",
        ],
    },
)
