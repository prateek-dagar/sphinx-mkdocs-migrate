# Expressions

Polars expressions evaluate lazily.

$$
f(x) = \sum_{i=1}^n x_i^2
$$

```mermaid
graph TD;
    Scan-->Filter;
    Filter-->Select;
```
