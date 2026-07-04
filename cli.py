"""Interfaz de terminal: escribe una pregunta en ingles y obten SQL + resultados."""
from textsql.db import TABLE_NAME, run_query
from textsql.model import TextToSQL
from textsql.sanitize import adapt_sql, validate_select_only


def main():
    print("Cargando modelo de Hugging Face (puede tardar la primera vez)...")
    engine = TextToSQL()
    print(f"Listo. Pregunta en ingles sobre la tabla '{TABLE_NAME}' (o 'salir' para terminar).\n")

    while True:
        question = input("Pregunta> ").strip()
        if not question:
            continue
        if question.lower() in {"salir", "exit", "quit"}:
            break

        raw_sql = engine.generate(question)
        sql = adapt_sql(raw_sql, TABLE_NAME)
        print(f"SQL generado: {sql}")

        try:
            validate_select_only(sql)
            df = run_query(sql)
        except Exception as exc:
            print(f"No se pudo ejecutar la consulta: {exc}\n")
            continue

        print(df.to_string(index=False))
        print()


if __name__ == "__main__":
    main()
