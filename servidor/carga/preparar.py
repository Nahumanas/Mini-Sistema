"""Carga los datos de la prueba de carga: N dueños, cada uno con su comercio, sus productos y ventas viejas.

Todo pasa por la API (como lo haría la página), así los datos quedan cifrados igual que los de verdad.
Al final escribe carga/.local/usuarios.json con el token y la llave de cada dueño (para locustfile.py).

Dos formas (desde la carpeta servidor/):

  GRATIS, en tu compu (antes hay que dejar corriendo:  python carga/servidor_local.py --nueva-base)
      python carga/preparar.py --local

  Contra el proyecto Supabase DE PRUEBAS (NUNCA el de los clientes). Ver carga/README.md.
      python carga/preparar.py --supabase --api https://<la-api-de-pruebas>.onrender.com

Para no esperar tanto, se puede achicar: --duenos 10 --productos 100 --ventas 20

Los tokens de Supabase vencen a la hora. Si preparar tardó mucho, justo antes de Locust renová tokens y llaves:
      python carga/preparar.py --supabase --renovar
"""

import argparse
import json
import os
import random
import secrets
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import jwt
from cryptography.hazmat.primitives import serialization

AQUI = Path(__file__).resolve().parent
LOCAL = AQUI / ".local"
PIN = "4826"
DOMINIO = "carga.mantenete.test"  # mails inventados: nunca llegan a nadie
CATEGORIAS = ["Bebidas", "Golosinas", "Almacén", "Limpieza", "Lácteos", "Panadería", "Cigarrillos", "Varios"]


# ---------------------------------------------------------------- los usuarios (tokens)


def usuarios_locales(cantidad: int) -> list[dict]:
    """En la base local: se crean como si Nahuel los hubiera invitado y se firman los tokens con la llave de prueba."""
    from servidor_local import BASE, URL_FALSA, preparar_secretos

    llave = serialization.load_pem_private_key(preparar_secretos()["llave_tokens"].encode(), None)
    usuarios = []
    valores = []
    for n in range(cantidad):
        uid, email = str(uuid.uuid4()), f"dueno{n + 1:03d}@{DOMINIO}"
        valores.append(f"('{uid}', '{email}', now())")
        ahora = int(time.time())
        token = jwt.encode({"sub": uid, "email": email, "aud": "authenticated", "role": "authenticated",
                            "iss": f"{URL_FALSA}/auth/v1", "iat": ahora, "exp": ahora + 24 * 3600}, llave, algorithm="ES256")
        usuarios.append({"email": email, "token": token})
    subprocess.run(["psql", "-q", "-v", "ON_ERROR_STOP=1", "-d", BASE, "-c",
                    "insert into auth.users (id, email, invited_at) values " + ", ".join(valores)],
                   check=True, capture_output=True)
    return usuarios


def _proyecto_de_pruebas() -> str:
    url = os.environ["SUPABASE_URL"].rstrip("/")
    if "ltxiykufdxoblkbfgrim" in url or "ltxiykufdxoblkbfgrim" in os.environ.get("DATABASE_URL", ""):
        sys.exit("¡Ese es el proyecto de los clientes! La prueba de carga va SOLO contra el proyecto de pruebas.")
    return url


def entrar(c: httpx.Client, url: str, email: str, clave: str) -> str:
    r = c.post(f"{url}/auth/v1/token?grant_type=password", headers={"apikey": os.environ["SUPABASE_PUBLISHABLE_KEY"]},
               json={"email": email, "password": clave})
    if r.status_code != 200:
        sys.exit(f"No se pudo entrar con {email}: {r.status_code} {r.text}\n"
                 "¿Está prendido Email (con contraseña) en Authentication → Sign In / Providers?")
    return r.json()["access_token"]


