"""Pruebas de la parte 4: el gimnasio (socios, cuotas, planes, clases, reservas con lista de espera e ingreso por DNI).
Siempre con un dueño "intruso" que no puede tocar nada de otro."""

from datetime import timedelta

from app import gimnasio as g

from .conftest import crear_usuario
from .test_parte_3 import _sql


def _gimnasio(cliente, quien, nombre="Gym"):
    """Un gimnasio con la caja abierta, una actividad y un plan de 8 clases por mes."""
    gym = cliente.post("/comercios", json={"nombre": nombre, "rubro": "gimnasio"}, headers=quien).json()
    gid = gym["id"]
    cliente.post(f"/comercios/{gid}/caja/abrir", json={"responsable": "Recepción", "montoInicial": 0}, headers=quien)
    crossfit = cliente.post(f"/comercios/{gid}/disciplinas", json={"nombre": "Crossfit"}, headers=quien).json()
    plan = cliente.post(f"/comercios/{gid}/planes", json={"nombre": "8 clases", "precio": 28000, "duracionMeses": 1,
                                                          "cantidadClases": 8, "actividades": []}, headers=quien).json()
    return gid, crossfit, plan


def _socio_al_dia(cliente, quien, gid, plan, dni, nombre="Socio"):
    socio = cliente.post(f"/comercios/{gid}/socios", json={"nombre": nombre, "dni": dni}, headers=quien).json()
    r = cliente.post(f"/comercios/{gid}/cuotas", json={"socioId": socio["id"], "planId": plan["id"], "medioPago": "efectivo",
                                                       "monto": plan["precio"], "vence": str(g.hoy() + timedelta(days=30)),
                                                       "cobradaPor": "Recepción"}, headers=quien)
    assert r.status_code == 201, r.text
    return r.json()["socio"]


def _clase_de_manana(cliente, quien, gid, disciplina, cupo=1, hora="23:00"):
    fecha = g.hoy() + timedelta(days=1)
    clase = cliente.post(f"/comercios/{gid}/clases", json={"disciplinaId": disciplina["id"], "diaSemana": fecha.weekday(),
                                                           "horaInicio": hora, "duracionMinutos": 60, "profesor": "Laura",
                                                           "cupoMaximo": cupo}, headers=quien).json()["clase"]
    return clase, str(fecha)


def test_socios_e_importar(cliente):
    ana = crear_usuario("ana.socios@gmail.com")
    beto = crear_usuario("beto.socios@gmail.com")
    gid, _, plan = _gimnasio(cliente, ana)

    r = cliente.post(f"/comercios/{gid}/socios", json={"nombre": "  Juan   Pérez ", "dni": "30.111.222", "email": "juan@x.com"}, headers=ana)
    assert r.status_code == 201
    juan = r.json()
    assert juan["nombre"] == "Juan Pérez" and juan["dni"] == "30111222" and juan["vence"] is None and juan["alta"] == str(g.hoy())
    assert cliente.post(f"/comercios/{gid}/socios", json={"nombre": "Otro", "dni": "30111222"}, headers=ana).status_code == 409
    assert cliente.post(f"/comercios/{gid}/socios", json={"nombre": "Otro", "dni": "123"}, headers=ana).status_code == 422
    assert cliente.post(f"/comercios/{gid}/socios", json={"nombre": "Otro", "dni": "40111222", "email": "mal"}, headers=ana).status_code == 422
    assert cliente.post(f"/comercios/{gid}/socios", json={"nombre": "Otro", "dni": "40111222"}, headers=beto).status_code == 404

    maria = cliente.post(f"/comercios/{gid}/socios", json={"nombre": "María", "dni": "40111222"}, headers=ana).json()
    assert cliente.patch(f"/socios/{maria['id']}", json={"nombre": "María", "dni": "30111222"}, headers=ana).status_code == 409
    assert cliente.patch(f"/socios/{maria['id']}", json={"nombre": "María Gómez", "dni": "40111222", "telefono": "11 5555"}, headers=beto).status_code == 404
    assert cliente.patch(f"/socios/{maria['id']}", json={"nombre": "María Gómez", "dni": "40111222", "telefono": "11 5555"}, headers=ana).json()["telefono"] == "11 5555"

    vence = str(g.hoy() + timedelta(days=20))
    r = cliente.post(f"/comercios/{gid}/socios/importar", json={"filas": [
        {"nombre": "Juan Pérez", "dni": "30111222", "telefono": "", "email": "", "planId": plan["id"], "vence": vence},  # ya estaba
        {"nombre": "Laura Díaz", "dni": "35123456", "telefono": "11 4444", "email": "", "planId": None, "vence": None},
    ]}, headers=ana).json()
    assert (r["nuevos"], r["actualizados"]) == (1, 1)
    juan = next(s for s in r["socios"] if s["dni"] == "30111222")
    assert juan["email"] == "juan@x.com"  # lo vacío del Excel no borra lo que tenía
    assert juan["vence"] == vence and juan["planId"] == plan["id"] and juan["clasesRestantes"] == 8
    # Un plan de otro gimnasio no se puede usar
    _, _, plan_beto = _gimnasio(cliente, beto)
    malo = {"filas": [{"nombre": "X", "dni": "36123456", "planId": plan_beto["id"], "vence": vence}]}
    assert cliente.post(f"/comercios/{gid}/socios/importar", json=malo, headers=ana).status_code == 422
    assert cliente.post(f"/comercios/{gid}/socios/importar", json=malo, headers=beto).status_code == 404


