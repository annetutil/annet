file_devdb := "annet/annlib/netdev/devdb/data/devdb.json"
file_devdb_gen := "annet/annlib/netdev/devdb/generated/__init__.pyi"

gen_devdb:
    python annet/annlib/netdev/devdb/codegen.py {{file_devdb}} {{file_devdb_gen}}

gen: gen_devdb

fmt:
    ruff format .
    ruff check --select I --fix .

[positional-arguments]
test-pytest *args:
    pytest -vv "$@"

test-fmt:
    ruff format --check .
    ruff check --select I .
    flake8 annet annet_generators

test-types:
    mypy .

test: test-pytest test-types test-fmt
