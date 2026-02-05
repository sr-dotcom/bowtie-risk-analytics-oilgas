"""Tests for manifest merge/append functionality."""
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile

from src.ingestion.manifests import (
    IncidentManifestRow,
    merge_incident_manifests,
    save_incident_manifest,
    load_incident_manifest,
)


class TestMergeKey:
    """Test merge key logic: (source, pdf_url) or fallback (source, incident_id)."""

    def test_dedupes_by_source_and_pdf_url(self):
        existing = [
            IncidentManifestRow(
                source="csb",
                incident_id="old-id",
                title="Old Title",
                detail_url="",
                pdf_url="https://csb.gov/report.pdf",
                pdf_path="csb/pdfs/report.pdf",
                downloaded=True,
            ),
        ]
        new = [
            IncidentManifestRow(
                source="csb",
                incident_id="new-id",  # Different incident_id
                title="New Title",
                detail_url="",
                pdf_url="https://csb.gov/report.pdf",  # Same pdf_url
                pdf_path="csb/pdfs/report.pdf",
                downloaded=False,
            ),
        ]

        merged = merge_incident_manifests(existing, new)

        assert len(merged) == 1
        # Winner should be existing (downloaded=True beats False)
        assert merged[0].downloaded is True

    def test_fallback_to_incident_id_when_pdf_url_empty(self):
        existing = [
            IncidentManifestRow(
                source="bsee",
                incident_id="same-id",
                title="Existing",
                detail_url="",
                pdf_url="",  # Empty pdf_url
                pdf_path="bsee/pdfs/same-id.pdf",
                downloaded=True,
            ),
        ]
        new = [
            IncidentManifestRow(
                source="bsee",
                incident_id="same-id",  # Same incident_id
                title="New",
                detail_url="",
                pdf_url="",  # Empty pdf_url
                pdf_path="bsee/pdfs/same-id.pdf",
                downloaded=False,
            ),
        ]

        merged = merge_incident_manifests(existing, new)

        assert len(merged) == 1
        assert merged[0].downloaded is True

    def test_different_sources_not_deduped(self):
        existing = [
            IncidentManifestRow(
                source="csb",
                incident_id="same-id",
                title="CSB",
                detail_url="",
                pdf_url="https://example.com/report.pdf",
                pdf_path="csb/pdfs/report.pdf",
            ),
        ]
        new = [
            IncidentManifestRow(
                source="bsee",  # Different source
                incident_id="same-id",
                title="BSEE",
                detail_url="",
                pdf_url="https://example.com/report.pdf",  # Same pdf_url
                pdf_path="bsee/pdfs/report.pdf",
            ),
        ]

        merged = merge_incident_manifests(existing, new)

        assert len(merged) == 2


