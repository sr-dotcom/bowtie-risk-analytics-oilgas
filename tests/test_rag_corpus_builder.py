import pytest
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
