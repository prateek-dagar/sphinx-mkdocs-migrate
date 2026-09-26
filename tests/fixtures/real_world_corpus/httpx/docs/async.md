# Async Support

HTTPX supports standard `asyncio` and `trio`.

```python
import httpx
async with httpx.AsyncClient() as client:
    r = await client.get('https://www.example.com/')
```
