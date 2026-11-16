# Central de Informações Ambientais — Documentação Técnica

## 1. Visão Geral e Arquitetura

A **Central de Informações Ambientais** do EcoMonitor foi projetada para reunir, organizar, normalizar e armazenar em cache local informações atualizadas de fontes jornalísticas, científicas e institucionais sobre queimadas, desmatamento, mudanças climáticas, biodiversidade e fiscalização ambiental, com prioridade geográfica para a **Amazônia Legal** e o **Estado do Pará**.

### Estrutura Modular (Backend FastAPI)

- **`app/models/central.py`**: Entidades SQLModel (`Noticia`, `ArtigoCientifico`, `DadoAmbientalOficial`, `IntegracaoStatus`, `IntegracaoLog`).
- **`app/integrations/`**: Conectores isolados por fonte com validação anti-SSRF, sanitização HTML, proteção contra entidades XML (XXE), timeouts configuráveis e cabeçalho `User-Agent` institucional:
  - `base.py`: cliente HTTP seguro, normalização de URL/DOI, classificação temática e remoção de tags HTML.
  - `rss.py`: leitor de feeds RSS/Atom configuráveis via `config/fontes_rss.json`.
  - `gnews.py`: integração com GNews API v4 para pesquisas em português.
  - `openalex.py`: integração com OpenAlex API (incluindo periódicos indexados no SciELO via `indexed_in:scielo`) e Crossref REST API.
  - `inpe_queimadas.py`: coleta e agregação do consolidado diário oficial de focos de calor (`focos_diario_br_AAAAMMDD.csv`) do servidor `dataserver-coids.inpe.br`.
  - `terrabrasilis.py`: consulta ao GeoServer WFS do TerraBrasilis/INPE (`deter-amz:deter_amz` e `prodes-legal-amz:yearly_deforestation`) e série histórica consolidada do PRODES.
  - `firms.py`: integração com a API da NASA FIRMS (VIIRS/MODIS).
- **`app/services/central_service.py`**: Orquestração de coletas, deduplicação por URL normalizada / DOI / identificador original, busca inteligente (com expansão semântica PT/EN) e painel de saúde.
- **`app/api/v1/endpoints/central.py`**: Endpoints REST em `/api/v1/central/*` protegidos por rate limit (`app/core/ratelimit.py`).
- **`app/cli.py`**: Utilitário de linha de comando para atualização agendada no backend.

---

## 2. Fontes Utilizadas e Limitações Documentadas

### 2.1. Fontes Ativas na v1

| Categoria | Fonte | Autenticação | Periodicidade Recomendada |
|---|---|---|---|
| Notícias | Feeds RSS (Mongabay Brasil, ((o))eco, Agência Brasil, G1 Natureza, Folha Ambiente, Mongabay Global, NASA Earth Observatory) | Pública (sem chave) | A cada 3 horas |
| Notícias | GNews API v4 (`https://gnews.io/api/v4/search`) | Chave `GNEWS_API_KEY` (opcional) | A cada 3 a 6 horas |
| Artigos Científicos | OpenAlex API (`https://api.openalex.org/works`) + indexação SciELO | Pública (Polite Pool via `mailto` ou `OPENALEX_API_KEY` opcional) | Diária (24h) |
| Artigos Científicos | Crossref REST API (`https://api.crossref.org/works`) | Pública (Polite Pool via `mailto`) | Diária (24h) |
| Monitoramento Oficial | INPE — Programa Queimadas (`dataserver-coids.inpe.br`) | Pública | Diária |
| Monitoramento Oficial | INPE — TerraBrasilis DETER e PRODES (GeoServer WFS) | Pública | Diária |
| Monitoramento Oficial | NASA FIRMS API (`firms.modaps.eosdis.nasa.gov`) | Chave `FIRMS_MAP_KEY` (opcional) | Diária |

### 2.2. Distinção Metodológica Obrigatória

O EcoMonitor **não trata** focos de calor, alertas de desmatamento e taxas consolidadas como equivalentes:
1. **Focos de calor (`foco_de_calor`)**: detecções pontuais de calor por sensores orbitais (INPE BDQueimadas / NASA FIRMS), expressas em **unidades de focos**.
2. **Alertas operacionais (`alerta_desmatamento`)**: polígonos de alteração da cobertura florestal detectados pelo sistema **DETER/INPE** para suporte imediato à fiscalização, expressos em **km²**.
3. **Desmatamento consolidado (`desmatamento_consolidado`)**: taxa oficial anual de corte raso calculada pelo **PRODES/INPE**, expressa em **km²**.

### 2.3. Limitações Documentadas (Sem Simulação)

