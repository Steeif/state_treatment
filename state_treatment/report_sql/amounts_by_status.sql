SELECT
    status AS "الحالة:Data:200",
    COUNT(name) AS "عدد الطلبات:Int:140",
    COALESCE(SUM(total_amount), 0) AS "إجمالي المبالغ (ج.م):Currency:180"
FROM `tabState Treatment Recommendation`
GROUP BY status
ORDER BY status
