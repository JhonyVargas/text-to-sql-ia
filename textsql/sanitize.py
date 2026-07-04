"""Adapta y valida el SQL generado por el modelo antes de ejecutarlo.

El modelo de Hugging Face fue entrenado sobre WikiSQL: no conoce el esquema
real de nuestra base de datos, asi que "inventa" nombres de columna a partir
de las palabras de la pregunta (p. ej. "city" -> Location o City), a veces
omite los parentesis de las funciones de agregacion (COUNT Price en vez de
COUNT(Price)) y no siempre entrega los valores de texto entre comillas.
Nunca se debe ejecutar SQL generado por un modelo de IA sin antes validarlo:
aqui se normaliza el resultado y se restringe a SELECT, evitando cualquier
statement destructivo o encadenado (mitigacion basica de inyeccion SQL).
"""
import re

FORBIDDEN_KEYWORDS = re.compile(
    r"\b(insert|update|delete|drop|alter|attach|detach|pragma|create|replace|vacuum)\b",
    re.IGNORECASE,
)

_VALUE_PATTERN = re.compile(
    r"(=|LIKE)\s+([A-Za-z][\w\s]*?)(?=(\s+AND\b|\s+OR\b|\s+ORDER\b|\s+GROUP\b|$))",
    re.IGNORECASE,
)

_AGG_NO_PARENS = re.compile(
    r"\b(COUNT|SUM|AVG|MIN|MAX)\s+(?!\()([A-Za-z_]\w*)(?:\s+[A-Za-z_]\w*)*\s+FROM",
    re.IGNORECASE,
)

_AGG_WITH_PARENS = re.compile(r"\b(COUNT|SUM|AVG|MIN|MAX)\(([A-Za-z_]\w*)\)", re.IGNORECASE)
_SELECT_SIMPLE = re.compile(r"\bSELECT\s+([A-Za-z_]\w*)\s+FROM\b", re.IGNORECASE)
_WHERE_COLUMN = re.compile(r"\b(WHERE|AND|OR)\s+([A-Za-z_]\w*)\s*(=|LIKE|>=|<=|>|<)", re.IGNORECASE)
_STRING_EQUALITY = re.compile(r"([A-Za-z_]\w*)\s*=\s*'([^']*)'")

# El modelo no ve nuestro esquema real: mapea los nombres que suele inventar
# (en base al vocabulario de la pregunta) a las columnas reales de "ventas".
COLUMN_SYNONYMS = {
    "product": "product",
    "item": "product",
    "category": "category",
    "type": "category",
    "price": "price",
    "cost": "price",
    "amount": "price",
    "quantity": "quantity",
    "qty": "quantity",
    "city": "city",
    "location": "city",
    "town": "city",
    "customer": "customer",
    "client": "customer",
    "buyer": "customer",
    "date": "sale_date",
    "saledate": "sale_date",
    "sale": "*",
    "sales": "*",
    "id": "id",
}


class UnsafeQueryError(ValueError):
    pass


def _map_column(token: str) -> str:
    return COLUMN_SYNONYMS.get(token.lower(), token.lower())


def _fix_missing_parens(sql: str) -> str:
    return _AGG_NO_PARENS.sub(lambda m: f"{m.group(1)}({m.group(2)}) FROM", sql)


def _quote_values(sql: str) -> str:
    def _quote(match: re.Match) -> str:
        op, value = match.group(1), match.group(2).strip()
        if value.replace(".", "", 1).isdigit() or value.startswith(("'", '"')):
            return f"{op} {value}"
        return f"{op} '{value}'"

    return _VALUE_PATTERN.sub(_quote, sql)


def _normalize_columns(sql: str) -> str:
    sql = _AGG_WITH_PARENS.sub(lambda m: f"{m.group(1)}({_map_column(m.group(2))})", sql)
    sql = _SELECT_SIMPLE.sub(lambda m: f"SELECT {_map_column(m.group(1))} FROM", sql)
    sql = _WHERE_COLUMN.sub(lambda m: f"{m.group(1)} {_map_column(m.group(2))} {m.group(3)}", sql)
    return sql


def _case_insensitive_compare(sql: str) -> str:
    """El modelo no siempre respeta la capitalizacion real de los datos (p. ej.
    'barcelona' en vez de 'Barcelona'), lo que puede devolver 0 filas en vez de
    fallar. Comparar en minusculas evita ese falso negativo silencioso."""
    return _STRING_EQUALITY.sub(lambda m: f"LOWER({m.group(1)}) = LOWER('{m.group(2)}')", sql)


def adapt_sql(raw_sql: str, table_name: str) -> str:
    """Repara parentesis, renombra la tabla generica y normaliza columnas y valores."""
    sql = _fix_missing_parens(raw_sql)
    sql = re.sub(r"\bFROM\s+table\b", f"FROM {table_name}", sql, flags=re.IGNORECASE)
    sql = _quote_values(sql)
    sql = _normalize_columns(sql)
    sql = _case_insensitive_compare(sql)
    return sql.strip().rstrip(";")


def validate_select_only(sql: str) -> None:
    """Lanza UnsafeQueryError si el SQL no es un SELECT unico y sin comandos peligrosos."""
    stripped = sql.strip()
    if not stripped.upper().startswith("SELECT"):
        raise UnsafeQueryError("Solo se permiten consultas SELECT generadas por el modelo.")
    if ";" in stripped:
        raise UnsafeQueryError("No se permiten multiples sentencias en una misma consulta.")
    if FORBIDDEN_KEYWORDS.search(stripped):
        raise UnsafeQueryError("La consulta generada contiene palabras clave no permitidas.")
