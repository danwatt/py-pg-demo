# Query data

Here is a query that returns rows:

<!-- chart:bar x=name y=age title="Age by Person" -->
```sql
SELECT id, name, age, age >= 50 AS senior FROM people ORDER BY id;
```

Join across the relationship (people -> pets):

```sql
SELECT p.name AS person, pe.name AS pet_name, pe.species
FROM people p
JOIN pets pe ON pe.person_id = p.id
ORDER BY p.name, pet_name;
```

Aggregate using the relationship:

<!-- chart:bar x=name y=pet_count title="Pets per Person" -->
```sql
SELECT p.name, COUNT(*)::int AS pet_count
FROM people p
LEFT JOIN pets pe ON pe.person_id = p.id
GROUP BY p.name
ORDER BY p.name;
```

You can also show aggregates:

```postgresql
SELECT COUNT(*) AS total, AVG(age)::numeric(10,2) AS avg_age FROM people;
```

## Explain plan example

Add a plan directive before a SQL block to render a visual plan:

<!-- plan -->
```sql
SELECT COUNT(*) FROM people;
```