def test_planes_actividades_y_reglas(cliente):
    ana = crear_usuario("ana.planes@gmail.com")
    beto = crear_usuario("beto.planes@gmail.com")
    gid, crossfit, plan = _gimnasio(cliente, ana)
    assert plan["actividades"] == [] and plan["duracionDias"] is None

    # El mismo nombre (aunque cambien los acentos o las mayúsculas) no se repite
    assert cliente.post(f"/comercios/{gid}/disciplinas", json={"nombre": "CROSSFÍT"}, headers=ana).status_code == 409
    yoga = cliente.post(f"/comercios/{gid}/disciplinas", json={"nombre": "Yoga"}, headers=ana).json()
    assert cliente.patch(f"/disciplinas/{yoga['id']}", json={"nombre": "Crossfit"}, headers=ana).status_code == 409
    assert cliente.patch(f"/disciplinas/{yoga['id']}", json={"nombre": "Yoga", "activa": False}, headers=ana).json()["activa"] is False
    assert cliente.patch(f"/disciplinas/{yoga['id']}", json={"nombre": "Yoga"}, headers=beto).status_code == 404

    trimestral = {"nombre": "Trimestral Crossfit", "precio": 75000, "duracionMeses": 3, "cantidadClases": 8, "actividades": [crossfit["id"]]}
    r = cliente.post(f"/comercios/{gid}/planes", json=trimestral, headers=ana)
    assert r.status_code == 201 and r.json()["actividades"] == [crossfit["id"]]
    pase = cliente.post(f"/comercios/{gid}/planes", json={"nombre": "Pase 15 días", "precio": 9000, "duracionDias": 15}, headers=ana).json()
    assert pase["duracionMeses"] is None and pase["duracionDias"] == 15 and pase["cantidadClases"] is None
    assert cliente.post(f"/comercios/{gid}/planes", json={**trimestral, "precio": 0}, headers=ana).status_code == 422
    assert cliente.post(f"/comercios/{gid}/planes", json={"nombre": "X", "precio": 1}, headers=ana).status_code == 422  # sin duración
    # Una actividad de otro gimnasio no entra en el plan
    otro, crossfit_beto, _ = _gimnasio(cliente, beto)
    assert cliente.post(f"/comercios/{gid}/planes", json={**trimestral, "actividades": [crossfit_beto["id"]]}, headers=ana).status_code == 422
    assert cliente.put(f"/planes/{plan['id']}", json={**trimestral, "activo": False}, headers=beto).status_code == 404
    assert cliente.put(f"/planes/{plan['id']}", json={**trimestral, "nombre": "8 clases", "activo": False}, headers=ana).json()["activo"] is False

    reglas = {"horasCancelacion": 4, "clasesSobrantes": "se_acumulan", "vencimiento": "fin_de_mes", "diasAviso": 5}
    assert cliente.put(f"/comercios/{gid}/reglas-gimnasio", json=reglas, headers=ana).json()["horasCancelacion"] == 4
    assert cliente.put(f"/comercios/{gid}/reglas-gimnasio", json={**reglas, "diasAviso": 3}, headers=ana).json()["diasAviso"] == 3
    assert cliente.put(f"/comercios/{gid}/reglas-gimnasio", json=reglas, headers=beto).status_code == 404

    datos = cliente.get("/inicio", headers=ana).json()
    assert {d["nombre"] for d in datos["disciplinas"]} == {"Crossfit", "Yoga"}
    assert len(datos["planes"]) == 3 and datos["reglasGimnasio"][0]["clasesSobrantes"] == "se_acumulan"
    assert not cliente.get("/inicio", headers=beto).json()["reglasGimnasio"]


