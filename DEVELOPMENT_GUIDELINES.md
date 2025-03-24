# Development Guidelines


- `pydantic` is used to parse data coming from the outside of any of the scripts here, e.g., an API, and on success, they are then converted to internal data structures
- `attrs` is used to model our internal data structures, with some basic validation in critical places
