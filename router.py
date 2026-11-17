"""Enrutador semántico de correos: asigna cada email al departamento más parecido.

Uso:
    python router.py "asunto" "cuerpo del correo"
    python router.py            # ejecuta la autoprueba
"""
import sys

from sentence_transformers import SentenceTransformer

# Edita aquí: departamento -> frases de ejemplo. Más ejemplos = mejor precisión.
DEPARTAMENTOS = {
    "soporte": [
        "no puedo iniciar sesión en mi cuenta",
        "la aplicación da un error al abrir",
        "olvidé mi contraseña",
        "el sistema no funciona, está caído",
        "tengo un problema técnico con el servicio",
    ],
    "facturacion": [
        "me cobraron dos veces este mes",
        "necesito una copia de mi factura",
        "quiero solicitar un reembolso",
        "cuál es el estado de mi pago",
        "actualizar mi método de pago o tarjeta",
    ],
    "ventas": [
        "quiero información sobre precios y planes",
        "me interesa contratar el servicio para mi empresa",
        "pueden enviarme una cotización",
        "quisiera agendar una demostración del producto",
        "tienen descuentos por volumen",
        "cuánto cuesta la licencia para mi equipo",
        "solicito un presupuesto",
    ],
    "rrhh": [
        "adjunto mi currículum para la vacante",
        "quiero postularme a un puesto de trabajo",
        "consulta sobre mi nómina o vacaciones",
        "solicito un certificado laboral",
        "información sobre el proceso de selección",
    ],
}
FALLBACK = "general"  # si nada se parece lo suficiente
UMBRAL = 0.40  # sube para ser más estricto, baja si cae mucho en "general"

_modelo = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
_nombres = [d for d, ejs in DEPARTAMENTOS.items() for _ in ejs]
_vectores = _modelo.encode(
    [e for ejs in DEPARTAMENTOS.values() for e in ejs], normalize_embeddings=True
)


def enrutar(asunto: str, cuerpo: str = "") -> tuple[str, float]:
    """Devuelve (departamento, similitud). Usa el ejemplo más cercano (vecino más próximo)."""
    # ponytail: solo los primeros 1000 caracteres; el modelo trunca textos largos de todos modos
    texto = f"{asunto}\n{cuerpo}"[:1000]
    v = _modelo.encode(texto, normalize_embeddings=True)
    sims = _vectores @ v
    i = int(sims.argmax())
    score = float(sims[i])
    return (_nombres[i] if score >= UMBRAL else FALLBACK), score


def _autoprueba():
    casos = [
        ("Error al entrar", "Me sale pantalla en blanco cuando intento loguearme", "soporte"),
        ("Cargo duplicado", "En mi tarjeta aparece el cobro repetido", "facturacion"),
        ("Presupuesto", "Somos 50 empleados, ¿cuánto costaría la licencia?", "ventas"),
        ("Oferta de empleo", "Me gustaría trabajar con ustedes, envío mi CV", "rrhh"),
    ]
    for asunto, cuerpo, esperado in casos:
        dep, score = enrutar(asunto, cuerpo)
        print(f"{dep:12} {score:.2f}  {asunto}")
        assert dep == esperado, f"'{asunto}' -> {dep}, esperado {esperado}"
    print("OK")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        dep, score = enrutar(sys.argv[1], " ".join(sys.argv[2:]))
        print(f"{dep} ({score:.2f})")
    else:
        _autoprueba()
