// Exact values from encoder.joblib (verified 2026-03-30, 49 barrier families)
export const BARRIER_TYPES = ['administrative', 'engineering', 'ppe', 'unknown'] as const

export const LINE_OF_DEFENSE = ['1st', '2nd', '3rd', 'recovery', 'unknown'] as const

export const SOURCE_AGENCY_DEFAULT = 'UNKNOWN'

// All 49 barrier families extracted from encoder.joblib
export const BARRIER_FAMILIES = [
  'active_fire_protection_firefighting',
  'active_intervention_to_stop_release',
  'alarms_general_alarm_pa',
  'change_management',
  'chemical_release_scrubbing_neutralization',
  'communication',
  'control_room_habitability_hvac_pressurization',
  'detection_monitoring_alarms',
  'detection_monitoring_surveillance',
  'emergency_disconnect_eds',
  'emergency_escape_access_rescue_decon',
  'emergency_power_backup_utilities',
  'emergency_preparedness_planning_training_drills',
  'emergency_shutdown_isolation',
  'emergency_shutdown_isolation_depressurization',
  'environmental_response_cleanup_reporting',
  'evacuation_muster_shelter_exclusion_access_control',
  'fire_response_firewatch_ignition_control',
  'fluid_discharge_and_containment',
  'gas_detection_atmospheric_monitoring',
  'hazard_analysis_prework_checks',
  'ignition_source_control',
  'incident_command_coordination_and_comms',
  'investigation_corrective_action_post_incident_verification',
  'maintenance',
  'marine_collision_avoidance',
  'mechanical_integrity',
  'medical_response_and_evacuation',
  'monitoring',
  'operating_controls_and_limits',
  'other_admin',
  'other_engineering',
  'other_ppe',
  'other_unknown',
  'overpressurization_gas_discharge_gas_isolation',
  'permits_controlled_work_during_response',
  'physical_protection_retention_restraints',
  'planning',
  'ppe_and_respiratory_protection',
  'pressure_relief_blowdown_flare_disposal',
  'prevention_of_ignition',
  'procedures',
  'regulatory_and_permits',
  'remote_monitoring_intervention_subsea',
  'spill_containment_environmental_mitigation',
  'structural_mechanical_integrity_escalation_prevention',
  'supervision_staffing_oversight',
  'training',
  'well_control_barriers_kill',
] as const

// ---------------------------------------------------------------------------
// Demo scenario (Loss of Containment — LOC)
// 5 prevention + 2 mitigation = 7 barriers.
// Designed for risk spread: engineering barriers score Low, administrative
// barriers (monitoring, procedures) at higher LOD score Medium/High.
// barrier_type/barrier_family use exact encoder values from encoder.joblib.
// ---------------------------------------------------------------------------

export const DEMO_SCENARIO = {
  eventDescription: 'Loss of containment during high-pressure gas transfer operations',
  barriers: [
    {
      name: 'Pressure Relief Valve',
      side: 'prevention' as const,
      barrier_type: 'engineering' as const,
      barrier_family: 'pressure_relief_blowdown_flare_disposal',
      line_of_defense: '1st' as const,
      barrierRole: 'Prevent overpressure beyond design limits',
      pathway_sequence: 0,
      upstream_failure_rate: 0.0,
    },
    {
      name: 'Automatic Shutdown System',
      side: 'prevention' as const,
      barrier_type: 'engineering' as const,
      barrier_family: 'emergency_shutdown_isolation',
      line_of_defense: '1st' as const,
      barrierRole: 'Isolate on high pressure signal',
      pathway_sequence: 0,
      upstream_failure_rate: 0.0,
    },
    {
      name: 'Operator Monitoring Procedure',
      side: 'prevention' as const,
      barrier_type: 'administrative' as const,
      barrier_family: 'monitoring',
      line_of_defense: '3rd' as const,
      barrierRole: 'Manual monitoring of pressure and flow readings during transfer',
      pathway_sequence: 3,
      upstream_failure_rate: 0.7,
    },
    {
      name: 'Pre-Transfer Safety Checklist',
      side: 'prevention' as const,
      barrier_type: 'administrative' as const,
      barrier_family: 'procedures',
      line_of_defense: '2nd' as const,
      barrierRole: 'Verify valve alignment and line integrity before operations',
      pathway_sequence: 2,
      upstream_failure_rate: 0.5,
    },
    {
      name: 'Gas Detection System',
      side: 'prevention' as const,
      barrier_type: 'engineering' as const,
      barrier_family: 'gas_detection_atmospheric_monitoring',
      line_of_defense: '2nd' as const,
      barrierRole: 'Detect gas release in transfer area',
      pathway_sequence: 1,
      upstream_failure_rate: 0.3,
    },
    {
      name: 'Emergency Response Plan',
      side: 'mitigation' as const,
      barrier_type: 'administrative' as const,
      barrier_family: 'emergency_preparedness_planning_training_drills',
      line_of_defense: '1st' as const,
      barrierRole: 'Coordinate emergency response and evacuation',
      pathway_sequence: 1,
      upstream_failure_rate: 0.4,
    },
    {
      name: 'Fire Suppression System',
      side: 'mitigation' as const,
      barrier_type: 'engineering' as const,
      barrier_family: 'active_fire_protection_firefighting',
      line_of_defense: '1st' as const,
      barrierRole: 'Suppress fire from ignited gas release',
      pathway_sequence: 0,
      upstream_failure_rate: 0.0,
    },
  ],
}
