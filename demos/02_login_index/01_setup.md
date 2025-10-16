# Setup schema

## Backstory

There was a legacy system that I once had to maintain that dealt with user access.

This system was very much of the "if it isn't broken, don't fix it" variety. It
had almost 0 automated tests for it, and getting QA time to manually test it was 
difficult. Unless we had some feature that was going to give us a notable ROI, we
basically just let it be.

This system almost had the most expensive database in the company. Accounting for
read replicas and the like, it cost low six-figures annually.

One of my roles was to monitor the system as a whole - the code, 3rd part systems,
and in this case, the database. And, I noticed that there was one query that
ran very frequently, and during peak times was responsible for over half of the
load on the database.

The query itself was not too terribly complex or expensive when run on its own.
The typical response time was well under 100ms. But, as activity was closely
correlated to peak user demand throughout the day, that query time started to add
up during peak times.

Below is a rough approximation of the database schema, with just the relevant
columns.

Every time a user logged in, a `session` record would be created. The user's `device`
would be tracked with a unique ID for that device, and we also tracked some data such
as the user agent.

<!-- schemadiagram -->
```sql

DROP TABLE IF EXISTS sessions;
DROP TABLE IF EXISTS devices;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS device_types;
DROP TABLE IF EXISTS temp_user_agents;

CREATE table users (
  id serial primary key,
  username varchar NOT NULL
);

CREATE table device_types (
    id serial primary key,
    name varchar NOT NULL
);

CREATE table devices (
    id serial primary key,
    -- TODO: Device ID, though its actually not really that relevant for this demo
    user_id int NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    device_type_id int NOT NULL REFERENCES device_types(id) ON DELETE CASCADE,
    created_at timestamp NOT NULL DEFAULT now()
);

CREATE table sessions (
    id bigserial primary key,
    user_id int not null references users(id) on delete cascade,
    device_id int NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    user_agent varchar NOT NULL,
    created_at timestamp NOT NULL DEFAULT now()
);

CREATE table temp_user_agents(
    id serial primary key,
    user_agent varchar NOT NULL
);
```

## Seed Data

```sql
insert into device_types (name) values ('desktop'), ('mobile'), ('tablet'), ('console'), ('tv'), ('smartwatch'), ('other');

insert into temp_user_agents (user_agent)
SELECT
    (ARRAY[
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.3' || floor(random()*100)+1,
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.1' || floor(random()*100)+1,
        'Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.5481.77 Mobile Safari/537.3' || floor(random()*100)+1,
        'Mozilla/5.0 (iPhone; CPU iPhone OS 16_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.2 Mobile/15E148 Safari/604.' || floor(random()*100)+1,
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/109.' || floor(random()*100)+1,
        'Mozilla/5.0 (Linux; Android 10; SM-A505FN) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.5359.128 Mobile Safari/537.3' || floor(random()*100)+1,
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.1' || floor(random()*100)+1,
        'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.3' || floor(random()*100)+1,
        'Mozilla/5.0 (Linux; Android 9; Pixel 3 XL) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.51 Mobile Safari/537.3' || floor(random()*100)+1,
        'Mozilla/5.0 (iPad; CPU OS 15_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.3 Mobile/15E148 Safari/604.' || floor(random()*100)+1
    ])[floor(random()*10)+1]
FROM generate_series(1,50);
```

<!-- fakeseed -->
```yaml
seed: 42
table: users
rows: 50000
fields:
  username:
    faker: ascii_free_email
```

```sql
SELECT setseed(0.42);
-- Insert devices for a random subset of users (e.g., 40% of users)
INSERT INTO devices (user_id, device_type_id,created_at)
SELECT u.id, (SELECT id FROM device_types ORDER BY random() LIMIT 1), NOW() - (random() * INTERVAL '365 days')
FROM users u
WHERE random() < 0.4;

-- Insert more devices for a random subset of users (e.g., 40% of users)
INSERT INTO devices (user_id, device_type_id, created_at)
SELECT u.id, (SELECT id FROM device_types ORDER BY random() LIMIT 1), NOW() - (random() * INTERVAL '365 days')
FROM users u
WHERE random() < 0.4;

-- Insert even more devices for a random subset of users (e.g., 40% of users)
INSERT INTO devices (user_id, device_type_id, created_at)
SELECT u.id, (SELECT id FROM device_types ORDER BY random() LIMIT 1),NOW() - (random() * INTERVAL '365 days')
FROM users u
WHERE random() < 0.4;
```

