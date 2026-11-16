SELECT
    status AS "الحالة:Data:200",
    COUNT(name) AS "عدد الطلبات:Int:140"
FROM `tabState Treatment Recommendation`
GROUP BY status
ORDER BY COUNT(name) DESC
