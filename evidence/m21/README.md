# M21 Evidence

`m21_foundation_summary.json` is generated deterministically by:

```powershell
& .\.venv\Scripts\python.exe .\scripts\validate_m21_foundation.py
```

It records foundation counts and normalized SHA-256 hashes for all M21 configuration contracts. It contains no financial output and does not change the frozen v1 baseline.
