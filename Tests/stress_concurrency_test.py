import argparse
import io
import json
import random
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter
from datetime import datetime
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
TESTS_DIR = Path(__file__).resolve().parent
CLIENT_DIR = BASE_DIR / "Client"
SERVER_PATH = BASE_DIR / "Server" / "server.py"
TABLE_PATH = BASE_DIR / "Tables" / "test.csv"
LOG_PATH = TESTS_DIR / "log.txt"
REPORT_PATH = TESTS_DIR / "relatorio_teste_concorrencia.md"
REPORT_MATRIX_PATH = TESTS_DIR / "relatorio_teste_concorrencia_matrix.md"

SQL_PATH = CLIENT_DIR / "sql.py"
SQL_SPEC = importlib.util.spec_from_file_location("client_sql", SQL_PATH)
if SQL_SPEC is None or SQL_SPEC.loader is None:
    raise ImportError(f"Não foi possível carregar o interpretador SQL em {SQL_PATH}")
SQL_MODULE = importlib.util.module_from_spec(SQL_SPEC)
SQL_SPEC.loader.exec_module(SQL_MODULE)
to_client_request = SQL_MODULE.to_client_request


def kill_process_on_port(port=5000):
    """Mata qualquer processo rodando na porta especificada (Windows)"""
    try:
        if sys.platform == "win32":
            subprocess.run(
                f'netstat -ano | findstr :{port}',
                shell=True,
                capture_output=True,
                text=True,
                check=False
            )
            # Tenta matar usando taskkill
            subprocess.run(
                f"for /f \"tokens=5\" %a in ('netstat -ano ^| findstr :{port}') do taskkill /PID %a /F",
                shell=True,
                capture_output=True,
                check=False
            )
    except Exception:
        pass


def port_open(host="localhost", port=5000, timeout=1.0):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def wait_for_port(host="localhost", port=5000, timeout=15.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if port_open(host, port, timeout=1.0):
                return True
        except KeyboardInterrupt:
            raise
        time.sleep(0.2)
    return False


def send_sql(sql_command):
    request_type, payload = to_client_request(sql_command)
    message = f"{request_type},{json.dumps(payload)}"

    started_at = time.perf_counter()
    with socket.socket() as connection:
        connection.settimeout(120)
        connection.connect(("localhost", 5000))
        connection.sendall(message.encode())
        connection.shutdown(socket.SHUT_WR)

        chunks = []
        while True:
            chunk = connection.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)

    elapsed = time.perf_counter() - started_at
    response = np.load(io.BytesIO(b"".join(chunks)), allow_pickle=True)
    user_message, log_message = response.tolist()

    return {
        "sql": sql_command,
        "type": request_type,
        "elapsed": elapsed,
        "user_message": user_message,
        "log_message": log_message,
    }


def pct(values, percentile):
    if not values:
        return 0.0

    ordered = sorted(values)
    index = round((len(ordered) - 1) * percentile)
    index = max(0, min(index, len(ordered) - 1))
    return ordered[index]


def build_cycle_sql(record_id, thread_id, cycle_number, rng):
    base_name = f"Stress_{thread_id}_{cycle_number}_{record_id}"
    seed_value = rng.randint(1, 100)
    return [
        f'SELECT * FROM test WHERE id >= 1 AND num >= {rng.randint(1, 100)}',
        f'INSERT INTO test (id, nome, num) VALUES ({record_id}, "{base_name}", {seed_value})',
        f'SELECT id, nome, num FROM test WHERE id = {record_id}',
        f'UPDATE test SET nome = "{base_name}_upd", num = {seed_value + 1} WHERE id = {record_id}',
        f'SELECT * FROM test WHERE id = {record_id}',
        f'DELETE FROM test WHERE id = {record_id}',
    ]


def run_worker(thread_id, cycles, id_state, id_lock, start_barrier, results, result_lock):
    rng = random.Random(20260428 + thread_id)
    start_barrier.wait()

    local_results = []
    for cycle_number in range(1, cycles + 1):
        with id_lock:
            record_id = id_state[0]
            id_state[0] += 1

        for step_number, sql_command in enumerate(build_cycle_sql(record_id, thread_id, cycle_number, rng), start=1):
            started_at = time.perf_counter()
            try:
                response = send_sql(sql_command)
                status = "ok"
                error_message = ""
                user_message = response["user_message"]
                request_type = response["type"]
                elapsed = response["elapsed"]
            except Exception as exc:  # pragma: no cover - captured in the report instead of failing early
                status = "error"
                error_message = str(exc)
                user_message = ""
                request_type = "UNKNOWN"
                elapsed = time.perf_counter() - started_at

            local_results.append(
                {
                    "thread": thread_id,
                    "cycle": cycle_number,
                    "step": step_number,
                    "sql": sql_command,
                    "type": request_type,
                    "status": status,
                    "elapsed": elapsed,
                    "user_message": user_message,
                    "error": error_message,
                }
            )

    with result_lock:
        results.extend(local_results)


