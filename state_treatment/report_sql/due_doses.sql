SELECT
    d.parent AS "رقم الطلب:Link/State Treatment Recommendation:170",
    d.medicine_name AS "الدواء:Data:200",
    d.dose AS "الجرعة:Data:160",
    d.scheduled_date AS "تاريخ الجرعة:Date:130"
FROM `tabTreatment Dose Tracking Item` d
WHERE d.parenttype = 'State Treatment Recommendation'
  AND d.parentfield = 'treatment_doses'
  AND COALESCE(d.dispensed, 0) = 0
  AND d.parent IN (
      SELECT name FROM `tabState Treatment Recommendation`
      WHERE status = 'Approved for Disbursement'
  )
  AND d.schedule_version = (
      SELECT MAX(d2.schedule_version)
      FROM `tabTreatment Dose Tracking Item` d2
      WHERE d2.parent = d.parent AND d2.protocol_item = d.protocol_item
  )
ORDER BY d.scheduled_date, d.parent
