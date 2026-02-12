# Documentation Standards -- LSTM Autoencoder Anomaly Detection

## Document Inventory

| Document | Path | Audience | Update frequency |
|----------|------|----------|-----------------|
| README | `README.md` | Thesis advisor, reviewers, future maintainers | On major features |
| Installation guide | `docs/installation.md` | Anyone setting up the project | On dependency/infra changes |
| Troubleshooting guide | `docs/troubleshooting.md` | Anyone running the project | On new known issues |
| Troubleshooting journal | `TROUBLESHOOTING_JOURNAL.md` | Developer (historical record) | After every debugging session |
| Environment reference | `.env.example` | Anyone configuring the project | On new env vars |

## Troubleshooting Journal Format

Every debugging session that discovers a root cause gets an entry:

```markdown
### Issue N: [Short descriptive title] (YYYY-MM-DD)

**Symptom:** What the user/system observed (error messages, wrong values, crashes)

**Root cause:** Technical explanation of why it happened

**Fix:** What was changed, with file paths and brief description
- `path/to/file.py` -- description of change
- `config/something.yaml` -- description of change

**Verification:** How the fix was confirmed working
```

Rules:
- Number issues sequentially within each session
- Include exact error messages when available
- Link root cause to specific code/config, not vague descriptions
- Verification must describe a concrete test, not "it works now"

## Terminology Reference

Use consistently across all documentation:

| Correct term | Avoid |
|-------------|-------|
| LSTM Autoencoder | autoencoder model, AE, LSTM-AE |
| reconstruction error | loss (in inference context), prediction error |
| mock service | test service, fake service, simulator |
| fixed_minmax scaler | bounded scaler, fixed scaler, custom scaler |
| anomaly injection | fault injection, chaos testing |
| scrape interval | polling interval (Prometheus context) |
| sampling interval | collection interval (data.yaml context) |
| dev stack | local stack, docker stack |

## Docstring Conventions

Python functions use Google-style docstrings:

```python
def function_name(param1: str, param2: int = 10) -> pd.DataFrame:
    """Short one-line summary.

    Longer description if needed, explaining the why and any
    non-obvious behavior.

    Args:
        param1: Description of param1.
        param2: Description of param2. Defaults to 10.

    Returns:
        Description of the return value.

    Raises:
        ValueError: When param1 is empty.
    """
```

## README Structure

The README should follow this order:
1. Project title and one-line description
2. Architecture diagram (Mermaid or ASCII)
3. Quick start (3-5 commands to get running)
4. Configuration reference (table of config files)
5. Training and inference instructions
6. Anomaly injection testing
7. Project structure (file tree)
8. Tech stack