def run_worker_workload(thread_id, workload, id_state, id_lock, start_barrier, results, result_lock):
    rng = random.Random(20260428 + thread_id)
    start_barrier.wait()

    local_results = []
    for cycle_number in range(1, workload["cycles"] + 1):
        with id_lock:
            record_id = id_state[0]
            id_state[0] += 1

        cycle_sql = build_cycle_sql(record_id, thread_id, cycle_number, rng)
        for step_number, sql_command in enumerate(cycle_sql, start=1):
            started_at = time.perf_counter()
            try:
                response = send_sql(sql_command)
                status = "ok"
                error_message = ""
                user_message = response["user_message"]
                request_type = response["type"]
                elapsed = response["elapsed"]
            except Exception as exc:  # pragma: no cover - captured in the report instead of failing early
                status = "error"
                error_message = str(exc)
                user_message = ""
                request_type = "UNKNOWN"
                elapsed = time.perf_counter() - started_at

            local_results.append(
                {
                    "thread": thread_id,
                    "cycle": cycle_number,
                    "step": step_number,
                    "sql": sql_command,
                    "type": request_type,
                    "status": status,
                    "elapsed": elapsed,
                    "user_message": user_message,
                    "error": error_message,
                }
            )

    with result_lock:
        results.extend(local_results)


def append_log_summary(summary_text):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_PATH, "a", encoding="utf-8") as log_file:
        log_file.write(f"[{timestamp}] TESTE DE CONCORRÊNCIA INTENSIVO\n")
        for line in summary_text.strip().splitlines():
            log_file.write(f"[{timestamp}] {line}\n")
        log_file.write("-" * 50 + "\n")


def write_report(report_data):
    lines = []
    lines.append("# Relatório do teste de concorrência")
    lines.append("")
    lines.append(f"- Data: {report_data['timestamp']}")
    lines.append(f"- Servidor iniciado pelo script: {report_data['started_server']}")
    lines.append(f"- Threads do cliente: {report_data['threads']}")
    lines.append(f"- Ciclos por thread: {report_data['cycles']}")
    lines.append(f"- Requisições totais: {report_data['total_requests']}")
    lines.append(f"- Sucessos: {report_data['successes']}")
    lines.append(f"- Erros: {report_data['errors']}")
    lines.append(f"- Taxa de sucesso: {report_data['success_rate']:.2f}%")
    lines.append(f"- Duração total: {report_data['total_duration']:.2f}s")
    lines.append(f"- Latência média: {report_data['avg_latency']:.3f}s")
    lines.append(f"- Mediana: {report_data['median_latency']:.3f}s")
    lines.append(f"- p95: {report_data['p95_latency']:.3f}s")
    lines.append(f"- p99: {report_data['p99_latency']:.3f}s")
    lines.append("")
    lines.append("## Distribuição por tipo")
    lines.append("")
    for request_type, count in sorted(report_data["by_type"].items()):
        lines.append(f"- {request_type}: {count}")
    lines.append("")
    lines.append("## Observações")
    lines.append("")
    lines.append("- O teste usa backup/restauração do arquivo `Tables/test.csv` para evitar sujeira na massa de dados.")
    lines.append("- A fila do servidor e o `time.sleep(1)` por requisição limitam a vazão total, então o foco é medir contenção e estabilidade sob concorrência real.")
    lines.append("- Se houve erro, ele aparece no resumo e no log de execução.")

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_matrix_report(matrix_rows, baseline_duration, total_requests):
    lines = []
    lines.append("# Relatório comparativo de concorrência")
    lines.append("")
    lines.append(f"- Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- Baseline de 1 thread: {baseline_duration:.2f}s")
    lines.append(f"- Requisições totais por rodada: {total_requests}")
    lines.append("")
    lines.append("| Threads | Ciclos por thread | Requisições | Duração | Req/s | Speedup | Eficiência |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for row in matrix_rows:
        lines.append(
            f"| {row['threads']} | {row['cycles_per_thread']} | {row['total_requests']} | {row['total_duration']:.2f}s | "
            f"{row['throughput']:.2f} | {row['speedup']:.2f}x | {row['efficiency']:.2f} |"
        )
    lines.append("")
    lines.append("## Interpretação")
    lines.append("")
    lines.append("- Speedup acima de 1x indica ganho em relação à execução com 1 thread no mesmo volume total de trabalho.")
    lines.append("- Req/s ajuda a ver se o sistema está realmente processando mais requisições por segundo.")
    lines.append("- Eficiência é o speedup dividido pelo número de threads e mostra o quanto cada thread contribui.")
    lines.append("- No seu caso, o gargalo principal também inclui o `time.sleep(1)` do servidor e o lock por operação no CSV.")

    REPORT_MATRIX_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_report_data(args, results, total_duration, started_server):
    successes = sum(1 for item in results if item["status"] == "ok")
    errors = len(results) - successes
    latencies = [item["elapsed"] for item in results if item["status"] == "ok"]
    by_type = Counter(item["type"] for item in results if item["status"] == "ok")

    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "started_server": "sim" if started_server else "não",
        "threads": args.threads,
        "cycles": args.cycles,
        "cycles_per_thread": args.cycles,
        "total_requests": len(results),
        "successes": successes,
        "errors": errors,
        "success_rate": (successes / len(results) * 100) if results else 0.0,
        "total_duration": total_duration,
        "avg_latency": sum(latencies) / len(latencies) if latencies else 0.0,
        "median_latency": pct(latencies, 0.5),
        "p95_latency": pct(latencies, 0.95),
        "p99_latency": pct(latencies, 0.99),
        "by_type": dict(by_type),
    }


