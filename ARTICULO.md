# Como conversar con tu base de datos usando IA: un generador de SQL a partir de lenguaje natural

*Articulo tecnico — Unidad 3, Base de Datos II*

## Introduccion

Una de las barreras mas comunes entre las personas de negocio y sus datos es
el propio SQL: saber que existe la informacion no sirve de mucho si hay que
escribir un `JOIN` para llegar a ella. En los ultimos anos, los modelos de
lenguaje (LLMs) han empezado a cerrar esa brecha con la tarea conocida como
**Text-to-SQL**: el usuario escribe una pregunta en lenguaje natural y el
modelo genera la consulta SQL correspondiente.

En este articulo muestro una implementacion pequena pero completa de este
patron, usando un modelo publico de Hugging Face, una base de datos SQLite de
ejemplo y una capa de validacion que evita que la IA ejecute algo peligroso.
El codigo completo esta disponible en el repositorio publico enlazado al
final.

## Arquitectura

```
pregunta (ingles)
   -> modelo T5 afinado en WikiSQL (Hugging Face)
   -> SQL "crudo" generado por el modelo
   -> adaptacion (nombre de tabla real + comillas en valores) y validacion (solo SELECT)
   -> ejecucion en modo solo-lectura sobre SQLite
   -> resultado tabular
```

La base de datos de ejemplo simula las ventas de una tienda de tecnologia,
con una tabla `ventas` que incluye producto, categoria, precio, cantidad,
ciudad, cliente y fecha:

```python
CREATE TABLE ventas (
    id INTEGER PRIMARY KEY,
    product TEXT NOT NULL,
    category TEXT NOT NULL,
    price REAL NOT NULL,
    quantity INTEGER NOT NULL,
    city TEXT NOT NULL,
    customer TEXT NOT NULL,
    sale_date TEXT NOT NULL
)
```

## El modelo: Hugging Face + T5 afinado en WikiSQL

Para generar SQL use `mrm8488/t5-base-finetuned-wikiSQL`, un modelo T5
disponible en Hugging Face y entrenado sobre el dataset WikiSQL. Se usa asi:

```python
from transformers import T5ForConditionalGeneration, T5Tokenizer

MODEL_NAME = "mrm8488/t5-base-finetuned-wikiSQL"

class TextToSQL:
    def __init__(self, model_name: str = MODEL_NAME):
        self.tokenizer = T5Tokenizer.from_pretrained(model_name)
        self.model = T5ForConditionalGeneration.from_pretrained(model_name)

    def generate(self, question: str) -> str:
        prompt = f"translate English to SQL: {question} </s>"
        features = self.tokenizer([prompt], return_tensors="pt")
        output_ids = self.model.generate(
            input_ids=features["input_ids"],
            attention_mask=features["attention_mask"],
            max_length=128,
        )
        return self.tokenizer.decode(output_ids[0], skip_special_tokens=True)
```

Para la pregunta `how many products were sold in Madrid`, el modelo entrega
algo como:

```sql
SELECT COUNT(product) FROM table WHERE city = Madrid
```

Dos detalles a resolver antes de poder ejecutar esto: la tabla generica
`table` (asi es como WikiSQL nombra sus tablas de entrenamiento) y el valor
`Madrid` sin comillas.

## La parte que casi nadie muestra: el modelo no conoce tu esquema

Al probar el modelo con preguntas reales aparecieron tres problemas que no se
ven en los ejemplos "de juguete" que suelen circular en tutoriales:

1. A veces omite los parentesis de las funciones de agregacion:
   `SELECT COUNT Product FROM table WHERE City = Madrid` en vez de
   `SELECT COUNT(Product) FROM table WHERE City = 'Madrid'`.
2. El modelo no sabe que nuestra tabla se llama `ventas` ni que sus columnas
   son `product`, `category`, `price`, `quantity`, `city`, `customer` y
   `sale_date`. WikiSQL entrena con miles de tablas distintas, asi que el
   modelo "inventa" un nombre de columna plausible a partir de las palabras
   de la pregunta (`city` a veces sale como `City`, otras como `Location`).
3. No siempre respeta la capitalizacion real de los datos: genero
   `City = barcelona` (minuscula) cuando en la base de datos el valor
   guardado es `Barcelona`. Si se ejecuta tal cual, la consulta no falla, pero
   **devuelve 0 filas silenciosamente** — el peor tipo de error porque parece
   que funciono.

Es tentador tomar el string que devuelve el modelo y pasarlo directo a
`cursor.execute()`. Es tambien la forma mas rapida de abrir una puerta a
inyeccion SQL, a que el modelo "alucine" un `DROP TABLE`, o a que un falso
negativo silencioso pase como resultado correcto. Por eso `textsql/sanitize.py`
hace cuatro cosas antes de que cualquier SQL toque la base de datos:

**1. Reparar** los parentesis faltantes en las funciones de agregacion:

```python
_AGG_NO_PARENS = re.compile(
    r"\b(COUNT|SUM|AVG|MIN|MAX)\s+(?!\()([A-Za-z_]\w*)(?:\s+[A-Za-z_]\w*)*\s+FROM",
    re.IGNORECASE,
)

def _fix_missing_parens(sql: str) -> str:
    return _AGG_NO_PARENS.sub(lambda m: f"{m.group(1)}({m.group(2)}) FROM", sql)
```

