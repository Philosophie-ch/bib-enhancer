# Python Style Guide

An opinionated set of Python standards centered on strict typing, immutability, and functional architecture.

## Type Safety

Enforce strict type safety using mypy with the `--strict` flag.

### Requirements

- All functions must have complete type annotations for parameters and return values
- No use of `Any` type unless justified with a comment explaining why and peer-reviewed
- No use of `cast()` calls
- No use of `# type: ignore` comments unless justified with a comment explaining why and peer-reviewed
- All type errors must be resolved properly through type narrowing or proper type design

### Type Narrowing

When dealing with union types, use explicit type checking:

```python
value = record.field
if isinstance(value, ExpectedType):
    result = value.attribute  # Type narrowed, safe to access
```

### Preserve Type Safety - Never Convert to Dicts

**CRITICAL**: Do not convert typed objects to dictionaries to access attributes. This loses all type safety.

```python
# NEVER DO THIS - loses type safety
data = record.model_dump()  # or __dict__ or dict(record)
name = data.get("name", "")  # Type checker cannot verify this

# ALWAYS DO THIS - preserves type safety
name_field = record.name
if isinstance(name_field, NameType):
    name = name_field.value
else:
    name = ""
```

Reasons:
- Dictionary access bypasses type checking completely
- Typos in keys are not caught by mypy
- Attribute renames do not update dictionary keys automatically
- Type narrowing is lost, leading to runtime errors

Always access attributes directly and use isinstance() for type narrowing.

### Forward References

Use `TYPE_CHECKING` for imports that are only needed for type annotations to avoid circular imports:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mypackage.models import SomeModel
```

## Pydantic at the Boundaries

Use Pydantic models exclusively at system boundaries - the primary side (user input, CLI arguments, configuration files) and the secondary side (API responses, database rows, external service payloads). Pydantic's validation overhead is justified here because this is where untrusted data enters the system.

```python
# Primary side: parsing user input
class CreateUserRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    name: str
    email: EmailStr

# Secondary side: parsing an external API response
class ExternalPayload(BaseModel):
    model_config = ConfigDict(strict=True)
    id: int
    status: str
```

Once data crosses a boundary and is validated, convert it into lightweight internal representations (e.g., frozen attrs classes, named tuples, or plain typed values) for all further processing. Do not pass Pydantic models through core business logic:

```python
# At the boundary: validate, then convert
request = CreateUserRequest.model_validate(raw_input)
user = User(name=request.name, email=request.email)  # attrs/dataclass

# Inside the core: work with lightweight, validated data
def process_user(user: User) -> Result:
    ...
```

This approach gives you:
- **Fail-fast guarantees** - malformed data is rejected immediately at the edges
- **Runtime consistency** - everything inside the core is already validated
- **No hidden overhead** - Pydantic validation runs once, not on every function call
- **Clean separation** - boundary concerns (parsing, serialization) stay out of business logic

## Data Structures and Idioms

The following patterns are preferred for immutability and clarity:

1. **Prefer tuples over lists** for sequences that do not need mutation
   ```python
   items = tuple(process(x) for x in source)  # Preferred
   items = [process(x) for x in source]       # Avoid
   ```

2. **Prefer `FrozenSet` over `Set`** for immutable unique collections

3. **Prefer comprehensions over explicit loops** when the logic is straightforward
   ```python
   # Preferred
   results = {key: frozenset(items) for key, items in mapping.items()}

   # Avoid
   results = {}
   for key, items in mapping.items():
       results[key] = frozenset(items)
   ```

4. **Use set operations** for collection operations
   ```python
   # Preferred
   candidates.update(index[key])

   # Avoid
   for item in index[key]:
       candidates.add(item)
   ```

5. **Use `frozen=True` and `slots=True`** on data classes for immutability and memory efficiency (e.g., `attrs.define(frozen=True, slots=True)` or `@dataclass(frozen=True, slots=True)`)

6. **Use `Enum` or `StrEnum` for closed sets of values** — this enables exhaustive `match` checking via mypy's `exhaustive-match` error code
   ```python
   from enum import StrEnum

   class Status(StrEnum):
       ACTIVE = "active"
       INACTIVE = "inactive"
       PENDING = "pending"

   def handle(status: Status) -> str:
       match status:
           case Status.ACTIVE: return "go"
           case Status.INACTIVE: return "stop"
           case Status.PENDING: return "wait"
           # mypy error if a case is missing
   ```

## Performance

### Avoid N+1 Problems

Never perform I/O inside a loop when a batch operation is available. This is the single most common performance mistake:

```python
# NEVER DO THIS - N+1: one query per item
results = tuple(fetch(item_id) for item_id in item_ids)

