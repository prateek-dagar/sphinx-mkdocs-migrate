# Polars User Guide

Blazingly fast DataFrames in Python and Rust.

!!! note "Performance"
    Polars uses Apache Arrow memory model.

=== "Python"
    ```python
    import polars as pl
    df = pl.DataFrame({"a": [1, 2, 3]})
    ```

=== "Rust"
    ```rust
    use polars::prelude::*;
    let df = df!("a" => &[1, 2, 3])?;
    ```