def build_workload_report_data(threads, cycles_per_thread, results, total_duration, started_server, total_requests):
    successes = sum(1 for item in results if item["status"] == "ok")
    errors = len(results) - successes
    latencies = [item["elapsed"] for item in results if item["status"] == "ok"]
    by_type = Counter(item["type"] for item in results if item["status"] == "ok")

    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "started_server": "sim" if started_server else "não",
        "threads": threads,
        "cycles": cycles_per_thread,
        "cycles_per_thread": cycles_per_thread,
        "total_requests": len(results),
        "successes": successes,
        "errors": errors,
        "success_rate": (successes / len(results) * 100) if results else 0.0,
        "total_duration": total_duration,
        "avg_latency": sum(latencies) / len(latencies) if latencies else 0.0,
        "median_latency": pct(latencies, 0.5),
        "p95_latency": pct(latencies, 0.95),
        "p99_latency": pct(latencies, 0.99),
        "by_type": dict(by_type),
        "throughput": (len(results) / total_duration) if total_duration else 0.0,
        "total_requests_target": total_requests,
    }


def run_benchmark(args, started_server):
    results = []
    result_lock = threading.Lock()
    id_lock = threading.Lock()

    original_frame = pd.read_csv(TABLE_PATH)
    next_id = [int(original_frame["id"].max()) + 1]

    barrier = threading.Barrier(args.threads + 1)
    workers = []

    started_at = time.perf_counter()
    for thread_id in range(1, args.threads + 1):
        worker = threading.Thread(
            target=run_worker,
            args=(thread_id, args.cycles, next_id, id_lock, barrier, results, result_lock),
            daemon=True,
        )
        worker.start()
        workers.append(worker)

    barrier.wait()

    for worker in workers:
        worker.join()

    total_duration = time.perf_counter() - started_at
    report_data = build_report_data(args, results, total_duration, started_server)
    return report_data