def test_cuota_entra_a_la_caja_y_se_puede_anular(cliente):
    ana = crear_usuario("ana.cuotas@gmail.com")
    beto = crear_usuario("beto.cuotas@gmail.com")
    gid, _, plan = _gimnasio(cliente, ana)
    socio = cliente.post(f"/comercios/{gid}/socios", json={"nombre": "Juan", "dni": "30111222"}, headers=ana).json()
    vence = str(g.hoy() + timedelta(days=30))
    cuota = {"socioId": socio["id"], "planId": plan["id"], "medioPago": "efectivo", "monto": 25000, "vence": vence, "cobradaPor": "Recepción"}

    assert cliente.post(f"/comercios/{gid}/cuotas", json={**cuota, "vence": str(g.hoy() - timedelta(days=1))}, headers=ana).status_code == 422
    assert cliente.post(f"/comercios/{gid}/cuotas", json=cuota, headers=beto).status_code == 404
    r = cliente.post(f"/comercios/{gid}/cuotas", json=cuota, headers=ana)
    assert r.status_code == 201
    r = r.json()
    assert r["socio"]["vence"] == vence and r["socio"]["clasesRestantes"] == 8 and r["clases"] == 8
    assert r["cuota"]["clasesCargadas"] == 8 and r["cuota"]["venceAntes"] is None
    venta = r["venta"]
    assert venta["total"] == 25000 and venta["descuento"] == 3000 and venta["subtotal"] == 28000
    # Como en la página, la cuota va con el id del plan en negativo
    assert venta["items"] == [{"productoId": -plan["id"], "nombre": "Cuota 8 clases", "categoria": "Cuotas", "cantidad": 1,
                               "precioUnitario": 28000, "costoUnitario": 0}]

    # Entra al arqueo: al cerrar, el efectivo esperado la incluye
    caja = cliente.post(f"/comercios/{gid}/caja/cerrar", json={"efectivoContado": 25000}, headers=ana).json()
    assert caja["efectivoEsperado"] == 25000
    # Sin caja abierta no se cobra
    assert cliente.post(f"/comercios/{gid}/cuotas", json=cuota, headers=ana).status_code == 409

    # Anular la venta de la cuota deja al socio como estaba
    r = cliente.post(f"/cajas/{caja['id']}/anular-venta", json={"ventaId": venta["id"], "hechoPor": "Ana", "motivo": "Se cobró mal"}, headers=ana).json()
    assert r["socio"]["vence"] is None and r["socio"]["clasesRestantes"] == 0
    assert r["productos"] == []  # una cuota no devuelve nada al stock

    datos = cliente.get("/inicio", headers=ana).json()
    assert datos["cuotas"][0]["anulada"] is not None and datos["socios"][0]["dni"] == "30111222"
    assert not cliente.get("/inicio", headers=beto).json()["cuotas"]


