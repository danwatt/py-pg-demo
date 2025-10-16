<!-- schemadiagram -->
```sql
DROP TABLE IF EXISTS users;

CREATE table users (
  id serial primary key,
  username varchar NOT NULL
);

create index ix_username on users(username);
create index ix_user_lower on users(lower(username));
```
<!-- fakeseed -->
```yaml
seed: 42
table: users
rows: 100000
fields:
  username:
    faker: ascii_free_email
```
