# Setup schema

<!-- schemadiagram -->
```sql
-- Drop child first to avoid FK issues, then parent
DROP TABLE IF EXISTS pets;
DROP TABLE IF EXISTS people;

-- People table
CREATE TABLE people (
  id serial PRIMARY KEY,
  name text NOT NULL,
  age int
);

-- Pets table with FK to people
CREATE TABLE pets (
  id serial PRIMARY KEY,
  person_id int NOT NULL REFERENCES people(id) ON DELETE CASCADE,
  name text NOT NULL,
  species text NOT NULL
);
```

<!-- fakeseed -->
```yaml
seed: 42
table: people
rows: 10
fields:
  name:
    faker: first_name
  age:
    faker: random_int
    kwargs:
      min: 1
      max: 50
```

<!-- fakeseed -->
```yaml
# Insert N fake pets, linking to existing people
seed: 42
table: pets
rows: 20
fields:
  person_id:
    ref: { table: people, column: id }
  name:
    faker: first_name
  species:
    oneof: ["cat", "dog", "penguin"]
```
