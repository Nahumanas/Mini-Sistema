"""Respaldos: copiar la base, restaurarla en una base vacía y ABRIR los datos con el código de recuperación.

Es la prueba completa que el workflow "Respaldo" hace cada semana con la base real (menos el último paso,
que necesita el código de recuperación y por eso lo corre Nahuel en su compu)."""

import os
import subprocess
import uuid
from decimal import Decimal
from pathlib import Path

import pyrage
import pytest
from fastapi.testclient import TestClient

from app import gimnasio as g
from respaldo import paquete
from respaldo.paquete import CopiaInservible
from respaldo.probar_descifrado import abrir_dueno

from .conftest import BASE, PIN_DE_PRUEBA, _psql, token_para

RESPALDO = Path(__file__).resolve().parents[1] / "respaldo"


def _dueno_con_frase(email: str) -> tuple[dict, str]:
    """Un dueño invitado que activó el cifrado. Devuelve sus encabezados (con llave de jefe) y su frase."""
    from app.main import app

    uid = str(uuid.uuid4())
    _psql("-d", BASE, "-c", f"insert into auth.users (id, email, invited_at) values ('{uid}', '{email}', now())")
    encabezados = {"Authorization": f"Bearer {token_para(uid, email)}"}
    cliente = TestClient(app)
    assert cliente.put("/yo/pin", json={"nuevo": PIN_DE_PRUEBA}, headers=encabezados).status_code == 200
    frase = cliente.get("/yo/cifrado/frase-nueva", headers=encabezados).json()["frase"]
    r = cliente.post("/yo/cifrado/activar", json={"pin": PIN_DE_PRUEBA, "frase": frase, "acepto": True}, headers=encabezados)
    assert r.status_code == 200, r.text
    return {**encabezados, "X-Llave": r.json()["llave"]}, frase


def _correr(*comando: str, **entorno: str) -> subprocess.CompletedProcess:
    r = subprocess.run(comando, capture_output=True, text=True, check=False, env={**os.environ, **entorno})
    assert r.returncode == 0, r.stdout + r.stderr
    return r


@pytest.fixture(scope="module")
def respaldo(cliente, tmp_path_factory):
    """Datos de verdad cargados por la API, copiados con hacer-respaldo.sh."""
    ana, frase = _dueno_con_frase("ana.respaldo@gmail.com")
    kiosco = cliente.post("/comercios", json={"nombre": "Kiosco", "rubro": "kiosco"}, headers=ana).json()["id"]
    gym = cliente.post("/comercios", json={"nombre": "Gym", "rubro": "gimnasio"}, headers=ana).json()["id"]
    alfajor = cliente.post(f"/comercios/{kiosco}/productos", json={
        "nombre": "Alfajor\tcon tab y \\barra", "precioVenta": 1500, "costo": 900, "stock": 10}, headers=ana).json()
    cliente.post(f"/comercios/{kiosco}/caja/abrir", json={"responsable": "Ana", "montoInicial": 1000}, headers=ana)
    venta = cliente.post(f"/comercios/{kiosco}/ventas", json={
        "items": [{"productoId": alfajor["id"], "cantidad": 2}], "medioPago": "efectivo", "vendidoPor": "Ana"}, headers=ana)
    assert venta.status_code == 201, venta.text
    cliente.post(f"/comercios/{kiosco}/gastos", json={"fecha": str(g.hoy()), "categoria": "Luz", "monto": 5000}, headers=ana)
    cliente.post(f"/comercios/{gym}/socios", json={"nombre": "Lucía Ñandú", "dni": "30111222"}, headers=ana)

    carpeta = tmp_path_factory.mktemp("respaldo")
    _correr("bash", str(RESPALDO / "hacer-respaldo.sh"), str(carpeta), BASE_URL=os.environ["DATABASE_URL"])
    return {"carpeta": carpeta, "frase": frase, "kiosco": kiosco, "gym": gym}


def test_la_copia_trae_los_datos_y_sus_llaves_juntos(respaldo):
    carpeta = respaldo["carpeta"]
    assert sorted(p.name for p in carpeta.iterdir()) == sorted([*paquete.ARCHIVOS, paquete.RESUMEN])
    tablas = paquete.leer_tablas((carpeta / paquete.DATOS).read_text(encoding="utf-8"))
    for tabla in ("public.claves_comercio", "public.cifrado_duenos", "public.ventas", "auth.users", "privado.clientes"):
        assert tabla in tablas, tabla
    assert paquete.problemas_de_llaves(tablas) == []
    # En la copia los datos del negocio siguen cifrados: no aparece ni el nombre del producto ni el del socio
    texto = (carpeta / paquete.DATOS).read_text(encoding="utf-8")
    assert "Alfajor" not in texto and "Ñandú" not in texto


