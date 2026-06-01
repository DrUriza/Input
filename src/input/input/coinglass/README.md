# CoinGlass Input

This package fetches raw and semi-raw CoinGlass derivatives market data.

Current derivatives MVP inputs:
- Open interest.
- Funding rate.
- Liquidations.
- Long/short ratio.

UML:
- `coinglass_uml.puml` documents the package classes and dependencies.

This package should not classify, normalize, calculate features or decide trading actions.

Minimal manual check:

```python
from project_trading.input.coinglass.coinglass_client import CoinGlassClient
from project_trading.input.coinglass.coinglass_models import CoinGlassRequest

client = CoinGlassClient()
payload = client.fetch_endpoint(
    CoinGlassRequest(
        endpoint_key="open_interest_ohlc",
        symbol="BTC",
        params={"symbol": "BTC", "interval": "1h", "limit": 24},
    )
)

print(payload.status)
print(payload.source)
print(payload.endpoint)
print(payload.metadata)
print(payload.data)
```
