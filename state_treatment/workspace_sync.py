"""Keep the State Treatment workspace in step with the app.

Frappe re-imports a workspace file only when it looks newer than the stored
copy, so shortcut and block changes in a release could be skipped on
migrate. Reloading it with force on every migrate makes the workspace match
the release.
"""
import frappe


def refresh_workspace():
    frappe.reload_doc("State Treatment", "workspace", "State Treatment", force=True)
