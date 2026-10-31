"""Configuración de la API. Todo sale de variables de entorno (en Railway: pestaña Variables)."""

import os

# Conexión a la base de Supabase (Project Settings → Database → Connection string, modo "Transaction pooler").
# Lleva la contraseña de la base: es SECRETA, solo va en Railway.
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# La dirección del proyecto de Supabase (no es secreta). Con ella se bajan las llaves públicas
# que firman los tokens de los usuarios, para comprobar que un token es de verdad.
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")

# Solo para proyectos viejos de Supabase que firman con un secreto compartido (HS256). Si tu proyecto
# usa "JWT Signing Keys" (lo normal desde 2025), dejala vacía. Si se usa, es SECRETA.
SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET", "")

# Desde qué páginas se puede llamar a la API (las de Mantenete y las vistas previas de Vercel).
ORIGENES_PERMITIDOS = [
    "https://mantenete-app.vercel.app",
    "https://mantenete.vercel.app",
    "https://app.mantenete.com.ar",
    "http://localhost:3000",
]
ORIGENES_VISTA_PREVIA = r"https://mantenete-[a-z0-9-]+-nahuel-900e\.vercel\.app"
