from concurrent.futures import ThreadPoolExecutor
import json
import os
import statistics
import time

import requests

BASE_URL = os.getenv("BENCHMARK_BASE_URL", "http://127.0.0.1:8001")
ENDPOINTS = [
    "/health",
    "/api/v1/central/destaques",
    "/api/v1/central/noticias?page=1&page_size=12",
    "/api/v1/central/artigos?page=1&page_size=10",
    "/api/v1/central/monitoramento?estado=PA",
    "/api/v1/central/busca?q=Queimadas%20no%20Par%C3%A1",
    "/api/v1/central/status",
]


def _uma_requisicao(idx: int) -> tuple[bool, float]:
    caminho = ENDPOINTS[idx % len(ENDPOINTS)]
    inicio = time.perf_counter()
    try:
        r = requests.get(f"{BASE_URL}{caminho}", timeout=10)
        lat_ms = (time.perf_counter() - inicio) * 1000.0
        return (r.status_code == 200, lat_ms)
    except Exception:  # noqa: BLE001
        lat_ms = (time.perf_counter() - inicio) * 1000.0
        return (False, lat_ms)


def rodar_cenario(usuarios_simultaneos: int, total_req: int) -> dict:
    inicio_total = time.perf_counter()
    with ThreadPoolExecutor(max_workers=usuarios_simultaneos) as pool:
        resultados = list(pool.map(_uma_requisicao, range(total_req)))
    duracao_s = max(time.perf_counter() - inicio_total, 0.001)

    latencias = sorted(lat for _, lat in resultados)
    erros = sum(1 for ok, _ in resultados if not ok)
    idx_p95 = min(int(len(latencias) * 0.95), len(latencias) - 1)

    return {
        "usuarios_simultaneos": usuarios_simultaneos,
        "total_requisicoes": total_req,
        "media_ms": round(statistics.mean(latencias), 2),
        "p95_ms": round(latencias[idx_p95], 2),
        "max_ms": round(max(latencias), 2),
        "taxa_erros_pct": round((erros / total_req) * 100.0, 2),
        "req_por_segundo": round(total_req / duracao_s, 1),
    }


def main() -> None:
    cenarios = [
        rodar_cenario(10, 40),
        rodar_cenario(25, 75),
        rodar_cenario(50, 150),
        rodar_cenario(100, 200),
    ]
    print(json.dumps(cenarios, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
