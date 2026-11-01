"""Configuración de la API. Todo sale de variables de entorno (en Render: pestaña Environment)."""

import os

# Conexión a la base de Supabase (Project Settings → Database → Connection string, modo "Transaction pooler").
# Lleva la contraseña de la base: es SECRETA, solo va en Render.
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# La dirección del proyecto de Supabase (no es secreta). Con ella se bajan las llaves públicas
# que firman los tokens de los usuarios, para comprobar que un token es de verdad.
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")

# Solo para proyectos viejos de Supabase que firman con un secreto compartido (HS256). Si tu proyecto
# usa "JWT Signing Keys" (lo normal desde 2025), dejala vacía. Si se usa, es SECRETA.
SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET", "")

# Cifrado (etapa 5). Las dos son SECRETAS y van solo en Render (botón "Generate": 32 caracteres o más).
# PIMIENTA_CIFRADO: se mezcla con los PIN y códigos. NO SE CAMBIA NUNCA: si se pierde o se cambia, los PIN
#   dejan de abrir los datos y cada dueño tiene que entrar con su frase de recuperación. Guardá una copia en papel.
# SECRETO_SESION: cierra las "llaves de sesión" que la página guarda mientras alguien está adentro. Si se cambia,
#   no se pierde nada: todos vuelven a poner su PIN o código.
PIMIENTA_CIFRADO = os.environ.get("PIMIENTA_CIFRADO", "")
SECRETO_SESION = os.environ.get("SECRETO_SESION", "")

# Desde qué páginas se puede llamar a la API (las de Mantenete y las vistas previas de Vercel).
ORIGENES_PERMITIDOS = [
    "https://mantenete-app.vercel.app",
    "https://mantenete.vercel.app",
    "https://app.mantenete.com.ar",
    "http://localhost:3000",
]
ORIGENES_VISTA_PREVIA = r"https://mantenete-[a-z0-9-]+-nahuel-900e\.vercel\.app"
