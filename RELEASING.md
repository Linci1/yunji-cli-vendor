# Release packaging

The vendor package is built from the current committed source tree. Suppliers do not need access to this repository.

```bash
git pull --ff-only origin main
python3 -m unittest discover -s tests -q
python3 tools/security_scan.py
python3 tools/package_release.py
```

Distribute both generated files from `dist/`:

- `yunji-cli-vendor-2.6.1.zip`
- `yunji-cli-vendor-2.6.1.zip.sha256`

The archive is allowlisted, deterministic, and contains no `.git` directory, Git remote, test suite, credentials, local reports, or machine-specific paths. Verify the published checksum before distribution.
