import io
import threading
import time
import queue
import json
import socket
from pathlib import Path
import methods as m
import numpy as np


BASE_DIR = Path(__file__).resolve().parent.parent
TABLES_DIR = BASE_DIR / "Tables"
task_queue = queue.Queue()


def recv_request(conn):
    chunks = []
    while True:
        data = conn.recv(4096) # O servidor lê a requisição em blocos de 4KB
        if not data:
            break
        chunks.append(data)
    return b"".join(chunks).decode()


def worker():
    while True:
        method, payload, conn = task_queue.get() # Pegando a função + parâmetro
        try:
            if method == "GET":
                response = m.get(payload["table"], payload.get("value"))

            elif method == "POST":
                response = m.post(payload["table"], payload.get("value"))

            elif method == "PUT":
                response = m.put(payload["table"], payload.get("value"))

            elif method == "DELETE":
                response = m.delete(payload["table"], payload.get("value"))

            else:
                response = ("Comando não reconhecido!", f"[ERRO] comando inválido: {method}")

        except FileNotFoundError:
            table = payload.get("table", "desconhecida")
            response = ("Tabela não encontrada", f"[ERRO] tabela={table} não encontrada")
        except ValueError as e:
            response = (str(e), f"[ERRO] {e}")
        except Exception as e:
            response = ("Erro interno no servidor", f"[ERRO] interno: {e}")

        try:
            buf = io.BytesIO()
            np.save(buf, response, allow_pickle=True) # Esse allow_pickle permite salvar qualquer objeto Python
            buf.seek(0)
            conn.sendall(buf.read())
        except (OSError, BrokenPipeError) as e:
            print(f"Erro ao enviar resposta: {e}")
        finally:
            conn.close()
            time.sleep(1)  # Simula processamento
            task_queue.task_done() # Avisa que o processo finalizou


def initialize_db_folder():
    if not TABLES_DIR.exists():
        TABLES_DIR.mkdir(parents=True)
        print(f"Created folder: {TABLES_DIR}")


def socket_server():
    s = socket.socket()
    s.bind(("localhost", 5000))
    s.listen()

    print("Servidor ouvindo...")

    while True:
        conn, addr = s.accept()
        data = recv_request(conn)

        try:
            if "," in data:
                method, json_payload = data.split(",", 1)
                payload = json.loads(json_payload.strip())
                task_queue.put((method.strip(), payload, conn))
            else:
                print(f"Formato inválido recebido de {addr}: {data}")
                conn.close()
        except json.JSONDecodeError as e:
            print(f"Erro ao decodificar JSON de {addr}: {e}")
            conn.close()


if __name__ == '__main__':
    initialize_db_folder()

    for _ in range(4):
        threading.Thread(target=worker, daemon=True).start()

    socket_server()