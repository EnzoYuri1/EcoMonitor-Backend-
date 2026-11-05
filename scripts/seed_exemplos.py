"""Cadastra ocorrências fictícias para demonstração do EcoMonitor.

Os registros são vinculados a um usuário existente e identificados pelo
prefixo ``[exemplo]`` na descrição, permitindo removê-los depois sem afetar
as ocorrências reais.

Uso (a partir da raiz do backend):

    .\\.venv\\Scripts\\python.exe scripts\\seed_exemplos.py
    .\\.venv\\Scripts\\python.exe scripts\\seed_exemplos.py --limpar
    .\\.venv\\Scripts\\python.exe scripts\\seed_exemplos.py --recriar
"""

from __future__ import annotations

import argparse
import random
import sys
from calendar import monthrange
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from sqlmodel import Session, func, select  # noqa: E402

from app.db.session import engine  # noqa: E402
from app.models import Ocorrencia, TipoOcorrencia, User  # noqa: E402

MARCADOR = "[exemplo]"
TOTAL_POR_TIPO = 20
USUARIO_PADRAO_ID = 2
SEMENTE = 20261104

MUNICIPIOS = [
    ("Sinop", "MT", -11.8642, -55.5025),
    ("Cuiabá", "MT", -15.6014, -56.0979),
    ("Sorriso", "MT", -12.5456, -55.7111),
    ("Rondonópolis", "MT", -16.4708, -54.6356),
    ("Barra do Garças", "MT", -15.8900, -52.2567),
    ("Alta Floresta", "MT", -9.8756, -56.0861),
    ("Tangará da Serra", "MT", -14.6222, -57.4936),
    ("Santarém", "PA", -2.4436, -54.7083),
    ("Marabá", "PA", -5.3686, -49.1178),
    ("Altamira", "PA", -3.2033, -52.2108),
    ("Novo Progresso", "PA", -7.1478, -55.3811),
    ("São Félix do Xingu", "PA", -6.6422, -51.9950),
    ("Manaus", "AM", -3.1190, -60.0217),
    ("Parintins", "AM", -2.6283, -56.7358),
    ("Itacoatiara", "AM", -3.1431, -58.4442),
    ("Lábrea", "AM", -7.2644, -64.7947),
    ("Humaitá", "AM", -7.5161, -63.0311),
]

DESCRICOES_QUEIMADA = [
    "Foco de calor com fumaça visível próximo à área rural",
    "Queimada de pequeno porte em pastagem",
    "Incêndio em vegetação nativa às margens da rodovia",
    "Foco de queimada identificado por monitoramento",
    "Queimada em área de cerrado com propagação rápida",
]

DESCRICOES_DESMATAMENTO = [
    "Área com remoção recente de vegetação nativa",
    "Desmatamento em área de transição próximo ao igarapé",
    "Corte raso identificado em propriedade rural",
    "Supressão de vegetação com solo exposto",
    "Desmatamento em área de floresta com acesso por estrada",
]


def _data_no_mes(hoje: date, meses_atras: int, dia_base: int) -> date:
    """Monta uma data dentro do mês informado, nunca posterior a hoje."""
    total_meses = hoje.year * 12 + (hoje.month - 1) - meses_atras
    ano, mes_zero = divmod(total_meses, 12)
    mes = mes_zero + 1
    ultimo_dia = monthrange(ano, mes)[1]
    dia = min(max(dia_base, 1), ultimo_dia)
    candidata = date(ano, mes, dia)
    return min(candidata, hoje)


def _datas_distribuidas(hoje: date, quantidade: int) -> list[date]:
    """Distribui as datas entre os últimos 12 meses."""
    datas = []
    for indice in range(quantidade):
        meses_atras = indice % 12
        dia_base = 1 + ((indice * 7) % 27)
        datas.append(_data_no_mes(hoje, meses_atras, dia_base))
    return datas


def _descricao(tipo: TipoOcorrencia, municipio: str, uf: str, indice: int) -> str:
    if tipo is TipoOcorrencia.QUEIMADA:
        contexto = DESCRICOES_QUEIMADA[indice % len(DESCRICOES_QUEIMADA)]
    else:
        contexto = DESCRICOES_DESMATAMENTO[indice % len(DESCRICOES_DESMATAMENTO)]

    return f"{MARCADOR} {contexto} em {municipio}/{uf}."


def _coordenadas(
    latitude: float,
    longitude: float,
    rng: random.Random,
) -> tuple[float, float]:
    """Aplica um pequeno deslocamento para variar os marcadores."""
    return (
        round(latitude + rng.uniform(-0.12, 0.12), 4),
        round(longitude + rng.uniform(-0.12, 0.12), 4),
    )


