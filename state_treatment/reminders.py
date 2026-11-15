"""Reminders for treatment doses and appointments.

A daily job tells the patient, and the users listed in State Treatment
Settings, about each dose or appointment that falls within the reminder window
(a number of days before the date, 2 by default). Each dose and appointment is
reminded once, tracked by its reminder_sent flag.
"""

import frappe
from frappe.utils import add_days, cint, formatdate, getdate, nowdate

APPROVED_STATUS = "Approved for Disbursement"
RECOMMENDATION = "State Treatment Recommendation"
SETTINGS = "State Treatment Settings"
DOSE_DOCTYPE = "Treatment Dose Tracking Item"
APPOINTMENT_DOCTYPE = "Treatment Appointment"
DEFAULT_DAYS = 2
APPOINTMENT_TYPES = {
    "Procedure": "إجراء",
    "Consultation": "كشف",
    "Follow-up": "متابعة",
    "Other": "زيارة",
}


def send_upcoming_reminders():
    """Scheduled daily. Sends every due reminder once."""
    settings = frappe.get_single(SETTINGS)
    if not cint(settings.reminders_enabled):
        return
    days = cint(settings.reminder_days_before) or DEFAULT_DAYS
    staff = [row.user for row in settings.reminder_recipients if row.user]

    today = getdate(nowdate())
    last_day = add_days(today, days)
    for name in frappe.get_all(RECOMMENDATION, filters={"status": APPROVED_STATUS}, pluck="name"):
        doc = frappe.get_doc(RECOMMENDATION, name)
        for kind, row in due_items(doc, today, last_day):
            try:
                deliver(doc, kind, row, staff)
            except Exception:
                frappe.log_error(frappe.get_traceback(), "State Treatment reminder")


def due_items(doc, today, last_day):
    """Doses and appointments inside the window that have not been reminded yet."""
    latest = {}
    for dose in doc.treatment_doses:
        latest[dose.protocol_item] = max(latest.get(dose.protocol_item, 0), cint(dose.schedule_version))

    items = []
    for dose in doc.treatment_doses:
        if cint(dose.dispensed) or cint(dose.reminder_sent):
            continue
        if cint(dose.schedule_version) != latest.get(dose.protocol_item):
            continue  # a dose from an older regimen version
        if dose.scheduled_date and today <= getdate(dose.scheduled_date) <= last_day:
            items.append(("dose", dose))

    for appointment in doc.appointments:
        if cint(appointment.reminder_sent) or not appointment.appointment_date:
            continue
        if today <= getdate(appointment.appointment_date) <= last_day:
            items.append(("appointment", appointment))
    return items


def deliver(doc, kind, row, staff):
    patient = frappe.db.get_value(
        "Patient", doc.patient, ["patient_name", "email", "mobile"], as_dict=True
    ) or {}
    patient_name = patient.get("patient_name") or doc.patient
    subject, patient_text, staff_text = _messages(doc, kind, row, patient_name)

    sent = False
    if patient.get("email"):
        frappe.sendmail(
            recipients=[patient["email"]],
            subject=subject,
            message=patient_text.replace("\n", "<br>"),
            reference_doctype=RECOMMENDATION,
            reference_name=doc.name,
        )
        sent = True
    if staff:
        frappe.sendmail(
            recipients=staff,
            subject=subject,
            message=staff_text.replace("\n", "<br>"),
            reference_doctype=RECOMMENDATION,
            reference_name=doc.name,
        )
        sent = True
    if patient.get("mobile"):
        try:
            _send_sms(patient["mobile"], patient_text)
            sent = True
        except Exception:
            frappe.log_error(frappe.get_traceback(), "State Treatment reminder SMS")

    # Nothing reached anyone: leave the row unmarked so a later run can try again.
    if sent:
        doctype = DOSE_DOCTYPE if kind == "dose" else APPOINTMENT_DOCTYPE
        frappe.db.set_value(doctype, row.name, "reminder_sent", 1, update_modified=False)


def _messages(doc, kind, row, patient_name):
    reference = doc.recommendation_no or doc.name
    if kind == "dose":
        when = formatdate(row.scheduled_date)
        subject = f"تذكير بجرعة علاج يوم {when}"
        patient_text = (
            f"عزيزي {patient_name}،\n"
            f"لديك جرعة {row.dose} من {row.medicine_name} يوم {when}.\n"
            "يرجى الحضور للصرف في موعدها.\n"
            f"رقم التوصية: {reference}"
        )
        staff_text = (
            f"تذكير: جرعة {row.dose} من {row.medicine_name} للمريض {patient_name} يوم {when}.\n"
            f"رقم التوصية: {reference}"
        )
        return subject, patient_text, staff_text

    when = formatdate(row.appointment_date)
    time_text = _time_text(row.appointment_time)
    when_text = f"{when} الساعة {time_text}" if time_text else when
    label = APPOINTMENT_TYPES.get(row.appointment_type, "زيارة")
    notes = f"\n{row.notes}" if row.notes else ""
    subject = f"تذكير بموعد {label} يوم {when}"
    patient_text = f"عزيزي {patient_name}،\nلديك موعد {label} يوم {when_text}.{notes}"
    staff_text = f"تذكير: موعد {label} للمريض {patient_name} يوم {when_text}.\nرقم التوصية: {reference}{notes}"
    return subject, patient_text, staff_text


def _time_text(value):
    if not value:
        return ""
    hours, minutes = str(value).split(":")[:2]
    return f"{int(hours):02d}:{int(minutes):02d}"


def _send_sms(mobile, text):
    from frappe.core.doctype.sms_settings.sms_settings import send_sms

    send_sms([mobile], text)