- **MapBiomas Alerta (`https://plataforma.alerta.mapbiomas.org/api/v2/graphql`)**: exige conta cadastrada e token Bearer obtido via mutation `SignIn`. Não é simulada; está documentada no Painel de Saúde da Central com link direto para a documentação oficial.
- **NewsAPI.org**: o plano gratuito (*Developer*) proíbe uso fora de ambiente local de desenvolvimento e impõe atraso de 24h nos artigos. Por conformidade de licença, a Central utiliza RSS direto dos veículos e GNews API opcional.
- **SciELO**: a API ArticleMeta nativa não oferece busca temática full-text; os artigos de periódicos SciELO são consultados via índice aberto do OpenAlex (`indexed_in:scielo`) mantendo a identificação `OpenAlex / SciELO`.

---

## 3. Variáveis de Ambiente e Credenciais

Configure no arquivo `.env` do backend (baseado no `.env.example`):

```ini
CENTRAL_CONTACT_EMAIL=seu-email@dominio.com
OPENALEX_API_KEY=
GNEWS_API_KEY=
FIRMS_MAP_KEY=
CENTRAL_HTTP_TIMEOUT=15
CENTRAL_RATE_LIMIT_PER_MIN=60
CENTRAL_NEWS_REFRESH_HOURS=3
CENTRAL_ARTICLES_REFRESH_HOURS=24
CENTRAL_MONITORING_REFRESH_HOURS=24
CENTRAL_SCHEDULER_ENABLED=false
```

### Como obter as chaves gratuitas opcionais:
1. **OpenAlex (`OPENALEX_API_KEY`)**: crie uma conta gratuita em `https://openalex.org` e gere a chave nas configurações de perfil. Mesmo sem chave, o sistema funciona usando o `CENTRAL_CONTACT_EMAIL` no Polite Pool.
2. **GNews (`GNEWS_API_KEY`)**: cadastre-se gratuitamente em `https://gnews.io/` (plano gratuito: até 100 requisições/dia).
3. **NASA FIRMS (`FIRMS_MAP_KEY`)**: solicite uma `MAP_KEY` gratuita informando seu e-mail em `https://firms.modaps.eosdis.nasa.gov/api/map_key/`.

---

## 4. Como Executar e Atualizar os Dados

### Atualização via Linha de Comando (Agendador / Cron / Task Scheduler)

```bash
# Atualizar todas as fontes (notícias, artigos e monitoramento oficial)
python -m app.cli atualizar --fonte todas

# Atualizar apenas notícias (ex.: a cada 3 horas)
python -m app.cli atualizar --fonte noticias

# Atualizar apenas artigos científicos (ex.: 1x por dia)
python -m app.cli atualizar --fonte artigos

# Atualizar apenas monitoramento oficial do INPE/FIRMS
python -m app.cli atualizar --fonte monitoramento

# Consultar status de saúde via terminal
python -m app.cli status
```

### Endpoints REST Disponíveis

- `GET /api/v1/central/destaques`: página inicial consolidada da Central.
- `GET /api/v1/central/noticias`: listagem paginada com filtros (`categoria`, `termo`, `veiculo`, `data_inicio`, `data_fim`, `ordenar`).
- `GET /api/v1/central/artigos`: biblioteca científica com filtros (`filtro`, `termo`, `ano`, `ordenar`).
- `GET /api/v1/central/monitoramento`: indicadores oficiais do INPE/FIRMS por estado, série PRODES e destaque para o Pará.
- `GET /api/v1/central/busca`: busca inteligente unificada (`q`, `escopo`, `ordenar`, `data_inicio`, `data_fim`).
- `GET /api/v1/central/status`: painel de saúde do sistema e status real de cada integração.
- `POST /api/v1/central/atualizar`: dispara coleta sob demanda (exige autenticação Bearer JWT).

---

## 5. Como Adicionar Novas Fontes Futuramente

1. **Novo Feed RSS (sem alterar código)**:
   Basta adicionar um novo objeto ao arquivo `config/fontes_rss.json` informando `id`, `nome`, `url`, `idioma`, `categoria_padrao` e `"ativo": true`.
2. **Nova API Externa**:
   Crie um módulo em `app/integrations/nova_fonte.py` utilizando `requisitar_http` e `limpar_texto_externo` de `app/integrations/base.py`, registre a chave no `CATALOGO_INTEGRACOES` em `app/services/central_service.py` e chame as funções de persistência deduplicada (`salvar_noticias_deduplicadas`, `salvar_artigos_deduplicados` ou `salvar_dados_ambientais_deduplicados`).
