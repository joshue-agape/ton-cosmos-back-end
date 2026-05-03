# Lancer le serveur

```bash
uvicorn app.main:app --reload
```

## Lancer les tests

```bash
pytest
```

### Create the initial migration

```bash
alembic revision --autogenerate -m "init"
```

#### Apply the migration

```bash
alembic upgrade head
```

##### Apply the seeder

```bash
python -m app.seed
```