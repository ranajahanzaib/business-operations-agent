# Security

OpsAgent is an educational local reference implementation, not a production service. It uses synthetic data and binds its development servers to localhost. The default operator and auditor tokens are public demo credentials. Keep the service on localhost; changing the tokens does not make network exposure safe.

Model output is treated as untrusted input. The model receives a bounded registry of read-only tools, never unrestricted SQL, shell, filesystem, or HTTP access. Business writes occur only through server-side approval handlers after actor authorization, immutable proposal integrity checks, current-state validation, and a database transaction. Report vulnerabilities through the process in [`.github/SECURITY.md`](.github/SECURITY.md), not through public issues.
