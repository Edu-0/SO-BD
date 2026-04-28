import pandas as pd
from pathlib import Path
import operator
import threading

class ReadWriteLock:
    def __init__(self):
        self.read_lock = threading.Lock()
        self.write_lock = threading.Lock()
        self.readers = 0

    def acquire_read(self):
        with self.read_lock:
            self.readers += 1
            if self.readers == 1:
                self.write_lock.acquire()

    def release_read(self):
        with self.read_lock:
            self.readers -= 1
            if self.readers == 0:
                self.write_lock.release()

    def acquire_write(self):
        self.write_lock.acquire()

    def release_write(self):
        self.write_lock.release()


lock = ReadWriteLock()

ops = {
    "==": operator.eq,
    ">": operator.gt,
    "<": operator.lt,
    ">=": operator.ge,
    "<=": operator.le,
    "!=": operator.ne
}

BASE_DIR = Path(__file__).resolve().parent.parent
TABLES_DIR = BASE_DIR / "Tables"


def aplicar_filtro(df, where):
    # df_filtrado = df[(df["id"] == 0) & (df["nome"] == "Eduardo")]
    # df_filtrado = df[(df["id"] == 0) | (df["nome"] == "Eduardo")]
    # Seguindo essa forma de filtro, segue uma forma para aplicar múltiplos:
    if not where:
        return pd.Series([True] * len(df), index=df.index)

    col, op, val = where[0]
    mask = ops[op](df[col], val)

    for item in where[1:]:
        logic, col, op, val = item
        cond = ops[op](df[col], val)

        if logic == "AND":
            mask &= cond
        elif logic == "OR":
            mask |= cond

    return mask


def get(table, value):
    # SELECT cols[...] FROM table WHERE where[...]
    lock.acquire_read()
    try:
        file_path = TABLES_DIR / table
        df = pd.read_csv(file_path, skipinitialspace=True)
        mask = aplicar_filtro(df, value["where"])
        df = df[mask]

        if value["cols"][0] != "*":
            df = df[value["cols"]]

        result = df.to_string(index=False)

        user_msg = result

        log_msg = f"[GET] tabela={table} | \n{user_msg}"

        return user_msg, log_msg # Retornando o GET para o usuário
    finally:
        lock.release_read()


def post(table, value):
    # INSERT INTO table(cols[...]) VALUES values([...])
    lock.acquire_write()
    try:
        file_path = TABLES_DIR / table
        df = pd.read_csv(file_path)

        # Verificando se a coluna passada existe. Se não existe, mas foi passada, acaba criando uma coluna indesejada
        for col in value["cols"]:
            if col not in df.columns:
                raise ValueError(f"A coluna '{col}' não existe na tabela")

        n = len(value["values"])

        new_lines = []
        for row in value["values"]:
            new_line = {col: row.get(col) for col in value["cols"]}
            new_lines.append(new_line)

        df = pd.concat([df, pd.DataFrame(new_lines)], ignore_index=True)

        df.to_csv(file_path, index=False)

        user_msg = f"INSERT realizado - {n} linha(s) inserida(s)"

        log_msg = f"[POST] tabela={table} | inseridas={n} | cols={','.join(value['cols'])}"

        return user_msg, log_msg
    finally:
        lock.release_write()


def put(table, value):
    # UPDATE table SET values[...] WHERE where[...]
    lock.acquire_write()
    try:
        file_path = TABLES_DIR / table
        df = pd.read_csv(file_path)

        filtro = aplicar_filtro(df, value["where"])

        n = filtro.sum() # Número de linhas afetados

        cols = df.columns if value["cols"][0] == "*" else value["cols"]

        for col in cols:
            if col in value["values"][0]:
                df.loc[filtro, col] = value["values"][0][col]

        user_msg = f"UPDATE realizado - {n} linha(s) afetada(s)"

        log_msg = f"[PUT] tabela={table} | afetadas={n} | colunas={','.join(cols)} | where={value['where']}"

        df.to_csv(file_path, index=False)
        return user_msg, log_msg
    finally:
        lock.release_write()


def delete(table, value):
    # DELETE FROM table WHERE where[...]
    lock.acquire_write()
    try:
        file_path = TABLES_DIR / table
        df = pd.read_csv(file_path)

        where = value["where"]
        mask = aplicar_filtro(df, where)

        n = mask.sum()  # Número de linhas afetados

        df = df[~mask]
        df.to_csv(file_path, index=False)

        user_msg = f"DELETE realizado - {n} linha(s) removida(s)"

        log_msg = f"[DELETE] tabela={table} | removidas={n} | where={where}"

        return user_msg, log_msg
    finally:
        lock.release_write()