# ALWAYS DO THIS - single batch call
results = batch_fetch(item_ids)
```

The same applies to HTTP calls, file reads, and any other I/O. If you are calling an external service per item, look for a batch endpoint or gather inputs first.

### Use Appropriate Data Structures for Lookups

Choose data structures based on access patterns:

```python
# Membership testing: use a set, not a list
valid_ids: frozenset[int] = frozenset(load_valid_ids())
if item_id in valid_ids:  # O(1)
    ...

# Keyed access: use a dict, not linear search
users_by_id: dict[int, User] = {u.id: u for u in users}
user = users_by_id[target_id]  # O(1)

# Avoid: scanning a list for every lookup — O(n) per call
user = next(u for u in users if u.id == target_id)
```

### Avoid Nested Loops over Large Collections

Nested iteration over two large collections is O(n*m). Restructure with index lookups:

```python
# Avoid - O(n * m)
matched = tuple(
    (o, p)
    for o in orders
    for p in products
    if o.product_id == p.id
)

# Preferred - O(n + m): build an index, then join
products_by_id = {p.id: p for p in products}
matched = tuple(
    (o, products_by_id[o.product_id])
    for o in orders
    if o.product_id in products_by_id
)
```

### Prefer Generators for Large Pipelines

When processing large datasets, use generator expressions to keep memory usage constant. Each item flows through the entire chain before the next is pulled:

```python
# Constant memory - items processed one at a time
validated = (validate(item) for item in raw_items)
transformed = (transform(item) for item in validated)
write_output(transformed)

# Avoid - loads entire dataset into memory at each step
validated = [validate(item) for item in raw_items]
transformed = [transform(item) for item in validated]
write_output(transformed)
```

See the [Streaming with Chained Generators](#streaming-with-chained-generators) subsection for the full pattern.

### Profile Before Optimizing

Do not guess at bottlenecks. Measure first with `cProfile` or `line_profiler`, then optimize the hot path:

```bash
python -m cProfile -s cumtime my_script.py
```

## Functional Architecture (Hexagonal / Ports & Adapters)

Follow hexagonal architecture principles using functional programming. The key insight: **hexagonal architecture doesn't require OOP** - function signatures serve as interfaces.

### Core Principles

1. **Business logic doesn't depend on I/O details**
2. **Dependencies point inward** - concrete implementations depend on abstract interfaces
3. **Ports define what you need** - type aliases for function signatures
4. **Adapters provide how** - concrete implementations matching those signatures

### Defining Ports (Abstract Interfaces)

Use type aliases to define the "shape" of functions your core logic needs:

```python
from typing import Callable, Generator

# Port: what the core logic needs (abstract)
type TItemReader[ReaderIn] = Callable[[ReaderIn], Generator[Item, None, None]]
type TItemWriter[WriterIn] = Callable[[Generator[Item, None, None], WriterIn], None]
type TTransform = Callable[[str], str]
```

The type signature **is** the contract. Any function matching that signature can be injected.

### Implementing Adapters (Concrete Implementations)

Create concrete functions that satisfy the port signatures:

```python
# Adapter: filesystem implementation
def read_from_filesystem(input_dirname: str) -> Generator[Item, None, None]:
    for file_name in os.listdir(input_dirname):
        yield read_file(os.path.join(input_dirname, file_name))

# Adapter: database implementation (alternative)
def read_from_database(connection_string: str) -> Generator[Item, None, None]:
    # ... database-specific logic
```

### Abstract Process Functions

Write core logic that accepts injected functions:

```python
def abstract_process[I, O](
    reader: TItemReader[I],
    reader_input: I,
    transform: TTransform,
    writer: TItemWriter[O],
    writer_input: O,
) -> None:
    """Core business logic - knows nothing about filesystems, databases, etc."""
    raw_items = reader(reader_input)
    processed = (transform(item) for item in raw_items)
    writer(processed, writer_input)
