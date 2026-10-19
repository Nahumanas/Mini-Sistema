"""Muestra un resumen de la base de datos usando consultas SQL.

Sirve para comprobar que los datos tienen sentido y como ejemplo de consultas
que después vamos a usar en las pantallas y en los reportes.

Uso:
    python ver_resumen.py            -> todos los comercios
    python ver_resumen.py "Carlos Pérez"   -> solo los comercios de ese dueño
"""

import sys

import pandas as pd

import base_datos

pd.set_option("display.width", 140)
pd.set_option("display.float_format", lambda x: f"{x:,.0f}")

# Ventas, costo de lo vendido, gastos y ganancia de cada comercio
SQL_RESUMEN = """
WITH ventas_comercio AS (
    SELECT v.comercio_id,
           COUNT(DISTINCT v.id)                       AS cantidad_ventas,
           SUM(d.subtotal)                            AS facturacion,
           SUM(d.cantidad * d.costo_unitario)         AS costo_mercaderia
    FROM ventas v
    JOIN ventas_detalle d ON d.venta_id = v.id
    WHERE v.anulada IS NULL  -- las ventas anuladas con un ajuste de caja no cuentan
    GROUP BY v.comercio_id
),
gastos_comercio AS (
    SELECT comercio_id, SUM(monto) AS gastos
    FROM gastos
    GROUP BY comercio_id
)
SELECT du.nombre  AS dueno,
       c.nombre   AS comercio,
       c.rubro,
       vc.cantidad_ventas,
       vc.facturacion,
       vc.costo_mercaderia,
       g.gastos,
       vc.facturacion - vc.costo_mercaderia - g.gastos AS ganancia_neta
FROM comercios c
JOIN duenos du           ON du.id = c.dueno_id
JOIN ventas_comercio vc  ON vc.comercio_id = c.id
JOIN gastos_comercio g   ON g.comercio_id = c.id
WHERE (:dueno IS NULL OR du.nombre = :dueno)
ORDER BY du.nombre, c.nombre
"""

# Ganancia neta de cada mes y comercio (positiva = ganó, negativa = perdió)
SQL_POR_MES = """
WITH v AS (
    SELECT v.comercio_id, strftime('%Y-%m', v.fecha) AS mes,
           SUM(d.subtotal - d.cantidad * d.costo_unitario) AS ganancia_bruta
    FROM ventas v JOIN ventas_detalle d ON d.venta_id = v.id
    WHERE v.anulada IS NULL
    GROUP BY 1, 2
),
g AS (
    SELECT comercio_id, strftime('%Y-%m', fecha) AS mes, SUM(monto) AS gastos
    FROM gastos GROUP BY 1, 2
)
SELECT c.nombre AS comercio, v.mes, v.ganancia_bruta - COALESCE(g.gastos, 0) AS ganancia_neta
FROM v
JOIN comercios c ON c.id = v.comercio_id
JOIN duenos du   ON du.id = c.dueno_id
LEFT JOIN g ON g.comercio_id = v.comercio_id AND g.mes = v.mes
WHERE (:dueno IS NULL OR du.nombre = :dueno)
ORDER BY c.nombre, v.mes
"""

# Unidades vendidas de cada producto (para ver los más y menos vendidos)
SQL_PRODUCTOS = """
SELECT c.nombre AS comercio, p.nombre AS producto, SUM(d.cantidad) AS unidades
FROM ventas_detalle d
JOIN ventas v    ON v.id = d.venta_id AND v.anulada IS NULL
JOIN productos p ON p.id = d.producto_id
JOIN comercios c ON c.id = p.comercio_id
JOIN duenos du   ON du.id = c.dueno_id
WHERE (:dueno IS NULL OR du.nombre = :dueno)
GROUP BY c.nombre, p.nombre
"""


def main():
    dueno = sys.argv[1] if len(sys.argv) > 1 else None
    motor = base_datos.obtener_motor()
    parametros = {"dueno": dueno}

    print("\n=== RESUMEN POR COMERCIO (todo el período) ===")
    print(pd.read_sql(SQL_RESUMEN, motor, params=parametros).to_string(index=False))

    print("\n=== GANANCIA NETA POR MES ===")
    por_mes = pd.read_sql(SQL_POR_MES, motor, params=parametros)
    print(por_mes.pivot(index="mes", columns="comercio", values="ganancia_neta").to_string())

    productos = pd.read_sql(SQL_PRODUCTOS, motor, params=parametros)
    for comercio, grupo in productos.groupby("comercio"):
        grupo = grupo.sort_values("unidades", ascending=False)
        print(f"\n=== {comercio} ===")
        print("  Más vendidos:  ", ", ".join(f"{r.producto} ({r.unidades})" for r in grupo.head(3).itertuples()))
        print("  Menos vendidos:", ", ".join(f"{r.producto} ({r.unidades})" for r in grupo.tail(3).itertuples()))

    motor.dispose()


if __name__ == "__main__":
    main()
