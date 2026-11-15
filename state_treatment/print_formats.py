import json
import os

import frappe

PRINT_FORMAT_FILE = os.path.join(os.path.dirname(__file__), "fixtures", "print_format.json")


def ensure_print_formats():
    """Create or update the official print formats from fixtures/print_format.json.

    Runs after every migrate, so each format exists even when the fixture import
    skips one. The repository is the source of truth: the stored HTML is replaced.
    """
    with open(PRINT_FORMAT_FILE, encoding="utf-8") as f:
        formats = json.load(f)

    for data in formats:
        values = {key: value for key, value in data.items() if key != "doctype"}
        if frappe.db.exists("Print Format", data["name"]):
            doc = frappe.get_doc("Print Format", data["name"])
            doc.update(values)
            doc.save(ignore_permissions=True)
        else:
            doc = frappe.get_doc(dict(values, doctype="Print Format"))
            doc.insert(ignore_permissions=True)
