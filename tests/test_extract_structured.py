import json
import pytest
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from src.ingestion.structured import (
    compute_quality_gate,
    extract_structured,
    generate_run_report,
    load_structured_manifest,
    merge_structured_manifests,
    save_structured_manifest,
    StructuredManifestRow,
    _parse_llm_json,
)
from src.llm.stub import StubProvider


class TestParseJson:
    def test_plain_json(self):
        result = _parse_llm_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_markdown_fenced_json(self):
        raw = '```json\n{"key": "value"}\n```'
        result = _parse_llm_json(raw)
        assert result == {"key": "value"}

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _parse_llm_json("not json at all")


class TestExtractStructured:
    def test_stub_extraction_produces_json(self):
        provider = StubProvider()
        with tempfile.TemporaryDirectory() as tmpdir:
            text_dir = Path(tmpdir) / "text"
            out_dir = Path(tmpdir) / "out"
            text_dir.mkdir()

            # Write a sample text file
            (text_dir / "test-001.txt").write_text("Sample incident narrative about a gas release.")

            rows = extract_structured(text_dir, out_dir, provider, "stub")

            assert len(rows) == 1
            assert rows[0].extracted is True
            assert rows[0].incident_id == "test-001"

            # Check JSON was written under provider subdir
            json_path = out_dir / "stub" / "test-001.json"
            assert json_path.exists()
            data = json.loads(json_path.read_text())
            assert data["incident_id"] == "test-001"

    def test_empty_text_file_skipped(self):
        provider = StubProvider()
        with tempfile.TemporaryDirectory() as tmpdir:
            text_dir = Path(tmpdir) / "text"
            out_dir = Path(tmpdir) / "out"
            text_dir.mkdir()

            (text_dir / "empty.txt").write_text("")

            rows = extract_structured(text_dir, out_dir, provider, "stub")
            assert len(rows) == 1
            assert rows[0].extracted is False
            assert rows[0].error == "Empty text file"

    def test_no_files_returns_empty(self):
        provider = StubProvider()
        with tempfile.TemporaryDirectory() as tmpdir:
            text_dir = Path(tmpdir) / "text"
            out_dir = Path(tmpdir) / "out"
            text_dir.mkdir()

            rows = extract_structured(text_dir, out_dir, provider, "stub")
            assert rows == []

    def test_multiple_files_processed(self):
        provider = StubProvider()
        with tempfile.TemporaryDirectory() as tmpdir:
            text_dir = Path(tmpdir) / "text"
            out_dir = Path(tmpdir) / "out"
            text_dir.mkdir()

            (text_dir / "inc-001.txt").write_text("Incident one narrative.")
            (text_dir / "inc-002.txt").write_text("Incident two narrative.")

            rows = extract_structured(text_dir, out_dir, provider, "stub")
            assert len(rows) == 2
            assert all(r.extracted for r in rows)


