# Pydantic

Data validation using Python type hints.

!!! tip "Performance"
    Pydantic V2 is written in Rust.

=== "Model Definition"
    ```python
    from pydantic import BaseModel
    class User(BaseModel):
        id: int
        name: str
    ```

=== "Dataclass"
    ```python
    from pydantic.dataclasses import dataclass
    @dataclass
    class User:
        id: int
        name: str
    ```
