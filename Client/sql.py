import re

class SQLInterpreter:
    def __init__(self, query: str):        
        self.query = query.strip()
        self.action = self._main_solver()
        self.result = self.parse()

    def parse(self):
        metodo = getattr(self, self.action, None)
        if not callable(metodo):
            raise ValueError("Comando não reconhecido")
        return metodo()

    def select(self):
        table = self._extract_table("from")
        columns = self._extract_columns("select")
        where = self._extract_conditions()
        return {
            "action": "select",
            "table": table,
            "columns": columns,
            "where": where
        }

    def insert(self):
        table = self._extract_table("into")
        columns = self._extract_insert_columns()
        values = self._extract_values()
        for row in values:
            if len(columns) != len(row):
                raise ValueError("Número de colunas e valores não corresponde.")
        
        data = [dict(zip(columns, row)) for row in values]

        return {
            "action": "insert",
            "table": table,
            "cols": columns,
            "values": data
        }

    def update(self):
        table = self._extract_table("update")
        set_clause = self._extract_set_clause()
        where = self._extract_conditions()
        return {
            "action": "update",
            "table": table,
            "data": set_clause,
            "where": where
        }

    def delete(self):
        table = self._extract_table("from")
        conditions = self._extract_conditions()
        if not conditions:
            raise ValueError("Condição WHERE mal formada para DELETE")
        return {
            "action": "delete",
            "table": table,
            "where": conditions,
            "conditions": conditions
        }

    # ------------------- Auxiliares -------------------
    def _main_solver(self):
        return self.query.lower().split(" ")[0]
    
    def _extract_table(self, separator: str):
        table_match = re.search(rf'{separator}\s+(\w+)', self.query, re.IGNORECASE)
        if not table_match:
            raise ValueError("Tabela não encontrada.")
        return table_match.group(1)
    
    def _extract_columns(self, separator: str):
        cols_match = re.search(rf'{separator}\s+(.*?)\s+from', self.query, re.IGNORECASE)
        if not cols_match:
            raise ValueError("Colunas não encontradas.")
        return [c.strip() for c in cols_match.group(1).split(",")]

    def _extract_insert_columns(self):
        cols_match = re.search(r'\((.*?)\)\s*values', self.query, re.IGNORECASE)
        if not cols_match:
            raise ValueError("Colunas não encontradas.")
        return [c.strip() for c in cols_match.group(1).split(",")]

    def _extract_values(self):
        values_match = re.search(r'values\s*(.*?)$', self.query, re.IGNORECASE)
        if not values_match:
            raise ValueError("Valores não encontrados.")

        values_str = values_match.group(1)
        groups = re.findall(r'\((.*?)\)', values_str)

        if not groups:
            raise ValueError("Nenhum grupo de valores encontrado.")

        result = []
        for group in groups:
            row = [v.strip().strip("'").strip('"') for v in group.split(",")]
            result.append(row)

        return result

    def _extract_set_clause(self):
        set_match = re.search(r'set\s+(.*?)(?:\s+where|$)', self.query, re.IGNORECASE)
        if not set_match:
            raise ValueError("SET não encontrado no UPDATE")
        set_clause = set_match.group(1)
        atributos = {}
        pares = re.split(r',(?=(?:[^\'"]|\'[^\']*\'|"[^"]*")*$)', set_clause)
        for par in pares:
            if "=" not in par:
                continue
            chave, valor = par.split("=", 1)
            atributos[chave.strip()] = valor.strip().strip("'").strip('"')
        return atributos

    def _extract_conditions(self):
        where_match = re.search(r'where\s+(.*)', self.query, re.IGNORECASE)
        if not where_match:
            return None

        condition_str = where_match.group(1).strip()
        
        parts = re.split(r'\s+(AND|OR)\s+', condition_str, flags=re.IGNORECASE)
        operators = ["<=", ">=", "<>", "=", "<", ">"]
        result = []
        i = 0
        while i < len(parts):
            cond = parts[i].strip()
            logic = parts[i+1].upper() if i+1 < len(parts) and parts[i+1].upper() in ("AND", "OR") else None

            for op in operators:
                if op in cond:
                    var, val = cond.split(op, 1)
                    result.append({
                        "variable": var.strip(),
                        "operator": op,
                        "value": val.strip().strip("'").strip('"'),
                        "logic": logic
                    })
                    break
            i += 2

        return result


def _cast_value(value):
    if isinstance(value, (int, float, bool)):
        return value

    val = str(value).strip()
    low = val.lower()

    if low == "true":
        return True
    if low == "false":
        return False

    try:
        return int(val)
    except ValueError:
        pass

    try:
        return float(val)
    except ValueError:
        return val


def _convert_where(conditions):
    if not conditions:
        return []

    op_map = {"=": "==", "<>": "!="}
    where = []

    first = conditions[0]
    where.append((
        first["variable"],
        op_map.get(first["operator"], first["operator"]),
        _cast_value(first["value"])
    ))

    for i in range(1, len(conditions)):
        prev_logic = conditions[i - 1].get("logic") or "AND"
        cond = conditions[i]
        where.append((
            prev_logic,
            cond["variable"],
            op_map.get(cond["operator"], cond["operator"]),
            _cast_value(cond["value"])
        ))

    return where


def to_client_request(sql_command):
    parsed = SQLInterpreter(sql_command).result
    action = parsed["action"]

    req_map = {
        "select": "GET",
        "insert": "POST",
        "update": "PUT",
        "delete": "DELETE"
    }

    if action not in req_map:
        raise ValueError("Ação SQL inválida")

    table = f"{parsed['table']}.csv"
    where = _convert_where(parsed.get("where"))

    if action == "select":
        value = {
            "cols": parsed["columns"],
            "values": [],
            "where": where
        }
    elif action == "insert":
        data = parsed["values"]
        cols = list(data[0].keys()) if data else []
        value = {
            "cols": cols,
            "values": [{k: _cast_value(v) for k, v in row.items()} for row in data],
            "where": []
        }
    elif action == "update":
        data = {k: _cast_value(v) for k, v in parsed["data"].items()}
        value = {
            "cols": list(data.keys()),
            "values": [data],
            "where": where
        }
    else:
        value = {
            "cols": ["*"],
            "values": [],
            "where": where
        }

    payload = {
        "table": table,
        "value": value
    }
    return req_map[action], payload

if __name__ == "__main__":
    data = input("Digite um comando SQL: ")
    print("Resultado:", SQLInterpreter(data).result)