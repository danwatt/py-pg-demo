# Index Types

So far we have an index on the username (email), and a functional index on the lowercase username.

E-mail addresses are supposed to be case-insensitive, but on this particular database, nothing
during account creation enforced that, so there was a mix of cases in the usernames. All queries
to look up a user would look like `WHERE lower(username) = lower(:email)`, and the functional index
would be used.

We can query by username fairly quickly:


<!-- plan -->
```sql
select * from users where username='jason41@hotmail.com';
```

And, if we want to be case-insensitive like we are supposed to, we can do so as well:

<!-- plan -->
```sql
select * from users where lower(username)=lower('jason41@HotMail.COM');
```

But where we run into problems is when we start to use LIKE queries:

<!-- plan -->
```sql
select * from users where username ilike 'jason41%' limit 10;
```

Using a prefix match is fine, but if we wanted to find all users with "watt" in their email address,
this starts to get slow:

<!-- plan -->
```sql
select count(username) from users where lower(username) like '%watt%';
```

## Enter the GIN index


```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
       
create index concurrently if not exists ix_users_email_gin
    on users using gin (lower(username) gin_trgm_ops);

create index concurrently if not exists ix_users_email_gist
    on users using gist (lower(username) gist_trgm_ops);

VACUUM ANALYZE users;
```

<!-- plan -->
```sql
select count(username) from users where lower(username) like '%watt%';
```