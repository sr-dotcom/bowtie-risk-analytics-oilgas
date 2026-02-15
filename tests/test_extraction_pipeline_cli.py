"""Test that extract-qc subcommand is registered in pipeline CLI."""
import subprocess
import sys

import pytest


class TestExtractQCSubcommand:
    def test_help_shows_extract_qc(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "src.pipeline", "extract-qc", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "--pdf-dir" in result.stdout
        assert "--output-dir" in result.stdout
        assert "--force" in result.stdout
