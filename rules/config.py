# Risk thresholds and escalation timings.
# ponytail: values are MVP defaults with no clinical source; adjust here if a real
# medical guideline is provided later — nothing else in the codebase should change.

BP_SYSTOLIC_DANGER_HIGH = 180
BP_SYSTOLIC_DANGER_LOW = 90
BP_DIASTOLIC_DANGER_HIGH = 120
BP_SYSTOLIC_WARNING_HIGH = 160

HR_DANGER_HIGH = 120
HR_DANGER_LOW = 50
HR_WARNING_HIGH = 100
HR_WARNING_LOW = 55

VITAL_STALE_MINUTES = 60

DANGER_SYMPTOMS = ["胸痛", "呼吸困難", "意識不清", "劇烈疼痛", "無法起身"]

FIRST_REMINDER_DELAY_MINUTES = 20
SECOND_REMINDER_DELAY_MINUTES = 20
MISSED_THRESHOLD_MINUTES = 60
EMERGENCY_UNRESPONSIVE_MINUTES = 120