**2. Renombrar** la tabla generica y **poner comillas** en los valores de
texto sueltos (igual que en la primera version).

**3. Normalizar columnas** con un diccionario de sinonimos, ya que el modelo
no ve el esquema real:

```python
COLUMN_SYNONYMS = {
    "product": "product", "item": "product",
    "category": "category", "type": "category",
    "price": "price", "cost": "price", "amount": "price",
    "quantity": "quantity", "qty": "quantity",
    "city": "city", "location": "city", "town": "city",
    "customer": "customer", "client": "customer", "buyer": "customer",
    "date": "sale_date", "sale": "*", "sales": "*",
}
```

Con esto, `COUNT Sale` (una columna que no existe) termina traduciendose a
`COUNT(*)`, que es exactamente lo que alguien quiere decir con "cuantas
ventas hubo".

**4. Comparar sin distinguir mayusculas**, para no devolver falsos negativos
silenciosos:

```python
def _case_insensitive_compare(sql: str) -> str:
    return _STRING_EQUALITY.sub(
        lambda m: f"LOWER({m.group(1)}) = LOWER('{m.group(2)}')", sql
    )
```

Y finalmente, **validar** que lo unico que se ejecute sea un `SELECT`, sin
comandos encadenados ni palabras clave destructivas:

```python
FORBIDDEN_KEYWORDS = re.compile(
    r"\b(insert|update|delete|drop|alter|attach|detach|pragma|create|replace|vacuum)\b",
    re.IGNORECASE,
)

def validate_select_only(sql: str) -> None:
    if not sql.strip().upper().startswith("SELECT"):
        raise UnsafeQueryError("Solo se permiten consultas SELECT generadas por el modelo.")
    if ";" in sql:
        raise UnsafeQueryError("No se permiten multiples sentencias en una misma consulta.")
    if FORBIDDEN_KEYWORDS.search(sql):
        raise UnsafeQueryError("La consulta generada contiene palabras clave no permitidas.")
```

Como defensa adicional, la conexion a SQLite se abre en **modo solo-lectura**
(`file:ventas.db?mode=ro`), de forma que incluso si algo se filtrara por la
validacion, la base de datos no podria modificarse.

## De la terminal a una demo web con Streamlit

Con el motor ya funcionando, envolverlo en una interfaz web con Streamlit
toma menos de 30 lineas:

```python
import streamlit as st
from textsql.db import TABLE_NAME, run_query
from textsql.model import TextToSQL
from textsql.sanitize import adapt_sql, validate_select_only

st.title("🗄️ Pregunta a tu base de datos en lenguaje natural")

question = st.text_input("Escribe tu pregunta en ingles")

if st.button("Generar y ejecutar") and question:
    sql = adapt_sql(engine.generate(question), TABLE_NAME)
    st.code(sql, language="sql")
    validate_select_only(sql)
    st.dataframe(run_query(sql))
```

El resultado es una pagina donde se escribe, por ejemplo, `what is the total
price where city is Barcelona`, se ve el SQL generado y la tabla de
resultados en tiempo real.

## Resultados y limitaciones

Con la tabla `ventas` de ejemplo (120 filas sinteticas) y la capa de
normalizacion en su lugar, preguntas como estas se ejecutan correctamente de
principio a fin:

```
"how many products were sold in city Madrid"
  -> SELECT COUNT(product) FROM ventas WHERE LOWER(city) = LOWER('Madrid')

"how many sale in category Phones"
  -> SELECT COUNT(*) FROM ventas WHERE LOWER(category) = LOWER('Phones')

"what is the customer where product is Smartwatch"
  -> SELECT customer FROM ventas WHERE LOWER(product) = LOWER('Smartwatch')
```

Aun asi, el prototipo tiene limites claros:

- Si la pregunta usa una palabra que no esta en `COLUMN_SYNONYMS`, la
  consulta puede fallar al ejecutarse (se muestra el error en pantalla en vez
  de arriesgarse a ejecutar algo incorrecto).
- Preguntas que requieren varias tablas o subconsultas (WikiSQL solo entrena
  con una tabla por ejemplo).
- Preguntas en espanol: el modelo fue entrenado en ingles, asi que hay que
  traducir la pregunta antes de enviarla (una extension natural del proyecto
  seria anadir un paso de traduccion automatica).

Estas limitaciones son, en si mismas, una buena leccion: los modelos
Text-to-SQL de hoy son excelentes asistentes para consultas exploratorias
sencillas, pero todavia necesitan una capa de validacion humana o automatica
antes de confiar en ellos para produccion.

## Conclusion

Combinar una base de datos SQL con un modelo de IA no requiere infraestructura
compleja: con un modelo publico de Hugging Face, unas 100 lineas de Python y
una capa de sanitizacion cuidadosa, es posible construir un prototipo
funcional de "conversacion con la base de datos" en una tarde. El reto
interesante no esta en generar el SQL, sino en decidir cuanto confiar en el
antes de ejecutarlo.

## Referencias

- Como comunicarse con cualquier base de datos mediante IA: crea tu propio
  extractor de datos con consultas SQL.
- Texto a SQL — Hugging Face.
- Como crear un generador de consultas SQL a partir de texto con Streamlit y
  Hugging Face (Medium), por Kuhelidey.
- Codigo completo: https://github.com/JhonyVargas/text-to-sql-ia
