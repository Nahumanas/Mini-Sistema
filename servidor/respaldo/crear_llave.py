"""Crea tu llave de respaldo (una sola vez). Son dos partes:

- la PÚBLICA (age1...): solo sirve para CERRAR paquetes. Va en GitHub (Settings → Secrets and variables →
  Actions → Variables → RESPALDO_LLAVE_PUBLICA). Que alguien la vea no es un problema.
- la PRIVADA (AGE-SECRET-KEY-1...): es la única que ABRE los respaldos. Se guarda en el archivo que elijas,
  FUERA de la carpeta del proyecto, y en papel junto a la pimienta. Nunca va a GitHub ni a Render.
  Si la perdés, los respaldos ya hechos no se abren más.

Uso (desde la carpeta servidor/):  python -m respaldo.crear_llave D:\\...\\respaldos\\llave-respaldo.txt
"""

import sys
from datetime import date
from pathlib import Path


def main(argv: list[str]) -> int:
    import pyrage

    if len(argv) != 1:
        print(__doc__)
        return 2
    destino = Path(argv[0])
    if destino.exists():
        print(f"ERROR: {destino} ya existe. No se pisa una llave (los respaldos viejos dependen de ella).", file=sys.stderr)
        return 1
    if (Path(__file__).resolve().parents[2] / ".git").exists() and Path(__file__).resolve().parents[2] in destino.resolve().parents:
        print("ERROR: la llave privada no se guarda dentro de la carpeta del proyecto (podría terminar en GitHub).", file=sys.stderr)
        return 1
    identidad = pyrage.x25519.Identity.generate()
    publica = str(identidad.to_public())
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        f"# Llave de respaldo de Mantenete, creada el {date.today()}. PRIVADA: no la compartas.\n"
        f"# Pública (para GitHub): {publica}\n{identidad}\n",
        encoding="utf-8",
    )
    print(f"Llave privada guardada en {destino}. Imprimila o copiala a mano y guardala con la pimienta.")
    print(f"Llave pública (pegala en GitHub como RESPALDO_LLAVE_PUBLICA):\n\n    {publica}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
