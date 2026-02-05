import pytest
from unittest.mock import patch, Mock
from pathlib import Path
import tempfile
import sys

from src.pipeline import main, cmd_acquire, cmd_extract_text


class TestCliParsing:
    def test_no_args_runs_default(self):
        """Running without args should run the original process behavior."""
        with patch("src.pipeline.process_raw_files") as mock_process:
            with patch("sys.argv", ["pipeline"]):
                main()
                mock_process.assert_called_once()

    def test_process_subcommand(self):
        """'process' subcommand runs original behavior."""
        with patch("src.pipeline.process_raw_files") as mock_process:
            with patch("sys.argv", ["pipeline", "process"]):
                main()
                mock_process.assert_called_once()

    def test_acquire_subcommand_parses_args(self):
        """'acquire' subcommand parses limits and flags."""
        with patch("src.pipeline.cmd_acquire") as mock_acquire:
            with patch(
                "sys.argv",
                [
                    "pipeline",
                    "acquire",
                    "--csb-limit",
                    "10",
                    "--bsee-limit",
                    "5",
                    "--download",
                ],
            ):
                main()
                mock_acquire.assert_called_once()
                args = mock_acquire.call_args[0][0]
                assert args.csb_limit == 10
                assert args.bsee_limit == 5
                assert args.download is True

    def test_extract_text_subcommand_parses_args(self):
        """'extract-text' subcommand parses manifest path."""
        with patch("src.pipeline.cmd_extract_text") as mock_extract:
            with patch(
                "sys.argv",
                [
                    "pipeline",
                    "extract-text",
                    "--manifest",
                    "custom/path.csv",
                    "--out",
                    "custom/text.csv",
                ],
            ):
                main()
                mock_extract.assert_called_once()
                args = mock_extract.call_args[0][0]
                assert args.manifest == "custom/path.csv"
                assert args.out == "custom/text.csv"


class TestCmdAcquire:
    def test_acquire_discovers_and_saves(self):
        """acquire command discovers incidents and saves manifest."""
        from src.ingestion.manifests import IncidentManifestRow

        mock_row = IncidentManifestRow(
            source="csb",
            incident_id="test-1",
            title="Test",
            detail_url="https://csb.gov/test",
            pdf_url="https://csb.gov/test.pdf",
            pdf_path="csb/pdfs/test.pdf",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "manifest.csv"

            mock_args = Mock()
            mock_args.csb_limit = 1
            mock_args.bsee_limit = 0
            mock_args.out = str(out_path)
            mock_args.download = False
            mock_args.timeout = 30
            mock_args.append = False

            with patch(
                "src.pipeline.discover_csb_incidents", return_value=iter([mock_row])
            ):
                with patch("src.pipeline.discover_bsee_incidents", return_value=iter([])):
                    cmd_acquire(mock_args)

            assert out_path.exists()

    def test_acquire_append_preserves_downloaded(self):
        """--append mode preserves existing downloaded=True row."""
        from src.ingestion.manifests import (
            IncidentManifestRow,
            save_incident_manifest,
            load_incident_manifest,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "manifest.csv"

            # Create existing manifest with downloaded=True
            existing_row = IncidentManifestRow(
                source="csb",
                incident_id="test-1",
                title="Existing",
                detail_url="https://csb.gov/test",
                pdf_url="https://csb.gov/test.pdf",
                pdf_path="csb/pdfs/test.pdf",
                downloaded=True,
                http_status=200,
                sha256="existing-hash",
            )
            save_incident_manifest([existing_row], out_path)

            # New discovery returns same pdf_url but downloaded=False
            new_row = IncidentManifestRow(
                source="csb",
                incident_id="test-1",
                title="New Discovery",
                detail_url="https://csb.gov/test",
                pdf_url="https://csb.gov/test.pdf",
                pdf_path="csb/pdfs/test.pdf",
                downloaded=False,
            )

            mock_args = Mock()
            mock_args.csb_limit = 1
            mock_args.bsee_limit = 0
            mock_args.out = str(out_path)
            mock_args.download = False
            mock_args.timeout = 30
            mock_args.append = True

            with patch(
                "src.pipeline.discover_csb_incidents", return_value=iter([new_row])
            ):
                with patch("src.pipeline.discover_bsee_incidents", return_value=iter([])):
                    cmd_acquire(mock_args)

            # Verify: still exactly 1 row, still downloaded=True
            final = load_incident_manifest(out_path)
            assert len(final) == 1
            assert final[0].downloaded is True
            assert final[0].sha256 == "existing-hash"

    def test_acquire_append_adds_new_incidents(self):
        """--append mode adds new incidents to existing manifest."""
        from src.ingestion.manifests import (
            IncidentManifestRow,
            save_incident_manifest,
            load_incident_manifest,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "manifest.csv"

            # Create existing manifest
            existing_row = IncidentManifestRow(
                source="csb",
                incident_id="existing-1",
                title="Existing",
                detail_url="",
                pdf_url="https://csb.gov/existing.pdf",
                pdf_path="csb/pdfs/existing.pdf",
                downloaded=True,
            )
            save_incident_manifest([existing_row], out_path)

            # New discovery returns different incident
            new_row = IncidentManifestRow(
                source="csb",
                incident_id="new-1",
                title="New",
                detail_url="",
                pdf_url="https://csb.gov/new.pdf",
                pdf_path="csb/pdfs/new.pdf",
                downloaded=False,
            )

            mock_args = Mock()
            mock_args.csb_limit = 1
            mock_args.bsee_limit = 0
            mock_args.out = str(out_path)
            mock_args.download = False
            mock_args.timeout = 30
            mock_args.append = True

            with patch(
                "src.pipeline.discover_csb_incidents", return_value=iter([new_row])
            ):
                with patch("src.pipeline.discover_bsee_incidents", return_value=iter([])):
                    cmd_acquire(mock_args)

            # Verify: now has 2 rows
            final = load_incident_manifest(out_path)
            assert len(final) == 2


class TestCmdExtractText:
    def test_extract_text_processes_manifest(self):
        """extract-text command reads manifest and extracts."""
        from src.ingestion.manifests import (
            IncidentManifestRow,
            TextManifestRow,
            save_incident_manifest,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "incidents.csv"
            out_path = Path(tmpdir) / "text.csv"

            # Create a manifest with one downloaded row
            rows = [
                IncidentManifestRow(
                    source="csb",
                    incident_id="test-1",
                    title="Test",
                    detail_url="",
                    pdf_url="",
                    pdf_path="csb/pdfs/test.pdf",
                    downloaded=True,
                )
            ]
            save_incident_manifest(rows, manifest_path)

            mock_args = Mock()
            mock_args.manifest = str(manifest_path)
            mock_args.out = str(out_path)

            mock_text_row = TextManifestRow(
                source="csb",
                incident_id="test-1",
                pdf_path="csb/pdfs/test.pdf",
                text_path="csb/text/test.txt",
                extracted=True,
            )

            with patch(
                "src.pipeline.process_incident_manifest", return_value=[mock_text_row]
            ):
                cmd_extract_text(mock_args)

            assert out_path.exists()
