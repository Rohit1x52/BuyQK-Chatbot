"""Pytest bootstrap for repository-level test configuration."""

from pathlib import Path

from dotenv import load_dotenv


load_dotenv(
    dotenv_path=Path(__file__).resolve().parent / ".env",
    override=False,
)