class TestManifestPersistence:
    def _make_row(self, incident_id: str) -> StructuredManifestRow:
        return StructuredManifestRow(
            incident_id=incident_id,
            source_text_path=f"text/{incident_id}.txt",
            output_json_path=f"out/{incident_id}.json",
            provider="stub",
            model=None,
            extracted=True,
            extracted_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            valid=True,
        )

    def test_save_and_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "manifest.csv"
            original = [self._make_row("INC-001"), self._make_row("INC-002")]

            save_structured_manifest(original, manifest_path)
            loaded = load_structured_manifest(manifest_path)

            assert len(loaded) == 2
            assert loaded[0].incident_id == "INC-001"
            assert loaded[1].incident_id == "INC-002"
            assert loaded[0].extracted is True
            assert loaded[0].valid is True

    def test_load_nonexistent_returns_empty(self):
        loaded = load_structured_manifest(Path("/tmp/does_not_exist.csv"))
        assert loaded == []

    def test_merge_upserts_by_composite_key(self):
        old_row = self._make_row("INC-001")
        updated_row = self._make_row("INC-001")
        updated_row.valid = False
        updated_row.validation_errors = "some error"
        new_row = self._make_row("INC-002")

        merged = merge_structured_manifests([old_row], [updated_row, new_row])

        assert len(merged) == 2
        by_id = {r.incident_id: r for r in merged}
        assert by_id["INC-001"].valid is False  # new wins
        assert by_id["INC-001"].validation_errors == "some error"
        assert by_id["INC-002"].extracted is True

    def test_merge_preserves_different_providers_same_incident(self):
        """Same incident_id with different providers must coexist."""
        openai_row = self._make_row("INC-001")
        openai_row.provider = "openai"
        openai_row.model = "gpt-4o"
        openai_row.output_json_path = "out/openai/INC-001.json"

        anthropic_row = self._make_row("INC-001")
        anthropic_row.provider = "anthropic"
        anthropic_row.model = "claude-sonnet-4-5-20250929"
        anthropic_row.output_json_path = "out/anthropic/INC-001.json"

        merged = merge_structured_manifests([openai_row], [anthropic_row])

        assert len(merged) == 2
        providers = {r.provider for r in merged}
        assert providers == {"openai", "anthropic"}

    def test_output_json_path_includes_provider(self):
        """extract_structured must write JSON under out_dir/<provider>/."""
        provider = StubProvider()
        with tempfile.TemporaryDirectory() as tmpdir:
            text_dir = Path(tmpdir) / "text"
            out_dir = Path(tmpdir) / "out"
            text_dir.mkdir()
            (text_dir / "INC-042.txt").write_text("Some narrative.")

            rows = extract_structured(text_dir, out_dir, provider, "stub")

            assert len(rows) == 1
            assert "/stub/" in rows[0].output_json_path or "\\stub\\" in rows[0].output_json_path
            assert (out_dir / "stub" / "INC-042.json").exists()

    def test_extraction_preserves_prior_manifest_rows(self):
        """Regression: running extraction must not drop prior manifest rows."""
        provider = StubProvider()
        with tempfile.TemporaryDirectory() as tmpdir:
            text_dir = Path(tmpdir) / "text"
            out_dir = Path(tmpdir) / "out"
            manifest_path = Path(tmpdir) / "manifest.csv"
            text_dir.mkdir()

            # Seed manifest with a pre-existing row
            prior_row = self._make_row("PRIOR-001")
            save_structured_manifest([prior_row], manifest_path)

            # Create a new text file for extraction
            (text_dir / "NEW-001.txt").write_text("A new incident narrative.")

            # Run extraction → returns only NEW-001
            new_rows = extract_structured(text_dir, out_dir, provider, "stub")

            # Simulate what pipeline does: load + merge + save
            existing = load_structured_manifest(manifest_path)
            merged = merge_structured_manifests(existing, new_rows)
            save_structured_manifest(merged, manifest_path)

            # Reload and verify both rows survive
            final = load_structured_manifest(manifest_path)
            ids = {r.incident_id for r in final}
            assert "PRIOR-001" in ids, "Prior row was dropped!"
            assert "NEW-001" in ids, "New row was not added!"
            assert len(final) == 2

    def test_raw_response_path_per_provider(self):
        """raw_response_path must contain /raw/<provider>/ with correct separators."""
        provider = StubProvider()
        with tempfile.TemporaryDirectory() as tmpdir:
            text_dir = Path(tmpdir) / "text"
            out_dir = Path(tmpdir) / "out"
            text_dir.mkdir()
            (text_dir / "INC-099.txt").write_text("Some narrative.")

            for pname in ("stub", "anthropic", "openai"):
                rows = extract_structured(text_dir, out_dir, provider, pname)
                assert len(rows) == 1
                rp = rows[0].raw_response_path
                assert rp is not None
                # Path must contain /raw/<provider>/ (or backslash on Windows)
                assert f"raw/{pname}/" in rp.replace("\\", "/"), (
                    f"Expected 'raw/{pname}/' in {rp}"
                )
                assert Path(rp).exists()


class TestParseRetryOnFailure:
    """JSON parse retry re-prompts the provider once on failure."""

    def test_retry_on_bad_json_then_good(self):
        """Provider returns prose first, then valid JSON on retry prompt."""
        call_count = 0
        prompts_received: list[str] = []

        class RetryProvider:
            def extract(self, prompt: str) -> str:
                nonlocal call_count
                call_count += 1
                prompts_received.append(prompt)
                if call_count == 1:
                    return "Here is the analysis:\nNot JSON at all"
                return '{"incident_id": "X", "source": {}, "context": {}, "event": {}, "bowtie": {"hazards": [{"hazard_id": "H-001", "description": "x"}], "threats": [{"threat_id": "T-001", "description": "x"}], "consequences": [{"consequence_id": "CON-001", "description": "x"}], "controls": []}, "controls": [], "pifs": {}}'

        with tempfile.TemporaryDirectory() as tmpdir:
            text_dir = Path(tmpdir) / "text"
            out_dir = Path(tmpdir) / "out"
            text_dir.mkdir()
            (text_dir / "retry-test.txt").write_text("Some incident text.")

            rows = extract_structured(text_dir, out_dir, RetryProvider(), "test")

            assert len(rows) == 1
            assert rows[0].extracted is True
            assert call_count == 2  # original + retry
            # Retry must contain the full schema prompt, not just a snippet
            assert "SCHEMA_TEMPLATE" not in prompts_received[1]  # template already resolved
            assert "Incident Text" in prompts_received[1] or "incident" in prompts_received[1].lower()
            assert "CRITICAL" in prompts_received[1]  # strict suffix


