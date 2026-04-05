# ravelry-openapi-specification

An OpenAPI 3.1 specification for the [Ravelry API](https://www.ravelry.com/api), generated from the official HTML documentation.

[Swagger UI](https://cxd309.github.io/ravelry-openapi-specification/swagger.html) · [ReDoc](https://cxd309.github.io/ravelry-openapi-specification/redoc.html)

## Prerequisites

- [uv](https://docs.astral.sh/uv/)
- [simple-file-server](https://github.com/cxd309/simple-file-server)

```bash
go install github.com/cxd309/simple-file-server@latest
```

## Generate

Parse `api_documentation.html` and write `docs/openapi.json`:

```bash
make generate
```

## Serve

Browse the spec locally, emulating the GitHub Pages URL structure:

```bash
make serve
# -> http://localhost:8081/ravelry-openapi-specification/swagger.html
# -> http://localhost:8081/ravelry-openapi-specification/redoc.html
```

## Project structure

```
api_documentation.html  # source: Ravelry API HTML docs
main.py                 # entry point
ravelry/
    parser.py           # HTML -> structured data
    generator.py        # structured data -> OpenAPI 3.1 spec
docs/
    openapi.json        # generated output
    swagger.html        # Swagger UI
    redoc.html          # ReDoc
```
