"""Give existing sites the default Patient Field Map row (National ID)."""
from state_treatment.settings import seed_default_patient_map


def execute():
    seed_default_patient_map()
