"""Give existing sites the default Date of Birth row in the Patient Field Map."""
from state_treatment.settings import add_default_dob_mapping


def execute():
    add_default_dob_mapping()
