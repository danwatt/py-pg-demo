# Setup

(This is still a work in progress)

One time I was working on a database that had subtables that contained data related
to interactions with 3rd party services. One of those services chose to use very long
identifiers - longer than a UUID. And, since this table kept track of each interaction
with the third party, we might have multiple rows with the same `third_party_id`.

The query pattern usually was to select the latest row for a given `third_party_id`,
sorted by created_at

Now, we did have a regular b-tree index on this column, but as there were millions of rows
in this table, that index itself was quite large.

```sql
DROP TABLE IF EXISTS external_data;

CREATE table external_data (
  id serial primary key,
  third_party_id varchar NOT NULL,
  created_at timestamp with time zone NOT NULL default now(),
  data varchar not null
);

create index ix_external_data_third_party_id on external_data(third_party_id);
```

<!-- fakeseed -->
```yaml
seed: 42
table: external_data
rows: 10000
fields:
  third_party_id:
    faker: password
    kwargs:
      length: 100
  data:
    faker: paragraph
```