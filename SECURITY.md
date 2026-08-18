# Security policy

## Supported versions

Koguard has not published `0.1.0` yet. Security fixes currently target the latest `dev` branch and the
next release candidate only. A supported-version table will replace this statement after the first public
release.

## Reporting a vulnerability

Do not disclose a suspected vulnerability, private corpus text, credentials, or exploit details in a public
issue. Use the repository's **Security → Report a vulnerability** flow to open a private GitHub Security
Advisory:

<https://github.com/skgur07/Koguard/security/advisories/new>

Include the affected version or commit, minimal reproduction, impact, and whether the report contains
sensitive user text. You should receive an acknowledgement within seven days. A fix timeline depends on
severity and reproducibility; the maintainer will coordinate disclosure after a patch is available.

Koguard's runtime does not use the network and does not log input text by default. Reports that demonstrate a
length-limit bypass, unexpected data disclosure, unbounded matcher path, artifact contamination, or unsafe
Unicode handling are in scope.
