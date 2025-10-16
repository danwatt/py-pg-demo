<!-- schemadiagram -->

At one point I was working on a front-end tool that was built for customer support staff to help
customers with their accounts.

One of the features was to be able to search for a user by a partial name.

Their e-mail address was their username, and we needed to be able to search by a part of an e-mail address,
3 or more characters. Sometimes users would forget their domain name, or customer support would have a hard
time hearing it without getting the users to phonetically sound it out, so it was easier to do a partial search.

In SQL, this kind of search would use a LIKE operator, such as "WHERE username LIKE '%robert123%'.

But, in SQL, doing a LIKE query where the `%` is at the beginning will result in traditional indexes being
bypassed.

```sql
DROP TABLE IF EXISTS users;

CREATE table users (
  id serial primary key,
  username varchar NOT NULL,
    name varchar not null
);

create unique index ix_username on users(username);
create index ix_user_lower on users(lower(username));
```
<!-- fakeseed -->
```yaml
seed: 42
table: users
rows: 10000
fields:
  username:
    unique: true
    faker: ascii_email
  name:
    faker: name
```
