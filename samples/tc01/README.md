# settings-lite

A tiny settings loader for small Python services.

## Usage

```python
from settings import get_setting

port = get_setting("port")
```

## Error handling

`get_setting(name)` raises `KeyError` if the setting does not exist.

## Listing settings

`list_settings()` returns the names of all settings.
