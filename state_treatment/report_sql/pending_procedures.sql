SELECT
    p.parent AS "رقم الطلب:Link/State Treatment Recommendation:170",
    p.item_name AS "الإجراء:Data:280",
    p.official_protocol_code AS "كود البروتوكول:Data:150",
    p.rate AS "السعر:Currency:130"
FROM `tabRecommendation Protocol Item` p
WHERE p.parenttype = 'State Treatment Recommendation'
  AND p.parentfield = 'protocol_items'
  AND p.treatment_type = 'Procedure'
  AND COALESCE(p.procedure_done, 0) = 0
  AND p.parent IN (
      SELECT name FROM `tabState Treatment Recommendation`
      WHERE status = 'Approved for Disbursement'
  )
ORDER BY p.parent, p.decision_sequence