def test_reservas_cupo_y_lista_de_espera(cliente):
    ana = crear_usuario("ana.reservas@gmail.com")
    beto = crear_usuario("beto.reservas@gmail.com")
    gid, crossfit, plan = _gimnasio(cliente, ana)
    juan = _socio_al_dia(cliente, ana, gid, plan, "30111222", "Juan")
    maria = _socio_al_dia(cliente, ana, gid, plan, "40111222", "María")
    sin_pagar = cliente.post(f"/comercios/{gid}/socios", json={"nombre": "Pedro", "dni": "35111222"}, headers=ana).json()
    clase, fecha = _clase_de_manana(cliente, ana, gid, crossfit, cupo=1)

    def reservar(socio, quien=ana):
        return cliente.post(f"/comercios/{gid}/reservas", json={"claseId": clase["id"], "socioId": socio["id"], "fecha": fecha,
                                                                "hechaPor": "Recepción"}, headers=quien)

    r = reservar(juan).json()
    assert r["estado"] == "reservado" and r["clasesRestantes"] == 7 and r["reserva"]["claseDescontada"] is True
    assert reservar(juan).status_code == 409  # ya está anotado
    r = reservar(maria).json()
    assert r["estado"] == "espera" and r["posicion"] == 1 and r["clasesRestantes"] == 8  # la espera no descuenta
    assert reservar(sin_pagar).status_code == 409
    assert reservar(juan, beto).status_code == 404
    otro_dia = cliente.post(f"/comercios/{gid}/reservas", json={"claseId": clase["id"], "socioId": juan["id"],
                                                                "fecha": str(g.hoy() + timedelta(days=2))}, headers=ana)
    assert otro_dia.status_code == 422

    reserva_juan = cliente.get("/inicio", headers=ana).json()["reservas"][0]
    assert cliente.post(f"/reservas/{reserva_juan['id']}/cancelar", json={"hechaPor": "X"}, headers=beto).status_code == 404
    # Juan cancela con tiempo: se le devuelve la clase y entra María (se le descuenta a ella)
    r = cliente.post(f"/reservas/{reserva_juan['id']}/cancelar", json={"hechaPor": "Recepción"}, headers=ana).json()
    assert r["devuelta"] is True and r["aTiempo"] is True and r["entraron"] == [{"socio": "María", "telefono": ""}]
    por_socio = {s["nombre"]: s["clasesRestantes"] for s in r["socios"]}
    assert por_socio == {"Juan": 8, "María": 7}
    assert {x["estado"] for x in r["reservas"]} == {"cancelado", "reservado"}
    assert cliente.post(f"/reservas/{reserva_juan['id']}/cancelar", json={}, headers=ana).status_code == 409

    # Agrandar el cupo hace entrar a la lista de espera
    reservar(juan)  # Juan vuelve: ahora queda en espera
    r = cliente.put(f"/clases/{clase['id']}", json={**{k: clase[k] for k in ("disciplinaId", "diaSemana", "horaInicio", "duracionMinutos", "profesor")},
                                                     "cupoMaximo": 2}, headers=ana).json()
    assert r["entraron"] == [{"socio": "Juan", "telefono": ""}] and r["socios"][0]["clasesRestantes"] == 7
    # Con reservas que vienen, no se le cambia el día
    cambio_de_dia = {**{k: clase[k] for k in ("disciplinaId", "horaInicio", "duracionMinutos")}, "diaSemana": (clase["diaSemana"] + 1) % 7, "cupoMaximo": 2}
    assert cliente.put(f"/clases/{clase['id']}", json=cambio_de_dia, headers=ana).status_code == 409

    # Dar de baja a María cancela su reserva sin devolverle la clase
    r = cliente.post(f"/socios/{maria['id']}/baja", json={"hechaPor": "Ana"}, headers=ana).json()
    assert r["canceladas"] == 1
    maria_ahora = next(s for s in r["socios"] if s["id"] == maria["id"])
    assert maria_ahora["activo"] is False and maria_ahora["clasesRestantes"] == 7
    assert cliente.post(f"/socios/{maria['id']}/reactivar", headers=ana).json()["activo"] is True

    # Sacar la clase de la grilla cancela lo que venía y devuelve las clases
    assert cliente.post(f"/clases/{clase['id']}/desactivar", json={"hechaPor": "Ana"}, headers=beto).status_code == 404
    r = cliente.post(f"/clases/{clase['id']}/desactivar", json={"hechaPor": "Ana"}, headers=ana).json()
    assert r["clase"]["activa"] is False and r["canceladas"] == 1 and r["socios"][0]["clasesRestantes"] == 8
    assert reservar(juan).status_code == 409


