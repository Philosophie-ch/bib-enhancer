# Development Guidelines


- `pydantic` is used to parse data coming from the outside of any of the scripts here, e.g., an API, and on success, they are then converted to internal data structures
- `attrs` is used to model our internal data structures, with some basic validation in critical places
- `pytest` is used for testing
- `mypy` is used for static type checking
- `black` is used for code formatting


## Testing

- Tests are written in the `tests` directory
- Tests are run with `poetry run pytest`
- Tests that depend on external APIs are marked with "external" and are skipped by default. To run them, use `poetry run pytest -m external`. They can be found in the `tests/external` directory