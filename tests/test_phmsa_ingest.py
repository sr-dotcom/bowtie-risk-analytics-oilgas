"""Tests for PHMSA bulk CSV ingest skeleton. All offline."""
import csv
import logging
from pathlib import Path

import pytest


class TestPhmsaIngestSkeleton:
    def test_skeleton_warns_on_missing_csv(self, tmp_path: Path, caplog) -> None:
        from src.ingestion.sources.phmsa_ingest import ingest_phmsa_csv
        manifest_path = tmp_path / "manifest.csv"
        missing_csv = tmp_path / "does_not_exist.csv"
        with caplog.at_level(logging.WARNING):
            rows = ingest_phmsa_csv(
                csv_path=missing_csv,
                output_dir=tmp_path / "out",
                manifest_path=manifest_path,
            )
        assert rows == []
        assert "not found" in caplog.text.lower() or "does not exist" in caplog.text.lower()

    def test_skeleton_inspects_headers(self, tmp_path: Path, caplog) -> None:
        from src.ingestion.sources.phmsa_ingest import ingest_phmsa_csv
        csv_path = tmp_path / "incidents.csv"
        csv_path.write_text(
            "REPORT_NUMBER,INCIDENT_DATE,NARRATIVE,CITY,STATE\n"
            "RPT-001,2024-01-15,A leak occurred,Houston,TX\n"
        )
        manifest_path = tmp_path / "manifest.csv"
        with caplog.at_level(logging.INFO):
            rows = ingest_phmsa_csv(
                csv_path=csv_path,
                output_dir=tmp_path / "out",
                manifest_path=manifest_path,
            )
        assert "REPORT_NUMBER" in caplog.text or "report_number" in caplog.text.lower()
        assert "mapping" in caplog.text.lower() or "recognized" in caplog.text.lower()

    def test_skeleton_warns_unknown_headers(self, tmp_path: Path, caplog) -> None:
        from src.ingestion.sources.phmsa_ingest import ingest_phmsa_csv
        csv_path = tmp_path / "weird.csv"
        csv_path.write_text("FOO,BAR,BAZ\nval1,val2,val3\n")
        manifest_path = tmp_path / "manifest.csv"
        with caplog.at_level(logging.WARNING):
            rows = ingest_phmsa_csv(
                csv_path=csv_path,
                output_dir=tmp_path / "out",
                manifest_path=manifest_path,
            )
        assert rows == []
        assert "mapping requires real csv" in caplog.text.lower() or "unrecognized" in caplog.text.lower()

    def test_manifest_schema(self, tmp_path: Path) -> None:
        from src.ingestion.sources.phmsa_ingest import PHMSA_MANIFEST_COLUMNS
        required = {"doc_id", "incident_id", "json_path", "valid", "provider", "error", "created_at"}
        assert required.issubset(set(PHMSA_MANIFEST_COLUMNS))