def usuarios_supabase(cantidad: int) -> list[dict]:
    """En el proyecto Supabase de pruebas: crea los usuarios con contraseña, los marca como invitados
    (así el trigger les arma la ficha de dueño) y entra con cada uno para tener su token."""
    url = _proyecto_de_pruebas()
    secreta = os.environ["SUPABASE_SECRET_KEY"]
    base = os.environ["DATABASE_URL"]

    admin = {"apikey": secreta}
    if not secreta.startswith("sb_"):  # las llaves viejas (JWT) también van en Authorization
        admin["Authorization"] = f"Bearer {secreta}"
    clave = secrets.token_urlsafe(18)
    emails = [f"dueno{n + 1:03d}@{DOMINIO}" for n in range(cantidad)]
    with httpx.Client(timeout=30) as c:
        for email in emails:
            r = c.post(f"{url}/auth/v1/admin/users", headers=admin,
                       json={"email": email, "password": clave, "email_confirm": True})
            if r.status_code not in (200, 201, 422):  # 422 = ya existía de una corrida anterior
                sys.exit(f"No se pudo crear {email}: {r.status_code} {r.text}")
            if r.status_code == 422:
                c.put(f"{url}/auth/v1/admin/users/{_id_de(c, url, admin, email)}", headers=admin, json={"password": clave})

        import psycopg

        with psycopg.connect(base, prepare_threshold=None) as con:
            con.execute("update auth.users set invited_at = now() where email like %s and invited_at is null",
                        (f"%@{DOMINIO}",))

        # La contraseña queda en carga/.local/usuarios.json (solo en tu compu) para poder renovar los tokens
        return [{"email": email, "token": entrar(c, url, email, clave), "clave": clave} for email in emails]


def renovar() -> None:
    """Tokens nuevos (vencen a la hora) y llaves nuevas, sin volver a cargar nada."""
    archivo = LOCAL / "usuarios.json"
    datos = json.loads(archivo.read_text())
    url = _proyecto_de_pruebas()
    with httpx.Client(timeout=60) as c:
        for d in datos["duenos"]:
            d["token"] = entrar(c, url, d["email"], d["clave"])
            r = c.post(f"{datos['api']}/yo/pin/verificar", json={"pin": PIN}, headers={"Authorization": f"Bearer {d['token']}"})
            r.raise_for_status()
            d["llave"] = r.json()["llave"]
    archivo.write_text(json.dumps(datos))
    print(f"Renovados {len(datos['duenos'])} tokens y llaves. Ahora:  locust -f carga/locustfile.py")


def _id_de(c: httpx.Client, url: str, admin: dict, email: str) -> str:
    pagina = 1
    while True:
        r = c.get(f"{url}/auth/v1/admin/users", headers=admin, params={"page": pagina, "per_page": 1000}).json()
        for u in r.get("users", []):
            if u["email"] == email:
                return u["id"]
        if not r.get("users"):
            sys.exit(f"No encontré a {email}")
        pagina += 1


# ---------------------------------------------------------------- el comercio de cada dueño


