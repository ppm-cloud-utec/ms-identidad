#!/usr/bin/env python3
"""Carga 30,003 registros en ms-identidad, repartidos en 3 tenants.

    python seed/generar.py                  # los 3 tenants
    python seed/generar.py --tenant t-acme   # solo uno
    python seed/generar.py --contar          # solo contar lo que ya hay

Reparto: 3 items de tenant + 10,001 usuarios por tenant = 30,003 registros.

Los tres tenants tienen PERFILES DISTINTOS a proposito (proporcion de roles
distinta segun el rubro). Si los datos salen identicos, el multi-tenancy se ve
falso en la demo.

Rendimiento: las 30,000 contrasenas comparten un unico hash precalculado.
Hashear cada una con los 200,000 ciclos de PBKDF2 tomaria unos 25 minutos; con
uno solo toma milisegundos y el login sigue siendo real. Los usuarios de la
demo usan la misma clave, lo cual es correcto para datos ficticios y esta
documentado en el informe.
"""
import os
import sys
import uuid
import random
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import boto3
from boto3.dynamodb.conditions import Key

TABLA = os.environ.get("TABLA", "ms-identidad-identidad-dev")
REGION = os.environ.get("AWS_REGION", "us-east-1")
PASSWORD_DEMO = "Demo1234"

TENANTS = {
    "t-acme": dict(
        nombre="Acme Ingenieria", rubro="construccion", usuarios=10_000,
        # Mucho PM y miembro de obra, poca gente de portafolio
        mezcla={"admin": 0.001, "pmo": 0.004, "pm": 0.095, "miembro": 0.900},
        dominio="acme.com.pe",
    ),
    "t-globex": dict(
        nombre="Globex Consulting", rubro="consultoria TI", usuarios=10_000,
        # Consultoria: muchos PM porque cada cliente es un proyecto
        mezcla={"admin": 0.001, "pmo": 0.009, "pm": 0.250, "miembro": 0.740},
        dominio="globex.com",
    ),
    "t-initech": dict(
        nombre="Initech Software", rubro="software", usuarios=10_000,
        # Producto: pocos PM, mucho equipo de desarrollo
        mezcla={"admin": 0.001, "pmo": 0.003, "pm": 0.046, "miembro": 0.950},
        dominio="initech.io",
    ),
}

NOMBRES = [
    "Ana", "Luis", "Carmen", "Jose", "Rosa", "Carlos", "Maria", "Jorge", "Elena",
    "Miguel", "Lucia", "Pedro", "Sofia", "Diego", "Valeria", "Andres", "Paola",
    "Ricardo", "Gabriela", "Fernando", "Claudia", "Javier", "Patricia", "Raul",
    "Monica", "Cesar", "Silvia", "Oscar", "Natalia", "Hugo", "Beatriz", "Alonso",
]
APELLIDOS = [
    "Quispe", "Flores", "Rojas", "Vargas", "Castillo", "Ramos", "Torres", "Diaz",
    "Mendoza", "Chavez", "Huaman", "Salazar", "Paredes", "Guerrero", "Ibanez",
    "Zarate", "Palomino", "Cordova", "Arce", "Bustamante", "Ñahui", "Velasquez",
]


def hash_demo():
    """Un solo hash para los 30,000 usuarios ficticios."""
    from src.claves import hashear
    return hashear(PASSWORD_DEMO)


def roles_del_tenant(cfg):
    """Expande la mezcla de roles a una lista de la longitud exacta."""
    total = cfg["usuarios"]
    lista = []
    for rol, proporcion in cfg["mezcla"].items():
        lista += [rol] * max(1, round(total * proporcion))
    lista = lista[:total]
    while len(lista) < total:
        lista.append("miembro")
    random.shuffle(lista)
    return lista


def generar(tenant_id, cfg, tabla, hash_password):
    pk = f"TENANT#{tenant_id}"
    escritos = 0

    # 1. El item del tenant, en la particion del registro global
    tabla.put_item(Item={
        "pk": "TENANTS",
        "sk": f"TENANT#{tenant_id}",
        "tenant_id": tenant_id,
        "nombre": cfg["nombre"],
        "rubro": cfg["rubro"],
        "activo": True,
    })
    escritos += 1

    # 2. El admin con email predecible, para poder entrar en la demo
    corto = tenant_id.removeprefix("t-")
    with tabla.batch_writer(overwrite_by_pkeys=["pk", "sk"]) as lote:
        lote.put_item(Item={
            "pk": pk, "sk": f"USUARIO#admin@{cfg['dominio']}",
            "usuario_id": str(uuid.uuid4()), "tenant_id": tenant_id,
            "email": f"admin@{cfg['dominio']}", "nombre": f"Admin {cfg['nombre']}",
            "rol": "admin", "activo": True, "password_hash": hash_password,
        })
        escritos += 1

        # 3. El resto de la poblacion
        for i, rol in enumerate(roles_del_tenant(cfg)):
            nombre = f"{random.choice(NOMBRES)} {random.choice(APELLIDOS)}"
            email = f"{corto}{i:05d}@{cfg['dominio']}"
            lote.put_item(Item={
                "pk": pk, "sk": f"USUARIO#{email}",
                "usuario_id": str(uuid.uuid4()), "tenant_id": tenant_id,
                "email": email, "nombre": nombre, "rol": rol,
                "activo": random.random() > 0.02,  # 2% de bajas, como en la vida real
                "password_hash": hash_password,
            })
            escritos += 1
            if escritos % 2500 == 0:
                print(f"    {escritos:>6} registros...", flush=True)

    return escritos


def contar(tabla):
    print(f"Tabla: {TABLA}\n")
    total = 0
    for tenant_id, cfg in TENANTS.items():
        n, clave = 0, None
        while True:
            args = {
                "KeyConditionExpression": Key("pk").eq(f"TENANT#{tenant_id}"),
                "Select": "COUNT",
            }
            if clave:
                args["ExclusiveStartKey"] = clave
            r = tabla.query(**args)
            n += r["Count"]
            clave = r.get("LastEvaluatedKey")
            if not clave:
                break
        print(f"  {cfg['nombre']:<22} ({tenant_id:<10}) {n:>6} usuarios")
        total += n
    r = tabla.query(KeyConditionExpression=Key("pk").eq("TENANTS"), Select="COUNT")
    print(f"  {'registro de tenants':<22} {'':<12} {r['Count']:>6} items")
    print(f"\n  TOTAL {total + r['Count']:>6} registros")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant", choices=list(TENANTS))
    ap.add_argument("--contar", action="store_true")
    args = ap.parse_args()

    tabla = boto3.resource("dynamodb", region_name=REGION).Table(TABLA)

    if args.contar:
        return contar(tabla)

    random.seed(2026)  # reproducible: dos corridas dan los mismos datos
    objetivo = {args.tenant: TENANTS[args.tenant]} if args.tenant else TENANTS

    print(f"Tabla: {TABLA}")
    print(f"Clave de todos los usuarios ficticios: {PASSWORD_DEMO}\n")
    h = hash_demo()

    total = 0
    for tenant_id, cfg in objetivo.items():
        print(f"== {cfg['nombre']} ({tenant_id}) ==")
        n = generar(tenant_id, cfg, tabla, h)
        print(f"   {n} registros · admin@{cfg['dominio']}\n")
        total += n

    print(f"Listo: {total} registros.")
    print("Verifica con:  python seed/generar.py --contar")


if __name__ == "__main__":
    main()
