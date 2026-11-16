from datetime import date, datetime, timezone

import pytest

from app.core.ratelimit import limpar_rate_limit
from app.integrations.base import (
    IntegrationError,
    classificar_categoria_noticia,
    limpar_texto_externo,
    normalizar_doi,
    normalizar_url,
    validar_url_externa,
)
from app.integrations.firms import parsear_csv_firms
from app.integrations.gnews import parsear_resposta_gnews
from app.integrations.inpe_queimadas import (
    descobrir_ultimo_csv_diario,
    parsear_csv_focos_inpe,
)
from app.integrations.openalex import (
    parsear_obra_crossref,
    parsear_obra_openalex,
)
from app.integrations.rss import parsear_xml_rss
from app.integrations.terrabrasilis import parsear_geojson_deter
from app.services import central_service

SENHA = "senhaSegura123"


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    limpar_rate_limit()
    yield
    limpar_rate_limit()


def _autenticar(client, email: str = "admin@example.com") -> dict[str, str]:
    client.post(
        "/api/v1/auth/register",
        json={"nome": "Admin Eco", "email": email, "senha": SENHA},
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "senha": SENHA},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_normalizacao_url_e_doi_e_protecao_ssrf():
    url_suja = (
        "https://Brasil.Mongabay.com/2026/11/queimadas-no-para/"
        "?utm_source=twitter&utm_medium=social&id=42#secao"
    )
    assert (
        normalizar_url(url_suja)
        == "https://brasil.mongabay.com/2026/11/queimadas-no-para?id=42"
    )
    assert (
        normalizar_doi("https://doi.org/10.1590/0102-311X001234")
        == "10.1590/0102-311x001234"
    )

    with pytest.raises(IntegrationError):
        validar_url_externa("http://127.0.0.1:8000/admin")

    with pytest.raises(IntegrationError):
        validar_url_externa("http://192.168.1.10/secret")

    with pytest.raises(IntegrationError):
        validar_url_externa("file:///etc/passwd")


def test_sanitizacao_html_e_classificacao():
    texto_sujo = '<p>Focos de <b>incêndio</b> em Santarém &amp; Belém <script>alert(1)</script></p>'
    limpo = limpar_texto_externo(texto_sujo)
    assert "<script>" not in limpo
    assert "<b>" not in limpo
    assert "Santarém & Belém" in limpo
    assert classificar_categoria_noticia(limpo) == "para"
    assert (
        classificar_categoria_noticia("Operação do Ibama aplica multas")
        == "fiscalizacao"
    )


