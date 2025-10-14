# Unoptimized Queries

```sql
SELECT DISTINCT s.device_id, d.created_date, s.user_agent, dt.name
FROM sessions s
         JOIN devices d ON d.device_id = s.device_id
         LEFT JOIN device_types dt ON dt.device_type_id = d.device_type_id
WHERE d.user_id = (select user_id from users order by random() limit 1)
ORDER BY d.created_date DESC;
```