class TestWinnerPriority:
    """Test conflict resolution priority rules."""

    def test_downloaded_true_beats_false(self):
        existing = [
            IncidentManifestRow(
                source="csb",
                incident_id="test",
                title="Existing",
                detail_url="",
                pdf_url="https://csb.gov/test.pdf",
                pdf_path="csb/pdfs/test.pdf",
                downloaded=False,
            ),
        ]
        new = [
            IncidentManifestRow(
                source="csb",
                incident_id="test",
                title="New",
                detail_url="",
                pdf_url="https://csb.gov/test.pdf",
                pdf_path="csb/pdfs/test.pdf",
                downloaded=True,
            ),
        ]

        merged = merge_incident_manifests(existing, new)

        assert merged[0].downloaded is True

    def test_newer_retrieved_at_beats_older(self):
        old_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
        new_time = datetime(2024, 6, 1, tzinfo=timezone.utc)

        existing = [
            IncidentManifestRow(
                source="csb",
                incident_id="test",
                title="Old",
                detail_url="",
                pdf_url="https://csb.gov/test.pdf",
                pdf_path="csb/pdfs/test.pdf",
                downloaded=True,
                retrieved_at=old_time,
            ),
        ]
        new = [
            IncidentManifestRow(
                source="csb",
                incident_id="test",
                title="New",
                detail_url="",
                pdf_url="https://csb.gov/test.pdf",
                pdf_path="csb/pdfs/test.pdf",
                downloaded=True,
                retrieved_at=new_time,
            ),
        ]

        merged = merge_incident_manifests(existing, new)

        assert merged[0].retrieved_at == new_time

    def test_sha256_present_beats_missing(self):
        existing = [
            IncidentManifestRow(
                source="csb",
                incident_id="test",
                title="No Hash",
                detail_url="",
                pdf_url="https://csb.gov/test.pdf",
                pdf_path="csb/pdfs/test.pdf",
                downloaded=True,
                sha256=None,
            ),
        ]
        new = [
            IncidentManifestRow(
                source="csb",
                incident_id="test",
                title="Has Hash",
                detail_url="",
                pdf_url="https://csb.gov/test.pdf",
                pdf_path="csb/pdfs/test.pdf",
                downloaded=True,
                sha256="abc123",
            ),
        ]

        merged = merge_incident_manifests(existing, new)

        assert merged[0].sha256 == "abc123"

    def test_larger_file_size_beats_smaller(self):
        existing = [
            IncidentManifestRow(
                source="csb",
                incident_id="test",
                title="Small",
                detail_url="",
                pdf_url="https://csb.gov/test.pdf",
                pdf_path="csb/pdfs/test.pdf",
                downloaded=True,
                sha256="abc",
                file_size_bytes=1000,
            ),
        ]
        new = [
            IncidentManifestRow(
                source="csb",
                incident_id="test",
                title="Large",
                detail_url="",
                pdf_url="https://csb.gov/test.pdf",
                pdf_path="csb/pdfs/test.pdf",
                downloaded=True,
                sha256="def",
                file_size_bytes=5000,
            ),
        ]

        merged = merge_incident_manifests(existing, new)

        assert merged[0].file_size_bytes == 5000

    def test_existing_wins_when_equal(self):
        existing = [
            IncidentManifestRow(
                source="csb",
                incident_id="test",
                title="Existing",
                detail_url="",
                pdf_url="https://csb.gov/test.pdf",
                pdf_path="csb/pdfs/test.pdf",
                downloaded=False,
            ),
        ]
        new = [
            IncidentManifestRow(
                source="csb",
                incident_id="test",
                title="New",
                detail_url="",
                pdf_url="https://csb.gov/test.pdf",
                pdf_path="csb/pdfs/test.pdf",
                downloaded=False,
            ),
        ]

        merged = merge_incident_manifests(existing, new)

        # Existing wins on tie
        assert merged[0].title == "Existing"


