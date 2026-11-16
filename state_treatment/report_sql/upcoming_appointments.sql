SELECT
    a.parent AS "رقم الطلب:Link/State Treatment Recommendation:170",
    a.appointment_date AS "تاريخ الموعد:Date:130",
    a.appointment_time AS "وقت الموعد:Time:110",
    a.appointment_type AS "نوع الموعد:Data:150",
    a.notes AS "ملاحظات:Data:260"
FROM `tabTreatment Appointment` a
WHERE a.parenttype = 'State Treatment Recommendation'
  AND a.parentfield = 'appointments'
  AND a.appointment_date >= CURDATE()
ORDER BY a.appointment_date, a.appointment_time
