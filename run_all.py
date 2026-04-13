import subprocess
import sys
import os
import platform

# Caminho para os arquivos
server_path = os.path.join("Server", "server.py")
client_path = os.path.join("Client", "client.py")

if __name__ == "__main__":

    if platform.system() == "Windows":
        # Windows - abre em terminais separados
        print("Iniciando servidor em novo terminal...")
        subprocess.Popen(f"start python {server_path}", shell=True)

        print("Iniciando cliente em novo terminal...")
        subprocess.Popen(f"start python {client_path}", shell=True)

        print("Terminais abertos! Pressione Enter para encerrar este script...")
        input()
    else:
        # Linux/Mac
        print("Iniciando servidor...")
        server_process = subprocess.Popen([sys.executable, server_path])

        print("Iniciando cliente...")
        client_process = subprocess.Popen([sys.executable, client_path])

        try:
            server_process.wait()
            client_process.wait()
        except KeyboardInterrupt:
            print("\nEncerrando processos...")
            server_process.terminate()
            client_process.terminate()