class TestEnrichFromLoser:
    """Test that winner is enriched with missing descriptive fields from loser."""

    def test_enriches_missing_title(self):
        existing = [
            IncidentManifestRow(
                source="csb",
                incident_id="test",
                title="",  # Empty
                detail_url="",
                pdf_url="https://csb.gov/test.pdf",
                pdf_path="csb/pdfs/test.pdf",
                downloaded=True,
            ),
        ]
        new = [
            IncidentManifestRow(
                source="csb",
                incident_id="test",
                title="Good Title",
                detail_url="",
                pdf_url="https://csb.gov/test.pdf",
                pdf_path="csb/pdfs/test.pdf",
                downloaded=False,
            ),
        ]

        merged = merge_incident_manifests(existing, new)

        # Winner is existing (downloaded=True), but title enriched from new
        assert merged[0].downloaded is True
        assert merged[0].title == "Good Title"

    def test_enriches_missing_dates(self):
        existing = [
            IncidentManifestRow(
                source="csb",
                incident_id="test",
                title="Test",
                date_occurred=None,
                date_report_released=None,
                detail_url="",
                pdf_url="https://csb.gov/test.pdf",
                pdf_path="csb/pdfs/test.pdf",
                downloaded=True,
            ),
        ]
        new = [
            IncidentManifestRow(
                source="csb",
                incident_id="test",
                title="Test",
                date_occurred="2024-01-15",
                date_report_released="2024-06-01",
                detail_url="",
                pdf_url="https://csb.gov/test.pdf",
                pdf_path="csb/pdfs/test.pdf",
                downloaded=False,
            ),
        ]

        merged = merge_incident_manifests(existing, new)

        assert merged[0].downloaded is True
        assert merged[0].date_occurred == "2024-01-15"
        assert merged[0].date_report_released == "2024-06-01"

    def test_does_not_overwrite_existing_descriptive_fields(self):
        existing = [
            IncidentManifestRow(
                source="csb",
                incident_id="test",
                title="Original Title",
                detail_url="https://original.com",
                pdf_url="https://csb.gov/test.pdf",
                pdf_path="csb/pdfs/test.pdf",
                downloaded=True,
            ),
        ]
        new = [
            IncidentManifestRow(
                source="csb",
                incident_id="test",
                title="New Title",
                detail_url="https://new.com",
                pdf_url="https://csb.gov/test.pdf",
                pdf_path="csb/pdfs/test.pdf",
                downloaded=False,
            ),
        ]

        merged = merge_incident_manifests(existing, new)

        # Winner's existing values preserved
        assert merged[0].title == "Original Title"
        assert merged[0].detail_url == "https://original.com"

    def test_does_not_enrich_state_fields(self):
        existing = [
            IncidentManifestRow(
                source="csb",
                incident_id="test",
                title="Test",
                detail_url="",
                pdf_url="https://csb.gov/test.pdf",
                pdf_path="csb/pdfs/test.pdf",
                downloaded=True,
                http_status=200,
                sha256=None,  # Missing
            ),
        ]
        new = [
            IncidentManifestRow(
                source="csb",
                incident_id="test",
                title="Test",
                detail_url="",
                pdf_url="https://csb.gov/test.pdf",
                pdf_path="csb/pdfs/test.pdf",
                downloaded=False,
                http_status=404,
                sha256="should-not-be-copied",
            ),
        ]

        merged = merge_incident_manifests(existing, new)

        # Winner is existing (downloaded=True)
        # State fields NOT enriched from loser
        assert merged[0].http_status == 200
        assert merged[0].sha256 is None


class TestMergeIntegration:
    """Integration tests with file I/O."""

    def test_append_mode_preserves_existing_downloaded(self):
        """Key test from requirements: append mode preserves downloaded=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "manifest.csv"

            # Create existing manifest with downloaded=True
            existing = [
                IncidentManifestRow(
                    source="csb",
                    incident_id="test-1",
                    title="Existing",
                    detail_url="https://csb.gov/test",
                    pdf_url="https://csb.gov/test.pdf",
                    pdf_path="csb/pdfs/test.pdf",
                    downloaded=True,
                    http_status=200,
                    sha256="existing-hash",
                ),
            ]
            save_incident_manifest(existing, manifest_path)

            # Simulate new discovery returning same pdf_url but downloaded=False
            new = [
                IncidentManifestRow(
                    source="csb",
                    incident_id="test-1",
                    title="New Discovery",
                    detail_url="https://csb.gov/test",
                    pdf_url="https://csb.gov/test.pdf",
                    pdf_path="csb/pdfs/test.pdf",
                    downloaded=False,
                ),
            ]

            # Load existing and merge
            loaded = load_incident_manifest(manifest_path)
            merged = merge_incident_manifests(loaded, new)

            # Save merged
            save_incident_manifest(merged, manifest_path)

            # Reload and verify
            final = load_incident_manifest(manifest_path)

            assert len(final) == 1
            assert final[0].downloaded is True
            assert final[0].sha256 == "existing-hash"
