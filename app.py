"""Demo web: Streamlit + Hugging Face para consultar una base de datos en lenguaje natural.

Ejecutar con:
    streamlit run app.py
"""
import streamlit as st

from textsql.db import TABLE_NAME, run_query
from textsql.model import TextToSQL
from textsql.sanitize import adapt_sql, validate_select_only

st.set_page_config(page_title="Text-to-SQL con IA", page_icon="🗄️")
st.title("🗄️ Pregunta a tu base de datos en lenguaje natural")
st.caption("Demo educativa: Hugging Face (T5 afinado en WikiSQL) + SQLite")


@st.cache_resource
def load_model() -> TextToSQL:
    return TextToSQL()


engine = load_model()

st.write(f"Tabla disponible: **{TABLE_NAME}** (product, category, price, quantity, city, customer, sale_date)")
question = st.text_input(
    "Escribe tu pregunta en ingles",
    placeholder="how many products were sold in Madrid",
)

if st.button("Generar y ejecutar") and question:
    raw_sql = engine.generate(question)
    sql = adapt_sql(raw_sql, TABLE_NAME)

    st.subheader("SQL generado")
    st.code(sql, language="sql")

    try:
        validate_select_only(sql)
        df = run_query(sql)
        st.subheader("Resultado")
        st.dataframe(df, use_container_width=True)
    except Exception as exc:
        st.error(f"No se pudo ejecutar la consulta generada: {exc}")
