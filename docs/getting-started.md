# Getting Started

## Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)

## Installation

Clone the repository and install all packages:

```bash
git clone <repo-url>
cd one-ring
uv sync --all-packages
```
## Development

Run all checks (lint, format, typecheck, test):

```bash
just check
```

Serve the documentation locally:

```bash
just docs-serve
```