At this point some users will have 0 devices, some will have 1 device, some 2, and fewer with 3.
```sql
with user_devices as (select d.user_id, count(*) as device_count
                      from devices d
                      group by d.user_id)
select device_count, count(*) as num_users
from user_devices ud
group by device_count;
```

```sql
select count(distinct user_id) from devices;
```

## Seed Session Data
```sql
SELECT setseed(0.42);

-- Every device has at least one session
with u as (select d.id as device_id,d.user_id, now() - (random() * INTERVAL '365 days') as last_seen, mod(d.id + floor(random()*100)::bigint, (select count(*) from temp_user_agents)) as ua_id from devices d)
INSERT INTO sessions(device_id, user_id, user_agent, created_at) SELECT device_id, user_id,user_agent, last_seen FROM u join temp_user_agents tua on u.ua_id = tua.id order by random();

-- Some have more than one

with u as (select d.id as device_id,d.user_id, now() - (random() * INTERVAL '365 days') as last_seen, mod(d.id + floor(random()*100)::bigint, (select count(*) from temp_user_agents)) as ua_id from devices d)
INSERT INTO sessions(device_id, user_id, user_agent, created_at) SELECT device_id, user_id,user_agent, last_seen FROM u join temp_user_agents tua on u.ua_id = tua.id  where random() < 0.8 order by random();

with u as (select d.id as device_id,d.user_id, now() - (random() * INTERVAL '365 days') as last_seen, mod(d.id + floor(random()*100)::bigint, (select count(*) from temp_user_agents)) as ua_id from devices d)
INSERT INTO sessions(device_id, user_id, user_agent, created_at) SELECT device_id, user_id,user_agent, last_seen FROM u join temp_user_agents tua on u.ua_id = tua.id  where random() < 0.8 order by random();

with u as (select d.id as device_id,d.user_id, now() - (random() * INTERVAL '365 days') as last_seen, mod(d.id + floor(random()*100)::bigint, (select count(*) from temp_user_agents)) as ua_id from devices d)
INSERT INTO sessions(device_id, user_id, user_agent, created_at) SELECT device_id, user_id,user_agent, last_seen FROM u join temp_user_agents tua on u.ua_id = tua.id  where random() < 0.8 order by random();

with u as (select d.id as device_id,d.user_id, now() - (random() * INTERVAL '365 days') as last_seen, mod(d.id + floor(random()*100)::bigint, (select count(*) from temp_user_agents)) as ua_id from devices d)
INSERT INTO sessions(device_id, user_id, user_agent, created_at) SELECT device_id, user_id,user_agent, last_seen FROM u join temp_user_agents tua on u.ua_id = tua.id  where random() < 0.8 order by random();

with u as (select d.id as device_id,d.user_id, now() - (random() * INTERVAL '365 days') as last_seen, mod(d.id + floor(random()*100)::bigint, (select count(*) from temp_user_agents)) as ua_id from devices d)
INSERT INTO sessions(device_id, user_id, user_agent, created_at) SELECT device_id, user_id,user_agent, last_seen FROM u join temp_user_agents tua on u.ua_id = tua.id  where random() < 0.8 order by random();

with u as (select d.id as device_id,d.user_id, now() - (random() * INTERVAL '365 days') as last_seen, mod(d.id + floor(random()*100)::bigint, (select count(*) from temp_user_agents)) as ua_id from devices d)
INSERT INTO sessions(device_id, user_id, user_agent, created_at) SELECT device_id, user_id,user_agent, last_seen FROM u join temp_user_agents tua on u.ua_id = tua.id  where random() < 0.8 order by random();

with u as (select d.id as device_id,d.user_id, now() - (random() * INTERVAL '365 days') as last_seen, mod(d.id + floor(random()*100)::bigint, (select count(*) from temp_user_agents)) as ua_id from devices d)
INSERT INTO sessions(device_id, user_id, user_agent, created_at) SELECT device_id, user_id,user_agent, last_seen FROM u join temp_user_agents tua on u.ua_id = tua.id  where random() < 0.8 order by random();

with u as (select d.id as device_id,d.user_id, now() - (random() * INTERVAL '365 days') as last_seen, mod(d.id + floor(random()*100)::bigint, (select count(*) from temp_user_agents)) as ua_id from devices d)
INSERT INTO sessions(device_id, user_id, user_agent, created_at) SELECT device_id, user_id,user_agent, last_seen FROM u join temp_user_agents tua on u.ua_id = tua.id  where random() < 0.8 order by random();


```

```sql
with t as (select sessions.device_id, count(*) as c
           from sessions
           group by sessions.device_id)
select t.c as sessions, count(*)
from t
group by t.c
order by t.c desc;
```