def test_parse_rss_e_bloqueio_xxe():
    xml_xxe = """<?xml version="1.0"?>
    <!DOCTYPE foo [ <!ENTITY xxe SYSTEM "file:///etc/passwd"> ]>
    <rss version="2.0"><channel><item><title>&xxe;</title></item></channel></rss>
    """
    with pytest.raises(IntegrationError):
        parsear_xml_rss(xml_xxe, veiculo="Teste", origem_id="teste")

    xml_valido = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
      <channel>
        <item>
          <title>Queimadas aumentam pressão sobre florestas no Pará</title>
          <link>https://brasil.mongabay.com/2026/11/queimadas-para/?utm_source=rss</link>
          <description><![CDATA[<p>Monitoramento por satélite aponta alta de focos em São Félix do Xingu.</p>]]></description>
          <pubDate>Mon, 16 Nov 2026 10:00:00 GMT</pubDate>
          <media:content url="https://brasil.mongabay.com/img/fogo.jpg" type="image/jpeg" />
        </item>
      </channel>
    </rss>
    """
    itens = parsear_xml_rss(
        xml_valido, veiculo="Mongabay Brasil", origem_id="mongabay_brasil"
    )
    assert len(itens) == 1
    assert itens[0]["veiculo"] == "Mongabay Brasil"
    assert itens[0]["categoria"] == "para"
    assert itens[0]["imagem_url"] == "https://brasil.mongabay.com/img/fogo.jpg"
    assert "utm_source" not in itens[0]["url_normalizada"]


def test_parsers_gnews_openalex_crossref_inpe_deter_firms():
    gnews_payload = {
        "articles": [
            {
                "title": "Desmatamento na Amazônia tem queda segundo PRODES",
                "description": "Dados oficiais do INPE apontam redução.",
                "url": "https://exemplo.com/noticia-prodes",
                "image": "https://exemplo.com/img.jpg",
                "publishedAt": "2026-11-15T14:00:00Z",
                "source": {"name": "Portal Ambiental"},
            }
        ]
    }
    not_gnews = parsear_resposta_gnews(gnews_payload)
    assert len(not_gnews) == 1
    assert not_gnews[0]["categoria"] == "desmatamento"

    obra_oa = {
        "id": "https://openalex.org/W12345",
        "doi": "https://doi.org/10.1590/scielo-amz-2025",
        "display_name": "Forest fire impacts on human health in Pará, Brazilian Amazon",
        "publication_year": 2025,
        "cited_by_count": 19,
        "indexed_in": ["crossref", "scielo"],
        "abstract_inverted_index": {
            "Wildfire": [0],
            "smoke": [1],
            "affects": [2],
            "Pará.": [3],
        },
        "authorships": [
            {
                "author": {"display_name": "Ana Silva"},
                "countries": ["BR"],
                "institutions": [
                    {"display_name": "UFPA", "country_code": "BR"}
                ],
            }
        ],
        "primary_location": {
            "source": {"display_name": "Acta Amazonica"},
            "landing_page_url": "https://scielo.br/acta",
        },
        "topics": [{"display_name": "Amazon Wildfire"}],
    }
    art_oa = parsear_obra_openalex(obra_oa)
    assert art_oa is not None
    assert art_oa["doi"] == "10.1590/scielo-amz-2025"
    assert art_oa["resumo"] == "Wildfire smoke affects Pará."
    assert art_oa["pesquisa_brasileira"] is True
    assert "SciELO" in art_oa["base_origem"]

    obra_cr = {
        "DOI": "10.1000/amaz-deforest-2024",
        "title": ["Deforestation alerts in the Legal Amazon"],
        "author": [{"given": "Carlos", "family": "Souza"}],
        "container-title": ["Remote Sensing of Environment"],
        "published-print": {"date-parts": [[2024, 5, 1]]},
        "is-referenced-by-count": 7,
    }
    art_cr = parsear_obra_crossref(obra_cr)
    assert art_cr is not None
    assert art_cr["ano_publicacao"] == 2024
    assert art_cr["categoria"] == "desmatamento"

    html_inpe = '<a href="focos_diario_br_20261115.csv">15</a><a href="focos_diario_br_20261116.csv">16</a>'
    nome_arq, dt_ref = descobrir_ultimo_csv_diario(html_inpe)
    assert nome_arq == "focos_diario_br_20261116.csv"
    assert dt_ref == date(2026, 11, 16)

    csv_inpe = (
        "id,lat,lon,data_hora_gmt,satelite,municipio,estado,pais,bioma,frp\n"
        "1,-2.88,-50.75,2026-11-16 00:00:00,GOES-19,PORTEL,PARÁ,Brasil,Amazônia,120.0\n"
        "2,-3.32,-50.07,2026-11-16 00:00:00,GOES-19,PORTEL,PARÁ,Brasil,Amazônia,95.0\n"
        "3,-3.10,-60.02,2026-11-16 00:00:00,GOES-19,MANAUS,AMAZONAS,Brasil,Amazônia,40.0\n"
    )
    regs_inpe = parsear_csv_focos_inpe(
        csv_inpe, date(2026, 11, 16), "https://dataserver-coids.inpe.br/teste.csv"
    )
    por_id = {r["identificador_original"]: r for r in regs_inpe}
    assert por_id["inpe_focos_uf:2026-11-16:PA"]["valor"] == 2.0
    assert por_id["inpe_focos_uf:2026-11-16:AM"]["valor"] == 1.0
    assert por_id["inpe_focos_pa_mun:2026-11-16:portel"]["municipio"] == "Portel"

    geojson_deter = {
        "features": [
            {
                "properties": {
                    "gid": "9001_curr",
                    "classname": "DESMATAMENTO_CR",
                    "view_date": "2026-10-12",
                    "areamunkm": "1,250",
                    "municipality": "altamira",
                    "uf": "PA",
                    "satellite": "AMAZONIA-1",
                }
            }
        ]
    }
    regs_deter = parsear_geojson_deter(geojson_deter)
    assert len(regs_deter) == 2
    assert any(r["tipo_metrica"] == "alerta_desmatamento" for r in regs_deter)

    csv_firms = "latitude,longitude,acq_date,frp\n-3.5,-52.1,2026-11-16,45.5\n"
    regs_firms = parsear_csv_firms(csv_firms)
    assert len(regs_firms) == 1
    assert regs_firms[0]["estado"] == "PA"


def test_deduplicacao_e_endpoints_da_central(client, session):
    # Insere notícias duplicadas com URL que difere apenas em parâmetros utm
    n1 = {
        "titulo": "Incêndios florestais no Pará exigem força-tarefa",
        "descricao": "Brigadistas atuam no combate aos focos de calor em Altamira e Santarém.",
        "imagem_url": None,
        "veiculo": "((o))eco",
        "origem_integracao": "rss:oeco",
        "url_original": "https://oeco.org.br/reportagens/incendios-para/?utm_source=feed",
        "url_normalizada": "",
        "data_publicacao": datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc),
        "categoria": "para",
        "idioma": "pt",
    }
    n2 = dict(
        n1,
        url_original="https://oeco.org.br/reportagens/incendios-para/?utm_medium=social",
        imagem_url="https://oeco.org.br/img/capa.jpg",
    )
    inseridas = central_service.salvar_noticias_deduplicadas(session, [n1, n2])
    assert inseridas == 1

    # Segunda chamada com a mesma notícia apenas atualiza imagem/coleta sem duplicar
    inseridas_novamente = central_service.salvar_noticias_deduplicadas(
        session, [n2]
    )
    assert inseridas_novamente == 0

    # Artigos duplicados pelo mesmo DOI
    a1 = {
        "titulo": "Impacts of Amazon wildfires on respiratory health in Pará",
        "autores": "Maria Costa, João Santos",
        "instituicao_ou_periodico": "Cadernos de Saúde Pública",
        "ano_publicacao": 2025,
        "resumo": "Estudo sobre impactos das queimadas na saúde humana na Amazônia.",
        "palavras_chave": "queimadas, saúde humana, Pará, Amazônia",
        "doi": "10.1590/0102-311x2025",
        "identificador_unico": "doi:10.1590/0102-311x2025",
        "url_original": "https://doi.org/10.1590/0102-311x2025",
        "base_origem": "OpenAlex / SciELO",
        "categoria": "queimadas",
        "citacoes": 12,
        "pesquisa_brasileira": True,
    }
    assert central_service.salvar_artigos_deduplicados(session, [a1, a1]) == 1

    # Testa GET /api/v1/central/noticias
    resp_not = client.get(
        "/api/v1/central/noticias", params={"categoria": "para"}
    )
    assert resp_not.status_code == 200
    dados_not = resp_not.json()
    assert dados_not["total"] == 1
    assert dados_not["items"][0]["veiculo"] == "((o))eco"
    assert dados_not["items"][0]["coletado_em"]

    # Testa validação de período inválido em notícias
    resp_inv = client.get(
        "/api/v1/central/noticias",
        params={"data_inicio": "2026-12-01", "data_fim": "2026-11-01"},
    )
    assert resp_inv.status_code == 400

    # Testa GET /api/v1/central/artigos
    resp_art = client.get(
        "/api/v1/central/artigos", params={"filtro": "brasileiras"}
    )
    assert resp_art.status_code == 200
    assert resp_art.json()["total"] == 1
    assert resp_art.json()["items"][0]["doi"] == "10.1590/0102-311x2025"

    # Testa GET /api/v1/central/monitoramento (inclui série PRODES e distinção metodológica)
    resp_mon = client.get(
        "/api/v1/central/monitoramento", params={"estado": "PA"}
    )
    assert resp_mon.status_code == 200
    dados_mon = resp_mon.json()
    assert dados_mon["prodes_para_ultimo_ano_km2"] > 0
    assert "não equivalentes" in dados_mon["nota_metodologica"]
    assert all(r["estado"] == "PA" for r in dados_mon["registros_recentes"])

    # Testa GET /api/v1/central/destaques
    resp_dest = client.get("/api/v1/central/destaques")
    assert resp_dest.status_code == 200
    assert resp_dest.json()["total_noticias"] == 1
    assert resp_dest.json()["total_artigos"] == 1

    # Testa GET /api/v1/central/busca (Mecanismo de busca inteligente)
    resp_busca = client.get(
        "/api/v1/central/busca",
        params={"q": "Queimadas no Pará", "escopo": "todas"},
    )
    assert resp_busca.status_code == 200
    dados_busca = resp_busca.json()
    assert dados_busca["total"] >= 2
    assert dados_busca["total_noticias"] >= 1
    assert dados_busca["total_artigos"] >= 1

    # Testa GET /api/v1/central/status (Painel de saúde)
    resp_status = client.get("/api/v1/central/status")
    assert resp_status.status_code == 200
    dados_status = resp_status.json()
    assert dados_status["status_backend"] == "online"
    assert len(dados_status["integracoes"]) >= 6
    assert len(dados_status["fontes_documentadas_limitacoes"]) >= 2


def test_endpoint_atualizar_exige_autenticacao_e_usa_mock(client, monkeypatch):
    # Sem token -> 401
    assert client.post("/api/v1/central/atualizar").status_code == 401

    monkeypatch.setattr(
        "app.services.central_service.coletar_feed_rss",
        lambda fonte, limite=18: [
            {
                "titulo": f"Notícia de {fonte.get('nome')}",
                "descricao": "Monitoramento ambiental na Amazônia Legal.",
                "imagem_url": None,
                "veiculo": fonte.get("nome", "RSS"),
                "origem_integracao": f"rss:{fonte.get('id')}",
                "url_original": f"https://exemplo.org/{fonte.get('id')}",
                "url_normalizada": f"https://exemplo.org/{fonte.get('id')}",
                "data_publicacao": datetime.now(timezone.utc),
                "categoria": "amazonia",
                "idioma": "pt",
            }
        ],
    )

    headers = _autenticar(client)
    resp = client.post(
        "/api/v1/central/atualizar",
        params={"escopo": "noticias"},
        headers=headers,
    )
    assert resp.status_code == 200
    corpo = resp.json()
    assert corpo["escopo"] == "noticias"
    assert corpo["noticias_novas"] >= 1


def test_rate_limit_protege_endpoints_da_central(client, monkeypatch):
    monkeypatch.setattr(
        "app.core.ratelimit.settings.CENTRAL_RATE_LIMIT_PER_MIN", 3
    )
    limpar_rate_limit()

    assert client.get("/api/v1/central/status").status_code == 200
    assert client.get("/api/v1/central/status").status_code == 200
    assert client.get("/api/v1/central/status").status_code == 200
    bloqueado = client.get("/api/v1/central/status")
    assert bloqueado.status_code == 429
