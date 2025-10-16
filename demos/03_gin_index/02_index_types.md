# Index Types

So far we have an index on the username (email), and a funcional index on the lowercase username.
  

```sql
select * from users limit 10;
```

We can query by username fairly quickly:

<!-- plan -->
```sql
select * from users where username='wdavis@hotmail.com';
```

And, if we want to be case-insensitive, we can do so as well:

<!-- plan -->
```sql
select * from users where lower(username)=lower('WDavis@hotmail.com');
```
