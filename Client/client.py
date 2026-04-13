import numpy as np
import socket
import json
import io
from sql import to_client_request
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def send_request(req, data, comando_original):
    with socket.socket() as s:
        s.connect(("localhost", 5000))
        msg = f"{req},{json.dumps(data)}"
        s.sendall(msg.encode())
        s.shutdown(socket.SHUT_WR)
        chunks = []
        while True: # Recebendo a resposta do servidor em partes
            chunk = s.recv(4096) # O cliente lê a resposta em blocos de 4KB
            if not chunk:
                break
            chunks.append(chunk)
        receive = b"".join(chunks)

    user_msg, log_msg = np.load(io.BytesIO(receive), allow_pickle=True)
    print(user_msg)
    with open(BASE_DIR / "log.txt" , "a", encoding="UTF-8") as log:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log.write(f"[{timestamp}] Comando: {comando_original}\n")
        log.write(f"[{timestamp}] Tipo: {req.upper()}\n")
        log.write(f"[{timestamp}] Resposta: {log_msg}\n")
        log.write("-" * 50 + "\n")


if __name__ == "__main__":
    try:
        while True:
            sql = input("Digite um comando SQL: ")
            try:
                req, data = to_client_request(sql)
                send_request(req, data, sql)
            except ValueError as e:
                print(e)
            except NameError:
                print("Nenhuma requisição válida passada")
    except KeyboardInterrupt:
        print("\n\nPrograma finalizado!")  # Removi o erro vermelho ao encerrar o programa forçadamente
