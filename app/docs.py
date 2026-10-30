from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

RAPIDOC_HTML = """<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>EcoMonitor API — Documentação</title>
  <script type="module"
    src="https://cdn.jsdelivr.net/npm/rapidoc@12.0.0/dist/rapidoc-min.js">
  </script>
  <style>
    html, body { margin: 0; padding: 0; height: 100%; }
    rapi-doc { height: 100vh; }
    noscript { display: block; padding: 2rem; font-family: sans-serif; }
  </style>
</head>
<body>
  <noscript>
    A documentação interativa requer JavaScript.
    <a href="/swagger">Abrir Swagger UI</a> ou
    <a href="/openapi.json">baixar o OpenAPI JSON</a>.
  </noscript>
  <rapi-doc
    spec-url="/openapi.json"
    theme="light"
    render-style="read"
    schema-style="table"
    default-schema-tab="example"
    show-header="true"
    show-info="true"
    show-components="false"
    allow-try="true"
    allow-authentication="true"
    persist-auth="true"
    show-method-in-nav-bar="as-colored-block"
    primary-color="#15803d"
    font-size="default"
  ></rapi-doc>
</body>
</html>
"""


@router.get(
    "/docs",
    include_in_schema=False,
    response_class=HTMLResponse,
    summary="Documentação interativa (RapiDoc)",
)
def rapidoc_docs() -> HTMLResponse:
    """Serve a interface RapiDoc apontando para o OpenAPI da API."""
    return HTMLResponse(RAPIDOC_HTML)