def test_ingreso_por_dni_y_clases_pasadas(cliente):
    ana = crear_usuario("ana.ingreso@gmail.com")
    beto = crear_usuario("beto.ingreso@gmail.com")
    gid, crossfit, plan = _gimnasio(cliente, ana)
    juan = _socio_al_dia(cliente, ana, gid, plan, "30111222", "Juan")
    # Una clase que empezó hace 10 minutos (o a medianoche, si recién es el día)
    ahora = g.ahora()
    inicio = ahora - timedelta(minutes=10) if (ahora - timedelta(minutes=10)).date() == ahora.date() else ahora.replace(hour=0, minute=0)
    clase = cliente.post(f"/comercios/{gid}/clases", json={"disciplinaId": crossfit["id"], "diaSemana": ahora.weekday(),
                                                           "horaInicio": inicio.strftime("%H:%M"), "duracionMinutos": 60,
                                                           "cupoMaximo": 10}, headers=ana).json()["clase"]
    reserva = cliente.post(f"/comercios/{gid}/reservas", json={"claseId": clase["id"], "socioId": juan["id"],
                                                               "fecha": str(ahora.date())}, headers=ana).json()["reserva"]

    assert cliente.post(f"/comercios/{gid}/ingresos", json={"socioId": juan["id"]}, headers=beto).status_code == 404
    r = cliente.post(f"/comercios/{gid}/ingresos", json={"socioId": juan["id"], "registradoPor": "Recepción"}, headers=ana).json()
    assert r["repetido"] is False and r["reserva"]["id"] == reserva["id"] and r["reserva"]["estado"] == "vino"
    assert r["asistencia"]["motivo"] == f"Crossfit {inicio.strftime('%H:%M')}" and r["asistencia"]["reservaId"] == reserva["id"]
    # Si pasa de nuevo dentro de la hora, no se anota otra entrada
    assert cliente.post(f"/comercios/{gid}/ingresos", json={"socioId": juan["id"]}, headers=ana).json()["repetido"] is True
    # Un rechazo se anota siempre, con el motivo
    r = cliente.post(f"/comercios/{gid}/ingresos", json={"socioId": juan["id"], "resultado": "rechazado", "motivo": "Debe"}, headers=ana).json()
    assert r["asistencia"]["resultado"] == "rechazado" and r["asistencia"]["motivo"] == "Debe"

    # Asistencia a mano
    assert cliente.post(f"/reservas/{reserva['id']}/asistencia", json={"vino": False}, headers=beto).status_code == 404
    assert cliente.post(f"/reservas/{reserva['id']}/asistencia", json={"vino": False}, headers=ana).json()["estado"] == "falto"

    # Las clases de ayer que quedaron abiertas: el reservado pasa a "faltó" y la espera a "cancelado"
    ayer = ahora.date() - timedelta(days=1)
    _sql(f"""insert into public.reservas (comercio_id, clase_id, socio_id, fecha, estado, hecha_por)
             values ({gid}, {clase['id']}, {juan['id']}, '{ayer}', 'reservado', 'x')""")
    otro = _socio_al_dia(cliente, ana, gid, plan, "40111222", "María")
    _sql(f"""insert into public.reservas (comercio_id, clase_id, socio_id, fecha, estado, hecha_por)
             values ({gid}, {clase['id']}, {otro['id']}, '{ayer}', 'espera', 'x')""")
    assert cliente.post(f"/comercios/{gid}/reservas/cerrar-pasadas", headers=beto).status_code == 404
    r = cliente.post(f"/comercios/{gid}/reservas/cerrar-pasadas", headers=ana).json()
    assert sorted(x["estado"] for x in r["reservas"]) == ["cancelado", "falto"]
    assert cliente.post(f"/comercios/{gid}/reservas/cerrar-pasadas", headers=ana).json()["reservas"] == []


def test_cargar_ejemplo(cliente):
    ana = crear_usuario("ana.ejemplo@gmail.com")
    beto = crear_usuario("beto.ejemplo@gmail.com")
    gid, crossfit, _ = _gimnasio(cliente, ana)
    ejemplo = {
        "disciplinas": [{"id": -100, "nombre": "Spinning"}],
        "planes": [{"nombre": "Spinning libre", "precio": 20000, "duracionMeses": 1, "actividades": [-100, crossfit["id"]]}],
        "clases": [{"disciplinaId": -100, "diaSemana": 0, "horaInicio": "18:00", "duracionMinutos": 45, "profesor": "Sofía", "cupoMaximo": 8},
                   {"disciplinaId": crossfit["id"], "diaSemana": 2, "horaInicio": "19:00", "duracionMinutos": 60, "profesor": "Laura", "cupoMaximo": 12}],
    }
    assert cliente.post(f"/comercios/{gid}/gimnasio/ejemplo", json=ejemplo, headers=beto).status_code == 404
    r = cliente.post(f"/comercios/{gid}/gimnasio/ejemplo", json=ejemplo, headers=ana)
    assert r.status_code == 201
    r = r.json()
    spinning = r["disciplinas"][0]["id"]
    assert spinning > 0 and r["planes"][0]["actividades"] == sorted([spinning, crossfit["id"]])
    assert [c["disciplinaId"] for c in r["clases"]] == [spinning, crossfit["id"]]
    assert r["reglas"]["diasAviso"] == 7
    # Una actividad de otro dueño no se puede colar en el ejemplo
    _, crossfit_beto, _ = _gimnasio(cliente, beto)
    malo = {"clases": [{**ejemplo["clases"][1], "disciplinaId": crossfit_beto["id"]}]}
    assert cliente.post(f"/comercios/{gid}/gimnasio/ejemplo", json=malo, headers=ana).status_code == 422
