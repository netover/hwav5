# Migration Guide: aiohttp → httpx

## Why Migrate?

**Benefits:**
- ✅ **-10MB** package size (aiohttp + dependencies)
- ✅ **Better HTTP/2** support
- ✅ **Consistent API** across codebase
- ✅ **Simpler** error handling
- ✅ **Better** type hints support

**Current Usage:**
```bash
grep -r "import aiohttp" resync/ --include="*.py" | wc -l
# Result: 3 files using aiohttp
```

---

## API Comparison

### Basic GET Request

```python
# BEFORE (aiohttp)
import aiohttp

async def fetch_data(url: str) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

# AFTER (httpx)
import httpx

async def fetch_data(url: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()  # No await needed!
```

### POST with JSON

```python
# BEFORE (aiohttp)
async def post_data(url: str, data: dict) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=data) as response:
            return await response.json()

# AFTER (httpx)
async def post_data(url: str, data: dict) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=data)
        return response.json()
```

### With Headers

```python
# BEFORE (aiohttp)
headers = {"Authorization": "Bearer token"}
async with aiohttp.ClientSession(headers=headers) as session:
    async with session.get(url) as response:
        data = await response.json()

# AFTER (httpx)
headers = {"Authorization": "Bearer token"}
async with httpx.AsyncClient(headers=headers) as client:
    response = await client.get(url)
    data = response.json()
```

### Timeout Configuration

```python
# BEFORE (aiohttp)
timeout = aiohttp.ClientTimeout(total=30)
async with aiohttp.ClientSession(timeout=timeout) as session:
    async with session.get(url) as response:
        data = await response.json()

# AFTER (httpx)
timeout = httpx.Timeout(30.0)
async with httpx.AsyncClient(timeout=timeout) as client:
    response = await client.get(url)
    data = response.json()
```

### Error Handling

```python
# BEFORE (aiohttp)
try:
    async with session.get(url) as response:
        response.raise_for_status()
        data = await response.json()
except aiohttp.ClientError as e:
    logger.error(f"Request failed: {e}")

# AFTER (httpx)
try:
    response = await client.get(url)
    response.raise_for_status()
    data = response.json()
except httpx.HTTPStatusError as e:
    logger.error(f"HTTP error: {e}")
except httpx.RequestError as e:
    logger.error(f"Request error: {e}")
```

---

## Files to Migrate

Based on grep results, migrate these files:

### 1. `resync/services/llm_fallback.py` (if using aiohttp)
```python
# Find all aiohttp imports
# Replace with httpx equivalent
```

### 2. `resync/knowledge/ingestion/extractor.py` (if using aiohttp)
```python
# Update HTTP client calls
```

### 3. Any other files using aiohttp
```bash
# Find all files
grep -rn "import aiohttp" resync/

# Check each file and migrate
```

---

## Shared Client Pattern

For better performance, reuse client across requests:

```python
# RECOMMENDED: Shared client
class APIService:
    def __init__(self):
        self._client: httpx.AsyncClient | None = None
    
    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                limits=httpx.Limits(max_connections=100),
            )
        return self._client
    
    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def fetch(self, url: str) -> dict:
        client = await self.get_client()
        response = await client.get(url)
        return response.json()

# Usage
service = APIService()
try:
    data = await service.fetch("https://api.example.com/data")
finally:
    await service.close()
```

---

## Testing Migration

```python
# test_http_migration.py
import pytest
import httpx

@pytest.mark.asyncio
async def test_httpx_get():
    async with httpx.AsyncClient() as client:
        response = await client.get("https://httpbin.org/get")
        assert response.status_code == 200
        data = response.json()
        assert "headers" in data

@pytest.mark.asyncio
async def test_httpx_post():
    async with httpx.AsyncClient() as client:
        payload = {"key": "value"}
        response = await client.post("https://httpbin.org/post", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["json"] == payload
```

---

## Checklist

- [ ] Identify all files using aiohttp
- [ ] Update imports: `aiohttp` → `httpx`
- [ ] Update API calls (remove extra `await` for `.json()`)
- [ ] Update timeout configuration
- [ ] Update error handling
- [ ] Test each migrated file
- [ ] Remove `aiohttp==3.11.11` from requirements.txt
- [ ] Run full test suite
- [ ] Update documentation

---

## Performance Comparison

```python
# Benchmark script
import asyncio
import time

async def benchmark_httpx():
    start = time.time()
    async with httpx.AsyncClient() as client:
        tasks = [client.get("https://httpbin.org/get") for _ in range(100)]
        await asyncio.gather(*tasks)
    print(f"httpx: {time.time() - start:.2f}s")

# Expected: httpx performs similar or better than aiohttp
# Benefit: -10MB dependencies, better HTTP/2 support
```

---

## Rollback Plan

If issues occur:

1. Keep both packages temporarily:
   ```python
   httpx==0.28.1
   aiohttp==3.11.11
   ```

2. Migrate gradually (file by file)

3. Full rollback: revert changes, keep aiohttp

**Risk:** LOW - httpx is battle-tested and widely used

---

**Effort:** 2-4 hours  
**Gain:** -10MB, better HTTP/2, cleaner code  
**Risk:** Minimal (easy rollback)
