import pytest
from src.rag.corpus_builder import assign_barrier_family, compose_barrier_text
from scripts.association_mining.event_barrier_normalization import (
    normalize_control_name,
    normalize_for_family,
    _match_family,
    _QUADRANT_DISPATCH,
    PREVENTION_ADMIN_FAMILIES,
    PREVENTION_ENGINEERING_FAMILIES,
    MITIGATION_ADMIN_FAMILIES,
    MITIGATION_ENGINEERING_FAMILIES,
)


class TestBarrierFamilyNormalization:
    """Verify normalization functions from event_barrier_normalization.py
    are importable and produce expected results for RAG corpus building."""

    def test_normalize_control_name_basic(self):
        result = normalize_control_name("PTW - Permit to Work")
        assert "permit to work" in result
        assert "ptw" not in result  # expanded

    def test_normalize_for_family_combines(self):
        result = normalize_for_family("ESD Valve procedure for shutdown")
        assert "emergency shutdown" in result  # esd expanded

    def test_prevention_admin_training(self):
        text = normalize_for_family("safety training program for operators")
        family = _match_family(text, PREVENTION_ADMIN_FAMILIES, "other_admin")
        assert family == "training"

    def test_prevention_eng_pressure_relief(self):
        text = normalize_for_family("pressure safety valve psv on wellhead")
        family = _match_family(text, PREVENTION_ENGINEERING_FAMILIES, "other_engineering")
        assert family == "overpressurization_gas_discharge_gas_isolation"

    def test_mitigation_admin_evacuation(self):
        text = normalize_for_family("muster point evacuation procedure")
        family = _match_family(text, MITIGATION_ADMIN_FAMILIES, "other_admin")
        assert family == "evacuation_muster_shelter_exclusion_access_control"

    def test_mitigation_eng_fire_protection(self):
        text = normalize_for_family("deluge fire suppression system")
        family = _match_family(text, MITIGATION_ENGINEERING_FAMILIES, "other_engineering")
        assert family == "active_fire_protection_firefighting"

    def test_quadrant_dispatch_keys(self):
        assert ("prevention", "administrative") in _QUADRANT_DISPATCH
        assert ("prevention", "engineering") in _QUADRANT_DISPATCH
        assert ("mitigation", "administrative") in _QUADRANT_DISPATCH
        assert ("mitigation", "engineering") in _QUADRANT_DISPATCH

    def test_ppe_fallback(self):
        # ppe has no quadrant taxonomy, should get other_ppe
        dispatch_key = ("prevention", "ppe")
        assert dispatch_key not in _QUADRANT_DISPATCH

    def test_unknown_text_gets_other(self):
        text = normalize_for_family("completely unrelated concept xyz")
        family = _match_family(text, PREVENTION_ADMIN_FAMILIES, "other_admin")
        assert family == "other_admin"


class TestAssignBarrierFamily:
    def test_prevention_admin(self):
        result = assign_barrier_family(
            name="Safety Training Program",
            barrier_role="Train operators on procedures",
            side="prevention",
            barrier_type="administrative",
        )
        assert result == "training"

    def test_prevention_engineering(self):
        result = assign_barrier_family(
            name="Pressure Safety Valve",
            barrier_role="Prevent overpressure",
            side="prevention",
            barrier_type="engineering",
        )
        assert result == "overpressurization_gas_discharge_gas_isolation"

    def test_mitigation_engineering(self):
        result = assign_barrier_family(
            name="Deluge System",
            barrier_role="Suppress fire",
            side="mitigation",
            barrier_type="engineering",
        )
        assert result == "active_fire_protection_firefighting"

    def test_ppe_gets_other_ppe(self):
        result = assign_barrier_family(
            name="Hard Hat",
            barrier_role="Protect head",
            side="prevention",
            barrier_type="ppe",
        )
        assert result == "other_ppe"

    def test_unknown_type_gets_other_unknown(self):
        result = assign_barrier_family(
            name="Mystery Barrier",
            barrier_role="Unknown role",
            side="prevention",
            barrier_type="unknown",
        )
        assert result == "other_unknown"


class TestComposeBarrierText:
    def test_all_fields_present(self):
        result = compose_barrier_text(
            name="ESD Valve",
            barrier_role="Emergency isolation",
            lod_basis="First line automated shutdown",
        )
        assert result == (
            "Barrier: ESD Valve\n"
            "Role: Emergency isolation\n"
            "LOD Basis: First line automated shutdown"
        )

    def test_missing_lod_basis(self):
        result = compose_barrier_text(
            name="ESD Valve",
            barrier_role="Emergency isolation",
            lod_basis=None,
        )
        assert result == (
            "Barrier: ESD Valve\n"
            "Role: Emergency isolation\n"
            "LOD Basis: N/A"
        )

    def test_empty_strings(self):
        result = compose_barrier_text(name="", barrier_role="", lod_basis="")
        assert "Barrier: " in result
        assert "Role: " in result
        assert "LOD Basis: " in result
