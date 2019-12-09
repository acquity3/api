# Acquity: Back-End

## Setup
Install Python 3.7. Use `pyenv` (https://github.com/pyenv/pyenv) to make life easy
```
curl https://pyenv.run | bash
pyenv install 3.7
pyenv local 3.7
```
Install Poetry (https://poetry.eustace.io), version 1.0.0a5
```
curl -sSL https://raw.githubusercontent.com/sdispater/poetry/master/get-poetry.py | env POETRY_VERSION=1.0.0a5 python
```
Install dependencies
```
poetry install
```
Setup/reset database (install Postgres first)
```
./setup_db.sh
./run_migrations.sh
./run_seeds.sh
```
Add environment variables from the default values
```
cp .env.default .env
```
## Run app
```
./launch.sh
```

## Test
```
./test.sh
```

## Lint
Auto-fix: `./lint_fix.sh`

Check (is run in CI): `./lint.sh`

## Database migrations
Generate migrations: `./generate_migration.sh "Change foo"`

Run migrations: `./run_migrations.sh`
