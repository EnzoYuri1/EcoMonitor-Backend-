import argparse
import json
import sys

from sqlmodel import Session

from app.db.session import create_db_and_tables, engine
from app.services import central_service


def _cmd_atualizar(escopo: str) -> int:
    create_db_and_tables()
    with Session(engine) as session:
        resultado = central_service.executar_atualizacao_central(
            session, escopo=escopo
        )
        resumo = {
            "escopo": resultado.escopo,
            "executado_em": resultado.executado_em.isoformat(),
            "noticias_novas": resultado.noticias_novas,
            "artigos_novos": resultado.artigos_novos,
            "indicadores_atualizados": resultado.indicadores_atualizados,
            "integracoes": [
                {
                    "chave": i.chave,
                    "status": i.status,
                    "itens": i.total_itens_ultima_coleta,
                    "mensagem": i.mensagem,
                }
                for i in resultado.integracoes
            ],
        }
        print(json.dumps(resumo, ensure_ascii=False, indent=2))
    return 0


def _cmd_status() -> int:
    create_db_and_tables()
    with Session(engine) as session:
        saude = central_service.obter_painel_saude(session)
        print(
            json.dumps(
                saude.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description="Utilitário de linha de comando e atualização agendada do EcoMonitor.",
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    p_atu = sub.add_parser(
        "atualizar",
        help="Executa a atualização de dados da Central de Informações Ambientais.",
    )
    p_atu.add_argument(
        "--fonte",
        choices=("todas", "noticias", "artigos", "monitoramento"),
        default="todas",
        help="Módulo a atualizar (padrão: todas).",
    )

    sub.add_parser(
        "status",
        help="Exibe o painel de saúde e o status das integrações externas.",
    )

    args = parser.parse_args(argv)
    if args.comando == "atualizar":
        return _cmd_atualizar(args.fonte)
    if args.comando == "status":
        return _cmd_status()
    return 1


if __name__ == "__main__":
    sys.exit(main())