def preparar_dueno(api: str, usuario: dict, productos: int, ventas: int) -> dict:
    encabezados = {"Authorization": f"Bearer {usuario['token']}"}
    with httpx.Client(base_url=api, headers=encabezados, timeout=120) as c:
        def pedir(metodo: str, ruta: str, **kw):
            r = c.request(metodo, ruta, **kw)
            if r.status_code >= 400:
                raise RuntimeError(f"{usuario['email']}: {metodo} {ruta} → {r.status_code} {r.text[:200]}")
            return r.json()

        yo = pedir("GET", "/inicio")
        if yo["dueno"]["cifradoActivo"]:  # de una corrida anterior: entra con el PIN
            llave = pedir("POST", "/yo/pin/verificar", json={"pin": PIN})["llave"]
        else:
            if not yo["dueno"]["pinConfigurado"]:
                pedir("PUT", "/yo/pin", json={"nuevo": PIN})
            frase = pedir("GET", "/yo/cifrado/frase-nueva")["frase"]
            llave = pedir("POST", "/yo/cifrado/activar", json={"pin": PIN, "frase": frase, "acepto": True})["llave"]
        c.headers["X-Llave"] = llave

        comercios = pedir("GET", "/comercios")
        if comercios:
            cid = comercios[0]["id"]
        else:
            cid = pedir("POST", "/comercios", json={"nombre": f"Kiosco {usuario['email'].split('@')[0]}", "rubro": "kiosco"})["id"]
            al_azar = random.Random(cid)
            filas = [{"codigo": f"77900{n:05d}", "nombre": f"Producto {n:05d}", "categoria": al_azar.choice(CATEGORIAS),
                      "precioVenta": al_azar.randint(5, 300) * 100, "costo": al_azar.randint(3, 200) * 100,
                      "stock": al_azar.randint(50, 500), "stockMinimo": al_azar.randint(0, 20)} for n in range(productos)]
            for desde in range(0, len(filas), 5000):
                pedir("POST", f"/comercios/{cid}/productos/importar", json={"filas": filas[desde:desde + 5000]})

        ids = [p["id"] for p in pedir("GET", f"/comercios/{cid}/productos")]
        if pedir("GET", f"/comercios/{cid}/caja") is None:
            pedir("POST", f"/comercios/{cid}/caja/abrir", json={"responsable": "Caja 1", "montoInicial": 10000})
        al_azar = random.Random()
        for _ in range(ventas):  # el historial: así los reportes tienen qué leer
            items = [{"productoId": p, "cantidad": al_azar.randint(1, 3)} for p in al_azar.sample(ids, al_azar.randint(1, 4))]
            pedir("POST", f"/comercios/{cid}/ventas", json={"items": items, "vendidoPor": "Caja 1",
                                                           "medioPago": al_azar.choice(["efectivo", "debito", "transferencia"])})
        return {**usuario, "llave": llave, "comercioId": cid, "productos": ids}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    donde = parser.add_mutually_exclusive_group(required=True)
    donde.add_argument("--local", action="store_true", help="base y API en tu compu (gratis)")
    donde.add_argument("--supabase", action="store_true", help="el proyecto Supabase DE PRUEBAS (variables en carga/README.md)")
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--duenos", type=int, default=100)
    parser.add_argument("--productos", type=int, default=500, help="por comercio (100 × 500 = 50.000)")
    parser.add_argument("--ventas", type=int, default=200, help="ventas viejas por comercio (100 × 200 = 20.000)")
    parser.add_argument("--hilos", type=int, default=10, help="cuántos dueños se preparan a la vez")
    parser.add_argument("--renovar", action="store_true", help="con --supabase: solo renueva tokens y llaves")
    args = parser.parse_args()
    if args.renovar:
        return renovar() if args.supabase else sys.exit("--renovar es solo para --supabase (los tokens locales duran 24 h).")

    if args.supabase and ("127.0.0.1" in args.api or "localhost" in args.api):
        sys.exit("Con --supabase pasá --api con la dirección de la API DE PRUEBAS (la que usa el proyecto de pruebas).")
    if "mini-sistemamini-sistema-api" in args.api:
        sys.exit("¡Esa es la API de los clientes! La prueba de carga va SOLO contra la API de pruebas.")

    print(f"Creando {args.duenos} dueños…")
    usuarios = usuarios_locales(args.duenos) if args.local else usuarios_supabase(args.duenos)
    print(f"Preparando sus comercios ({args.productos} productos y {args.ventas} ventas cada uno). Puede tardar…")
    inicio = time.monotonic()
    listos = []
    with ThreadPoolExecutor(max_workers=args.hilos) as hilos:
        for n, dueno in enumerate(hilos.map(lambda u: preparar_dueno(args.api, u, args.productos, args.ventas), usuarios), 1):
            listos.append(dueno)
            if n % 10 == 0 or n == len(usuarios):
                print(f"  {n}/{len(usuarios)} listos ({time.monotonic() - inicio:.0f} s)")
    LOCAL.mkdir(exist_ok=True)
    (LOCAL / ".gitignore").write_text("*\n")
    (LOCAL / "usuarios.json").write_text(json.dumps({"api": args.api, "duenos": listos}))
    print(f"Listo: {LOCAL / 'usuarios.json'}. Ahora:  locust -f carga/locustfile.py")


if __name__ == "__main__":
    sys.path.insert(0, str(AQUI))
    main()