def test_se_restaura_en_una_base_vacia_y_queda_igual(respaldo):
    r = _correr("bash", str(RESPALDO / "restaurar-y-controlar.sh"), str(respaldo["carpeta"]), "mantenete_prueba_restaurada")
    assert "La restauración coincide con la copia" in r.stdout
    _psql("-d", "postgres", "-c", "drop database if exists mantenete_prueba_restaurada")


def test_cerrado_con_la_llave_de_respaldo_y_abierto_con_el_codigo_de_recuperacion(respaldo, tmp_path):
    identidad = pyrage.x25519.Identity.generate()
    llave = tmp_path / "llave-respaldo.txt"
    llave.write_text(f"# prueba\n{identidad}\n", encoding="utf-8")
    cerrado = paquete.empaquetar(respaldo["carpeta"], tmp_path / "respaldo.tar.gz.age", str(identidad.to_public()))
    assert b"claves_comercio" not in cerrado.read_bytes()  # cerrado no se lee nada

    archivos = paquete.abrir_paquete(cerrado, llave)
    tablas = paquete.leer_tablas(archivos[paquete.DATOS].decode("utf-8"))
    abierto = abrir_dueno(tablas, "Ana.Respaldo@gmail.com", respaldo["frase"].lower())  # con minúsculas también vale
    assert abierto.todo_bien, abierto.no_abrieron
    assert abierto.comercios == sorted([respaldo["kiosco"], respaldo["gym"]])
    assert [p["nombre"] for p in abierto.tablas["productos"]] == ["Alfajor\tcon tab y \\barra"]
    venta = abierto.tablas["ventas"][0]
    assert (venta["subtotal"], venta["descuento"], venta["total"]) == (Decimal("3000.00"), Decimal("0.00"), Decimal("3000.00"))
    assert abierto.tablas["socios"][0]["nombre"] == "Lucía Ñandú"
    assert abierto.tablas["gastos"][0]["monto"] == Decimal("5000.00")


def test_otra_llave_o_otro_codigo_no_abren(respaldo, tmp_path):
    publica = pyrage.x25519.Identity.generate().to_public()
    cerrado = paquete.empaquetar(respaldo["carpeta"], tmp_path / "r.tar.gz.age", str(publica))
    otra = tmp_path / "otra.txt"
    otra.write_text(f"{pyrage.x25519.Identity.generate()}\n", encoding="utf-8")
    with pytest.raises(CopiaInservible, match="no abre este paquete"):
        paquete.abrir_paquete(cerrado, otra)

    tablas = paquete.leer_tablas((respaldo["carpeta"] / paquete.DATOS).read_text(encoding="utf-8"))
    with pytest.raises(CopiaInservible, match="no abre la clave"):
        abrir_dueno(tablas, "ana.respaldo@gmail.com", "ABCD-EFGH-JKLM-NPQR-STUV-WXYZ")


def test_sin_las_llaves_del_cifrado_la_copia_no_se_acepta(respaldo, tmp_path):
    """La regla de oro: si claves_comercio no viaja con los datos, el respaldo se frena (sería basura)."""
    for archivo in paquete.ARCHIVOS:
        (tmp_path / archivo).write_bytes((respaldo["carpeta"] / archivo).read_bytes())
    datos = (tmp_path / paquete.DATOS).read_text(encoding="utf-8")
    sin_claves = datos.replace("COPY public.claves_comercio ", "COPY public.otra_cosa ")
    (tmp_path / paquete.DATOS).write_text(sin_claves, encoding="utf-8")
    with pytest.raises(CopiaInservible, match="Falta la tabla public.claves_comercio"):
        paquete.resumir(tmp_path)


def test_si_un_archivo_cambia_despues_de_copiar_se_avisa(respaldo, tmp_path):
    for archivo in [*paquete.ARCHIVOS, paquete.RESUMEN]:
        (tmp_path / archivo).write_bytes((respaldo["carpeta"] / archivo).read_bytes())
    with open(tmp_path / paquete.DATOS, "a", encoding="utf-8") as f:
        f.write("-- tocado\n")
    with pytest.raises(CopiaInservible, match="cambió"):
        paquete.controlar(tmp_path, os.environ["DATABASE_URL"])


def test_lee_los_escapes_de_copy():
    texto = "COPY public.x (a, b, c) FROM stdin;\nuno\\tdos\t\\N\tbarra\\\\ y \\n salto\n\\.\n"
    assert paquete.leer_tablas(texto) == {"public.x": [{"a": "uno\tdos", "b": None, "c": "barra\\ y \n salto"}]}