def _gerar_ocorrencias(hoje: date, usuario_id: int) -> list[Ocorrencia]:
    rng = random.Random(SEMENTE)
    registros = []

    for tipo in (TipoOcorrencia.QUEIMADA, TipoOcorrencia.DESMATAMENTO):
        datas = _datas_distribuidas(hoje, TOTAL_POR_TIPO)
        municipios = MUNICIPIOS[:]
        rng.shuffle(municipios)

        for indice, data_ocorrencia in enumerate(datas):
            municipio, uf, latitude, longitude = municipios[
                indice % len(municipios)
            ]
            lat, lon = _coordenadas(latitude, longitude, rng)

            registros.append(
                Ocorrencia(
                    tipo=tipo,
                    municipio=municipio,
                    estado=uf,
                    descricao=_descricao(tipo, municipio, uf, indice),
                    latitude=lat,
                    longitude=lon,
                    data_ocorrencia=data_ocorrencia,
                    created_by=usuario_id,
                )
            )

    return registros


def _contar_exemplos(session: Session) -> int:
    statement = (
        select(func.count())
        .select_from(Ocorrencia)
        .where(Ocorrencia.descricao.like(f"{MARCADOR}%"))
    )
    return session.exec(statement).one()


def _limpar_exemplos(session: Session) -> int:
    registros = session.exec(
        select(Ocorrencia).where(Ocorrencia.descricao.like(f"{MARCADOR}%"))
    ).all()

    for registro in registros:
        session.delete(registro)

    session.commit()
    return len(registros)


def _resumo(session: Session) -> tuple[int, int, int]:
    total = session.exec(select(func.count()).select_from(Ocorrencia)).one()
    queimadas = session.exec(
        select(func.count())
        .select_from(Ocorrencia)
        .where(Ocorrencia.tipo == TipoOcorrencia.QUEIMADA)
    ).one()
    desmatamentos = session.exec(
        select(func.count())
        .select_from(Ocorrencia)
        .where(Ocorrencia.tipo == TipoOcorrencia.DESMATAMENTO)
    ).one()
    return total, queimadas, desmatamentos


def _validar_usuario(session: Session, usuario_id: int) -> User:
    usuario = session.get(User, usuario_id)
    if usuario is None:
        raise SystemExit(
            f"Usuário id={usuario_id} não encontrado. "
            "Informe outro com --usuario-id."
        )
    return usuario


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Cadastra 40 ocorrências fictícias (20 queimadas e 20 "
            "desmatamentos) para demonstração."
        )
    )
    parser.add_argument(
        "--limpar",
        action="store_true",
        help="Remove somente os registros marcados com [exemplo].",
    )
    parser.add_argument(
        "--recriar",
        action="store_true",
        help="Remove os exemplos existentes e cadastra os 40 novamente.",
    )
    parser.add_argument(
        "--usuario-id",
        type=int,
        default=USUARIO_PADRAO_ID,
        help=f"Usuário responsável (padrão: {USUARIO_PADRAO_ID}).",
    )
    args = parser.parse_args()

    with Session(engine) as session:
        if args.limpar:
            removidos = _limpar_exemplos(session)
            print(f"{removidos} registro(s) de exemplo removido(s).")
            total, queimadas, desmatamentos = _resumo(session)
            print(
                "Banco agora com "
                f"{total} ocorrência(s): {queimadas} queimada(s) e "
                f"{desmatamentos} desmatamento(s)."
            )
            return

        usuario = _validar_usuario(session, args.usuario_id)

        if args.recriar:
            removidos = _limpar_exemplos(session)
            print(f"{removidos} registro(s) de exemplo removido(s) antes da recriação.")

        existentes = _contar_exemplos(session)
        if existentes and not args.recriar:
            print(
                f"Já existem {existentes} registro(s) de exemplo. "
                "Nada foi alterado. Use --recriar para refazer ou "
                "--limpar para remover."
            )
            return

        hoje = date.today()
        registros = _gerar_ocorrencias(hoje, usuario.id)
        session.add_all(registros)
        session.commit()

        total, queimadas, desmatamentos = _resumo(session)
        print(
            f"{len(registros)} ocorrência(s) fictícia(s) cadastrada(s) "
            f"para {usuario.nome} ({usuario.email})."
        )
        print(
            "Banco agora com "
            f"{total} ocorrência(s): {queimadas} queimada(s) e "
            f"{desmatamentos} desmatamento(s)."
        )
        print(f"Use --limpar para remover apenas os registros {MARCADOR}.")


if __name__ == "__main__":
    main()