class TestRunReport:
    def _make_row(self, incident_id: str, valid: bool = True,
                  validation_errors: str | None = None,
                  error: str | None = None,
                  extracted: bool = True) -> StructuredManifestRow:
        return StructuredManifestRow(
            incident_id=incident_id,
            source_text_path=f"text/{incident_id}.txt",
            output_json_path=f"out/{incident_id}.json",
            provider="stub",
            extracted=extracted,
            valid=valid,
            validation_errors=validation_errors,
            error=error,
        )

    def test_report_counts(self):
        rows = [
            self._make_row("A", valid=True),
            self._make_row("B", valid=False, validation_errors="event -> costs: Input should be a valid string"),
            self._make_row("C", valid=False, validation_errors="JSON parse error: Expecting value"),
            self._make_row("D", valid=False, extracted=False, error="Timeout"),
        ]
        report = generate_run_report(rows, "stub", "test-model")

        assert report["total"] == 4
        assert report["extracted"] == 3
        assert report["valid"] == 1
        assert report["invalid"] == 2
        assert report["parse_failed"] == 1
        assert report["errored"] == 1
        assert report["provider"] == "stub"
        assert report["model"] == "test-model"
        assert 0 < report["valid_rate"] < 1
        assert len(report["top_validation_errors"]) == 2

    def test_empty_rows(self):
        report = generate_run_report([], "stub")
        assert report["total"] == 0
        assert report["valid_rate"] == 0.0


class TestModelDumpWritePath:
    """Extracted JSON files must contain all schema sections with defaults."""

    def test_output_has_all_sections(self):
        provider = StubProvider()
        with tempfile.TemporaryDirectory() as tmpdir:
            text_dir = Path(tmpdir) / "text"
            out_dir = Path(tmpdir) / "out"
            text_dir.mkdir()
            (text_dir / "full-001.txt").write_text("An incident occurred at a refinery.")

            rows = extract_structured(text_dir, out_dir, provider, "stub")
            assert len(rows) == 1
            assert rows[0].valid is True

            data = json.loads((out_dir / "stub" / "full-001.json").read_text())
            # All top-level sections must be present
            for key in ("incident_id", "source", "context", "event", "bowtie", "pifs", "notes"):
                assert key in data, f"Missing top-level key: {key}"

            # pifs must have all three sub-sections with defaults
            assert "people" in data["pifs"]
            assert "work" in data["pifs"]
            assert "organisation" in data["pifs"]

            # bowtie must have all four sub-sections
            for key in ("hazards", "threats", "consequences", "controls"):
                assert key in data["bowtie"], f"Missing bowtie key: {key}"

            # event must have summary field
            assert "summary" in data["event"]

            # notes must have schema_version
            assert data["notes"]["schema_version"] == "2.3"


class TestQualityGate:
    def test_quality_gate_computes_metrics(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            # Write a complete incident JSON
            complete = {
                "incident_id": "INC-1",
                "source": {},
                "context": {},
                "event": {"summary": "A fire broke out."},
                "bowtie": {
                    "hazards": [{"hazard_id": "H-001", "name": "fire"}],
                    "threats": [{"threat_id": "T-001", "name": "ignition"}],
                    "consequences": [{"consequence_id": "CON-001", "name": "injury"}],
                    "controls": [{"control_id": "C-001", "name": "alarm"}],
                },
                "pifs": {
                    "people": {"competence_mentioned": True},
                    "work": {},
                    "organisation": {},
                },
            }
            (d / "inc1.json").write_text(json.dumps(complete))

            # Write a minimal incident JSON (missing most)
            minimal = {"incident_id": "INC-2", "source": {}, "context": {}, "event": {}}
            (d / "inc2.json").write_text(json.dumps(minimal))

            gate = compute_quality_gate(d)

            assert gate["total"] == 2
            assert gate["has_controls"] == 1
            assert gate["has_summary"] == 1
            assert gate["has_pifs"] == 1
            assert gate["has_hazards"] == 1
            assert gate["has_controls_pct"] == 50.0
            # Controls count distribution
            assert gate["controls_count_min"] == 0
            assert gate["controls_count_max"] == 1
            assert gate["controls_count_p50"] >= 0
            assert gate["controls_count_p90"] >= 0

    def test_quality_gate_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gate = compute_quality_gate(Path(tmpdir))
            assert gate["total"] == 0
