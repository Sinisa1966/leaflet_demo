#!/usr/bin/env python3
"""
Pomera sloj opština (katop_lat) ulevo tako da se poklopi sa granicama parcela DKP.
Referenca: parcela 5218 u DKP-Vršac – desna (istočna) ivica parcele treba da se
poklopi sa granicom opštine Vršac; na osnovu toga računamo pomeraj i primenjujemo
ga na ceo sloj opština.

Korišćenje:
  Iz korena projekta, sa učitanim .env (ndvi_auto/.env):
    python scripts/align_opstine_layer.py

  Na serveru (Hetzner), ako se baza poziva preko kontejnera, pokrenuti iz kontejnera
  koji ima pristup bazi (npr. host=db, port=5432) ili sa hosta na localhost:5434.

  Opciono env: POSTGRES_HOST, POSTGRES_PORT, POSTGRES_USER, POSTGRES_PASS, POSTGRES_DB
  (podrazumevano: localhost, 5434, admin, iz .env, moj_gis).

  Na serveru (Hetzner): POSTGRES_HOST=db POSTGRES_PORT=5432 ako skriptu pokrećeš
  iz kontejnera u istoj mreži kao db.

  --dry-run: samo ispiše izračunati pomeraj, ne menja bazu.
"""

import argparse
import os
import sys
from pathlib import Path

# Učitaj ndvi_auto/.env ako postoji
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / "ndvi_auto" / ".env"
if ENV_PATH.exists():
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if val and key not in os.environ:
            os.environ[key] = val

try:
    import psycopg2
    from psycopg2 import sql
except ImportError:
    print("Instaliraj psycopg2: pip install psycopg2-binary", file=sys.stderr)
    sys.exit(1)

# Konfiguracija iz env
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "127.0.0.1")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5434")
POSTGRES_USER = os.getenv("POSTGRES_USER", "admin")
POSTGRES_PASS = os.getenv("POSTGRES_PASS", "")
POSTGRES_DB = os.getenv("POSTGRES_DB", "moj_gis")

# Referentna parcela i sloj opština
PARCEL_ID = "5218"
OPSTINA_NAME = "Vršac"


def get_geom_column(conn, table: str) -> str:
    """Vraća ime geometrijske kolone za tabelu (geom ili wkb_geometry)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT f_geometry_column
            FROM geometry_columns
            WHERE f_table_schema = 'public' AND f_table_name = %s
            LIMIT 1
            """,
            (table,),
        )
        row = cur.fetchone()
    if not row:
        raise SystemExit(f"Tabela {table} nema registrovanu geometriju u geometry_columns.")
    return row[0]


def main() -> None:
    parser = argparse.ArgumentParser(description="Poravnaj sloj opština (katop_lat) sa DKP parcelama.")
    parser.add_argument("--dry-run", action="store_true", help="Samo ispiši pomeraj, ne ažuriraj bazu.")
    args = parser.parse_args()

    if not POSTGRES_PASS:
        print("POSTGRES_PASS nije postavljen (ndvi_auto/.env ili env).", file=sys.stderr)
        sys.exit(1)

    conn = psycopg2.connect(
        host=POSTGRES_HOST,
        port=int(POSTGRES_PORT),
        user=POSTGRES_USER,
        password=POSTGRES_PASS,
        dbname=POSTGRES_DB,
    )
    conn.autocommit = False

    geom_katop = get_geom_column(conn, "katop_lat")
    geom_dkp = get_geom_column(conn, "vrsac_dkp_pg")
    print(f"  katop_lat geom kolona: {geom_katop}")
    print(f"  vrsac_dkp_pg geom kolona: {geom_dkp}")

    with conn.cursor() as cur:
        # Pomeraj: istočna ivica parcele (ST_XMax) vs najbliža tačka na granici opštine
        # u tom području. delta_lon = parcel_east_x - opstina_boundary_x (ulevo ako negativno)
        # Koristimo podupite da ne prosleđujemo geometriju iz Pythona.
        # Opština Vršac može biti zapisana kao VRšAC / VR\u008AAC (različiti encoding)
        like_vrsac = f"%{OPSTINA_NAME}%"
        like_vrsac_alt = "VR%AC"  # fallback bez diakritika
        q = f"""
            WITH parcel AS (
                SELECT p.{geom_dkp} AS g
                FROM vrsac_dkp_pg p
                WHERE p.brparcele::text = %s
                LIMIT 1
            ),
            opstina AS (
                SELECT k.{geom_katop} AS g
                FROM katop_lat k
                WHERE k.imeolatv ILIKE %s OR k.imeolatv ILIKE %s
                LIMIT 1
            ),
            parcel_east AS (
                SELECT ST_XMax(p.g) AS x_max, ST_Y(ST_Centroid(p.g)) AS y_cent
                FROM parcel p
            ),
            opstina_boundary AS (
                SELECT ST_Boundary(o.g) AS boundary FROM opstina o
            ),
            ref_point AS (
                SELECT ST_SetSRID(ST_MakePoint(pe.x_max, pe.y_cent), 4326) AS pt
                FROM parcel_east pe
            ),
            closest_on_boundary AS (
                SELECT ST_ClosestPoint(ob.boundary, rp.pt) AS cp
                FROM opstina_boundary ob, ref_point rp
            )
            SELECT
                (SELECT x_max FROM parcel_east) AS parcel_x,
                ST_X(cp) AS opstina_x
            FROM closest_on_boundary
            """
        cur.execute(q, (PARCEL_ID, like_vrsac, like_vrsac_alt))
        row = cur.fetchone()
        if not row or row[0] is None or row[1] is None:
            print("Nije moguce izracunati pomeraj (podaci ili geometrija nedostaju).", file=sys.stderr)
            conn.rollback()
            sys.exit(1)
        parcel_x, opstina_x = float(row[0]), float(row[1])
        delta_lon = parcel_x - opstina_x

        print(f"  Parcela 5218 (istocna lon): {parcel_x:.6f}")
        print(f"  Granica opstine Vrsac (lon u tom segmentu): {opstina_x:.6f}")
        print(f"  Izracunat pomeraj (delta_lon): {delta_lon:.6f} (ulevo ako je negativno)")

        if abs(delta_lon) < 1e-7:
            print("Pomeraj je zanemarljiv; nema izmene.")
            conn.rollback()
            return

        if args.dry_run:
            print("  [dry-run] Izlazim bez izmene baze.")
            conn.rollback()
            return

        # Primeni pomeranje na SVE zapise u katop_lat
        cur.execute(
            sql.SQL("UPDATE katop_lat SET {} = ST_Translate({}, %s, 0)").format(
                sql.Identifier(geom_katop), sql.Identifier(geom_katop)
            ),
            (delta_lon,),
        )
        updated = cur.rowcount
    conn.commit()
    print(f"  Azurirano zapisa u katop_lat: {updated}")
    print("Gotovo. Osvezi WFS sloj Opstine (KatOp_Lat) u mapi da vidis promenu.")


if __name__ == "__main__":
    main()