```

### Wiring: Injecting Dependencies

Create concrete entry points that wire everything together:

```python
def main_filesystem(input_dir: str, output_dir: str) -> None:
    """Concrete implementation using filesystem adapters."""
    abstract_process(
        reader=read_from_filesystem,
        reader_input=input_dir,
        transform=my_transform_function,
        writer=write_to_filesystem,
        writer_input=output_dir,
    )
```

### Benefits Over OOP-Style Dependency Injection

| Aspect | FP Style | OOP Style |
|--------|----------|-----------|
| Interface definition | Type alias | Abstract class/Protocol |
| Boilerplate | Minimal | Class definitions, `__init__`, etc. |
| Testing | Pass mock functions directly | Mock objects, DI frameworks |
| Composition | Natural function composition | Decorator pattern, etc. |
| State | Explicit (parameters) | Hidden in `self` |

### When to Use This Pattern

Use functional hexagonal architecture when:

- Processing pipelines (read → transform → write)
- Multiple I/O backends are possible (filesystem, database, API)
- Business logic should be testable in isolation
- You want to swap implementations without changing core logic

### Example: Complete Module Structure

```python
# types.py - Port definitions
type TValidate = Callable[[str], str]
type TSanitize = Callable[[str], str]
type TItemReader[In] = Callable[[In], Generator[Item, None, None]]
type TItemWriter[Out] = Callable[[Generator[Item, None, None], Out], None]

# core.py - Abstract process (pure business logic)
def process_content(
    content: str,
    validate: TValidate,
    sanitize: TSanitize,
) -> str:
    return sanitize(validate(content))

def abstract_process[I, O](...) -> None:
    # Orchestration logic

# adapters/filesystem.py - Filesystem adapter
def filesystem_reader(dirname: str) -> Generator[Item, None, None]: ...
def filesystem_writer(items: Generator[Item, None, None], dirname: str) -> None: ...

# adapters/transforms.py - Transform implementations
def regex_validate(content: str) -> str: ...
def html_sanitize(content: str) -> str: ...

# main.py - Wiring
def main_filesystem(input_dir: str, output_dir: str) -> None:
    abstract_process(
        reader=filesystem_reader,
        reader_input=input_dir,
        validate=regex_validate,
        sanitize=html_sanitize,
        writer=filesystem_writer,
        writer_input=output_dir,
    )
```

### Streaming with Chained Generators

This extends the `abstract_process` pattern shown above with multiple chained transformation steps. Each step is lazy - no intermediate lists are allocated - and only the terminal function at the end of the chain triggers evaluation and produces side effects:

```python
from typing import Callable, Generator

type TReader[In] = Callable[[In], Generator[Item, None, None]]
type TTransform = Callable[[Item], Item]
type TToRow = Callable[[Item], str]
type TWriter[Out] = Callable[[Generator[str, None, None], Out], None]

def process_pipeline[I, O](
    reader: TReader[I],
    reader_input: I,
    validate: TTransform,
    transform: TTransform,
    to_row: TToRow,
    writer: TWriter[O],
    writer_output: O,
) -> None:
    raw_items = reader(reader_input)                        # Generator[Item, None, None]
    validated = (validate(item) for item in raw_items)      # lazy
    transformed = (transform(item) for item in validated)   # lazy
    rows = (to_row(item) for item in transformed)           # lazy
    writer(rows, writer_output)                             # terminal: consumes the chain
```

The entire chain evaluates one item at a time, end to end, before pulling the next. This keeps memory usage constant regardless of input size. The terminal function (here `writer`) is the only place where side effects occur - everything upstream is a pure transformation.

This composes naturally with the hexagonal architecture: `reader` and `writer` are adapters, `validate`, `transform`, and `to_row` are injected core functions, and `process_pipeline` is the wiring.

## Code Organization

### Module Structure

- **Types/Ports**: Type aliases defining function signatures (interfaces)
- **Core**: Abstract process functions that accept injected dependencies
- **Adapters**: Concrete implementations for I/O and transformations
- **Main/Wiring**: Entry points that wire adapters into core logic
- **Models**: Define data structures using frozen, slotted classes (e.g., `attrs.define(frozen=True, slots=True)`)
- **No classes** except for simple data containers and index structures

### Function Design

Functions should be:

- **Pure** when possible (no side effects)
- **Small and focused** (single responsibility)
- **Composable** (easy to combine with other functions)
- **Injectable** (accept dependencies as parameters rather than importing them)

### Imports

Group imports in the following order:

1. Standard library imports
2. Third-party library imports
3. Local application imports

Within each group, sort alphabetically.

### Logging over Print

Use the `logging` module for all output beyond throwaway debugging. `print` statements should not appear in committed code.

```python
import logging

