"""Alta y baja de un tenant en ms-identidad."""
import os
import secrets
import uuid

import boto3
from botocore.exceptions import ClientError

from src import db, roles
from src.password import hashear

PROTEGIDOS = frozenset({"t-acme", "t-globex", "t-initech"})


def _guardar_clave(tenant_id, clave):
    """Deja la contrasena inicial cifrada en SSM y devuelve donde quedo."""
    nombre = f"/ppm/tenants/{tenant_id}/admin-password"
    boto3.client("ssm").put_parameter(
        Name=nombre, Value=clave, Type="SecureString", Overwrite=True,
        Description=f"Contrasena inicial del admin de {tenant_id}",
    )
    return nombre


def aprovisionar(event, context):
    """Registra el tenant y crea su administrador. Idempotente."""
    tenant_id = event["tenant_id"]
    nombre = event["nombre"]
    rubro = event.get("rubro", "")
    email = (event.get("admin_email") or f"admin@{tenant_id[2:]}.com").strip().lower()

    tabla = db.tabla()

    # 1. El registro que ve el selector del login.
    tabla.put_item(Item={
        "pk": db.REGISTRO_TENANTS,
        "sk": db.sk_tenant(tenant_id),
        "tenant_id": tenant_id,
        "nombre": nombre,
        "rubro": rubro,
    })

    clave = secrets.token_urlsafe(12)
    creado = True
    try:
        tabla.put_item(
            Item={
                "pk": db.pk_tenant(tenant_id),
                "sk": db.sk_usuario(email),
                "usuario_id": str(uuid.uuid4()),
                "tenant_id": tenant_id,
                "email": email,
                "nombre": f"Admin {nombre}",
                "rol": roles.ADMIN,
                "activo": True,
                "password_hash": hashear(clave),
            },
            ConditionExpression="attribute_not_exists(sk)",
        )
    except ClientError as e:
        if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
        creado = False

    parametro = _guardar_clave(tenant_id, clave) if creado else None

    return {"servicio": "ms-identidad", "tenant_id": tenant_id,
            "admin_email": email, "admin_creado": creado,
            "clave_en": parametro, "ok": True}


def compensar(event, context):
    """Deshace el alta: borra el admin y el registro del tenant."""
    tenant_id = event["tenant_id"]
    if tenant_id in PROTEGIDOS:
        raise PermissionError(
            f"{tenant_id} es un tenant original: no se compensa jamas")

    email = (event.get("admin_email") or f"admin@{tenant_id[2:]}.com").strip().lower()
    tabla = db.tabla()
    tabla.delete_item(Key={"pk": db.pk_tenant(tenant_id),
                           "sk": db.sk_usuario(email)})
    tabla.delete_item(Key={"pk": db.REGISTRO_TENANTS,
                           "sk": db.sk_tenant(tenant_id)})
    try:
        boto3.client("ssm").delete_parameter(
            Name=f"/ppm/tenants/{tenant_id}/admin-password")
    except ClientError:
        pass  # no existia: nada que limpiar

    return {"servicio": "ms-identidad", "tenant_id": tenant_id,
            "revertido": True}