def run_fixed_workload(thread_count, total_cycles, started_server):
    results = []
    result_lock = threading.Lock()
    id_lock = threading.Lock()

    original_frame = pd.read_csv(TABLE_PATH)
    next_id = [int(original_frame["id"].max()) + 1]

    base_cycles = total_cycles // thread_count
    remainder = total_cycles % thread_count
    workloads = []
    for index in range(thread_count):
        cycles = base_cycles + (1 if index < remainder else 0)
        workloads.append({"cycles": cycles})

    barrier = threading.Barrier(thread_count + 1)
    workers = []

    started_at = time.perf_counter()
    for thread_id, workload in enumerate(workloads, start=1):
        worker = threading.Thread(
            target=run_worker_workload,
            args=(thread_id, workload, next_id, id_lock, barrier, results, result_lock),
            daemon=True,
        )
        worker.start()
        workers.append(worker)

    barrier.wait()

    for worker in workers:
        worker.join()

    total_duration = time.perf_counter() - started_at
    total_requests = total_cycles * 6
    return build_workload_report_data(thread_count, total_cycles // thread_count if thread_count else 0, results, total_duration, started_server, total_requests)


def restore_table(backup_path):
    shutil.copy2(backup_path, TABLE_PATH)


def main():
    parser = argparse.ArgumentParser(description="Executa um teste intenso de concorrência no SO-BD.")
    parser.add_argument("--threads", type=int, default=8, help="Número de threads concorrentes no cliente.")
    parser.add_argument("--cycles", type=int, default=3, help="Número de ciclos por thread.")
    parser.add_argument(
        "--matrix",
        type=int,
        nargs="+",
        help="Lista de quantidades de threads para comparar em sequência. Ex.: --matrix 1 2 4 8",
    )
    parser.add_argument(
        "--workload-cycles",
        type=int,
        default=16,
        help="Quantidade total de ciclos a manter constante em cada rodada da matriz. Cada ciclo executa 6 requisições.",
    )
    parser.add_argument(
        "--server-start-timeout",
        type=float,
        default=20.0,
        help="Tempo máximo para esperar o servidor subir, em segundos.",
    )
    args = parser.parse_args()

    if not TABLE_PATH.exists():
        raise FileNotFoundError(f"Tabela base não encontrada: {TABLE_PATH}")

    backup_dir = Path(tempfile.mkdtemp(prefix="so_bd_backup_"))
    backup_path = backup_dir / TABLE_PATH.name
    shutil.copy2(TABLE_PATH, backup_path)

    started_server = False
    server_process = None
    if not port_open():
        kill_process_on_port()  # Limpa qualquer processo anterior na porta
        try:
            time.sleep(0.5)  # Aguarda a porta ficar realmente livre
        except KeyboardInterrupt:
            if server_process:
                server_process.terminate()
            raise
        server_process = subprocess.Popen([sys.executable, "-u", str(SERVER_PATH)], cwd=str(BASE_DIR))
        started_server = True
        if not wait_for_port(timeout=args.server_start_timeout):
            raise RuntimeError("O servidor não ficou disponível dentro do tempo esperado.")

    matrix_mode = bool(args.matrix)
    try:
        if matrix_mode:
            matrix_threads = args.matrix
            if 1 not in matrix_threads:
                matrix_threads = [1] + matrix_threads

            matrix_rows = []
            baseline_duration = None

            for thread_count in matrix_threads:
                restore_table(backup_path)
                report_data = run_fixed_workload(thread_count, args.workload_cycles, started_server)

                if thread_count == 1:
                    baseline_duration = report_data["total_duration"]

                matrix_rows.append(report_data)

                summary = (
                    f"Rodada com {report_data['threads']} thread(s): {report_data['total_requests']} requisições, "
                    f"{report_data['total_duration']:.2f}s no total"
                )
                append_log_summary(summary)

                print(summary)

            if baseline_duration is None:
                baseline_duration = matrix_rows[0]["total_duration"]

            for row in matrix_rows:
                row["speedup"] = baseline_duration / row["total_duration"] if row["total_duration"] else 0.0
                row["efficiency"] = row["speedup"] / row["threads"] if row["threads"] else 0.0
                row["throughput"] = row["total_requests"] / row["total_duration"] if row["total_duration"] else 0.0

            write_matrix_report(matrix_rows, baseline_duration, args.workload_cycles * 6)
            print(f"Relatório comparativo salvo em: {REPORT_MATRIX_PATH}")

        else:
            restore_table(backup_path)
            report_data = run_benchmark(args, started_server)
            write_report(report_data)

            summary = (
                f"Resumo do teste: {report_data['total_requests']} requisições, "
                f"{report_data['successes']} sucessos, {report_data['errors']} erros, "
                f"{report_data['total_duration']:.2f}s no total, "
                f"média {report_data['avg_latency']:.3f}s"
            )
            append_log_summary(summary)

            print("Teste concluído.")
            print(summary)
            print(f"Relatório salvo em: {REPORT_PATH}")
            print(f"Resumo salvo em: {LOG_PATH}")

    finally:
        restore_table(backup_path)
        shutil.rmtree(backup_dir, ignore_errors=True)

        if started_server and server_process is not None:
            server_process.terminate()
            try:
                server_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server_process.kill()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTeste cancelado pelo usuário.")
        sys.exit(1)