logger = logging.getLogger(__name__)

logger.info("Processing %d items", count)
logger.error("Failed to connect to %s", url)
```

## Testing

### Test Requirements

- All new functionality must have corresponding tests
- Tests must pass with `pytest`
- Test coverage should be comprehensive
- Tests should be deterministic and fast

### Test Structure

```python
def test_feature_description() -> None:
    """Brief description of what is being tested."""
    # Arrange
    input_data = create_test_data()

    # Act
    result = function_under_test(input_data)

    # Assert
    assert result == expected_value
```

### Parametrized Tests

Use `pytest.mark.parametrize` for testing multiple cases:

```python
@pytest.mark.parametrize(
    "input_value, expected_output",
    [
        (case1_input, case1_output),
        (case2_input, case2_output),
    ],
)
def test_multiple_cases(input_value: str, expected_output: str) -> None:
    assert transform(input_value) == expected_output
```

## Documentation

### Docstrings

All public functions and classes must have docstrings following this format:

```python
def function_name(param1: Type1, param2: Type2) -> ReturnType:
    """Brief one-line description.

    Longer description if needed, explaining the purpose and behavior.

    Args:
        param1: Description of first parameter
        param2: Description of second parameter

    Returns:
        Description of return value
    """
```

### Comments

- Use comments sparingly - prefer self-documenting code
- Explain **why**, not **what** (the code shows what)
- Update comments when code changes

## Formatting

### General Style

- Follow PEP 8 conventions
- Line length: 88 characters (Black default)
- Use double quotes for strings
- Use trailing commas in multi-line structures

### Function Signatures

For functions with many parameters, format each parameter on its own line:

```python
def complex_function(
    parameter1: Type1,
    parameter2: Type2,
    parameter3: Type3 = default_value,
) -> ReturnType:
    pass
```

## Error Handling

### Type-Safe Error Handling

Handle expected errors explicitly:

```python
# Check conditions and return early
if not valid_input(data):
    return default_value

# Use isinstance for type narrowing
if isinstance(value, ExpectedType):
    process(value)
```

### Avoid Bare Except

Always catch specific exceptions:

```python
# Preferred
try:
    risky_operation()
except ValueError as e:
    handle_value_error(e)

# Avoid
try:
    risky_operation()
except:
    pass
```

## Version Control

### Commit Messages

Follow conventional commits format:

```
type(scope): brief description

Longer explanation if needed.
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`

## Tools

### Required Tools

- `mypy` - Type checking with `--strict` mode
- `pytest` - Testing framework
- A dependency manager such as `poetry`, `uv`, or `pip`

### Running Checks

```bash
# Type checking
mypy .

# Run tests
pytest

# Run specific test file
pytest tests/path/to/test_file.py -v
```

### Suggested `pyproject.toml` Configuration

A strict mypy + Pydantic setup (works with any build backend — Poetry, uv, etc.):

```toml
[tool.mypy]
python_version = "3.13"
strict = true
explicit_package_bases = true
warn_unreachable = true
disallow_any_explicit = true
disallow_any_unimported = true
disallow_any_decorated = true
enable_error_code = [
    "possibly-undefined",
    "redundant-expr",
    "truthy-bool",
    "truthy-iterable",
    "exhaustive-match",
]
mypy_path = "."
plugins = ["pydantic.mypy"]

[tool.pydantic-mypy]
init_forbid_extra = true
init_typed = true
warn_required_dynamic_aliases = true
warn_untyped_fields = true

# Override for third-party libraries that ship without type stubs.
# Add libraries here only when no stubs exist (check typeshed / pypi for *-stubs).
[[tool.mypy.overrides]]
module = [
    "some_untyped_lib",
    "another_untyped_lib",
]
ignore_missing_imports = true
```

## Summary

This guide prioritizes:

1. **Type safety** - Strict mypy compliance without escape hatches
2. **Immutability and clarity** - Tuples, frozensets, frozen data classes, comprehensions over loops
3. **Performance** - Batch I/O, appropriate data structures, generators for constant memory
4. **Testability** - Comprehensive test coverage with fast, deterministic tests

When in doubt, consult existing code in the project for examples of these patterns in practice.
