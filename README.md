# Text-to-SQL con IA 🗄️🤖

Demo educativa para el curso **Base de Datos II**: convierte preguntas en
lenguaje natural en consultas SQL usando un modelo de Hugging Face, y las
ejecuta de forma segura contra una base de datos SQLite de ejemplo (ventas de
una tienda de tecnologia).

## Arquitectura

```
pregunta (ingles) --> modelo T5 (Hugging Face, afinado en WikiSQL)
                   --> SQL "crudo" generado por el modelo
                   --> adaptacion (tabla real + comillas) y validacion (solo SELECT)
                   --> ejecucion en modo solo-lectura sobre SQLite
                   --> resultado (tabla)
```

- `seed_db.py` — crea `data/ventas.db` con datos sinteticos.
- `textsql/model.py` — carga el modelo `mrm8488/t5-base-finetuned-wikiSQL` y genera SQL.
- `textsql/sanitize.py` — repara y normaliza el SQL generado (agrega
  parentesis faltantes en `COUNT`/`SUM`/..., renombra la tabla generica,
  mapea los nombres de columna "inventados" por el modelo a las columnas
  reales via un diccionario de sinonimos, agrega comillas a los valores de
  texto y compara strings sin distinguir mayusculas/minusculas) y bloquea
  cualquier cosa que no sea un `SELECT` (mitigacion basica de inyeccion SQL:
  nunca se ejecuta SQL de un modelo de IA sin validar).
- `textsql/db.py` — ejecuta la consulta abriendo la base de datos en modo
  solo-lectura (`mode=ro`).
- `cli.py` — interfaz de terminal.
- `app.py` — interfaz web con Streamlit.

## Instalacion

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
python seed_db.py             # crea data/ventas.db
```

## Uso

Terminal:

```bash
python cli.py
```

Web (Streamlit):

```bash
streamlit run app.py
```

Preguntas de ejemplo (el modelo fue entrenado en ingles, con el dataset
WikiSQL):

- `how many products were sold in Madrid`
- `what is the total price where city is Barcelona`
- `how many sales were there in category Phones`

## Limitaciones conocidas

- El modelo genera SQL orientado a una sola tabla (formato WikiSQL) y no
  conoce el esquema real de `ventas`: "inventa" nombres de columna a partir
  de las palabras de la pregunta. `textsql/sanitize.py` los normaliza con un
  diccionario de sinonimos, pero si la pregunta usa una palabra que no esta
  mapeada, la consulta puede fallar (se muestra el error en vez de ejecutar
  algo incorrecto).
- El modelo fue entrenado en ingles: las preguntas deben escribirse en ese
  idioma.
- Solo se permiten consultas `SELECT`: cualquier otra sentencia se rechaza
  antes de tocar la base de datos.
- Es un proyecto con fines educativos, no una solucion de produccion.

## Referencias

- Como comunicarse con cualquier base de datos mediante IA: crea tu propio
  extractor de datos con consultas SQL.
- Texto a SQL — Hugging Face.
- Como crear un generador de consultas SQL a partir de texto con Streamlit y
  Hugging Face (Medium).

## Licencia

MIT
