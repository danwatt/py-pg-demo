# Optimization

<!-- plan -->
```sql
SELECT DISTINCT s.device_id, d.created_at, s.user_agent, dt.name, d.user_id
FROM sessions s
         JOIN devices d ON d.id = s.device_id
         LEFT JOIN device_types dt ON dt.id = d.device_type_id
WHERE d.user_id = (select id from users where username='jillrhodes@hotmail.com')
ORDER BY d.created_at DESC;
```
## Add basic indexes
```sql
create index ix_test1 on sessions(device_id);
create index ix_test2 on devices(user_id);
create index ix_user on users(username);
vacuum analyze;
```

<!-- plan -->
```sql
SELECT DISTINCT s.device_id, d.created_at, s.user_agent, dt.name, d.user_id
FROM sessions s
         JOIN devices d ON d.id = s.device_id
         LEFT JOIN device_types dt ON dt.id = d.device_type_id
WHERE d.user_id = (select id from users where username='jillrhodes@hotmail.com')
ORDER BY d.created_at DESC;
```

## Add Covering Indexs

```sql 
create index ix_test3 on devices(user_id,created_at DESC);
create index ix_test4 on devices(user_id,created_at DESC) include (created_at, user_id, device_type_id);
create index ix_test5 on sessions(device_id) include (user_agent);
create index ix_test6 on sessions(device_id) include (user_agent,device_id);
vacuum analyze;
```

<!-- plan -->
```sql
SELECT DISTINCT s.device_id, d.created_at, s.user_agent, dt.name, d.user_id
FROM sessions s
         JOIN devices d ON d.id = s.device_id
         LEFT JOIN device_types dt ON dt.id = d.device_type_id
WHERE d.user_id = (select id from users where username='jillrhodes@hotmail.com')
ORDER BY d.created_at DESC;
```


```sql
SELECT
    relname AS object_name,
    pg_size_pretty(pg_total_relation_size(pg_class.oid)) AS total_size
FROM pg_class
JOIN pg_namespace ON pg_namespace.oid = pg_class.relnamespace
WHERE pg_namespace.nspname = current_schema()
  AND relkind IN ('r', 'i')
ORDER BY total_size DESC;
```