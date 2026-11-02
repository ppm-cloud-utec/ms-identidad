"""Acceso a DynamoDB. Single-table design con aislamiento por particion.

Claves:
  Tenant   pk = "TENANTS"            sk = "TENANT#<tenant_id>"
  Usuario  pk = "TENANT#<tenant_id>" sk = "USUARIO#<email>"

El email es la clave de ordenamiento del usuario porque es unico dentro del
tenant: asi el login es un GetItem directo, sin indices ni scans. El usuario_id
se guarda como atributo.
"""
import os

import boto3

_dynamo = boto3.resource("dynamodb")

REGISTRO_TENANTS = "TENANTS"


def tabla():
    return _dynamo.Table(os.environ["TABLA"])


def pk_tenant(tenant_id):
    """La particion de los usuarios de un tenant.

    Todo acceso a usuarios pasa por aqui, asi una query no puede cruzar
    tenants ni por error de programacion.
    """
    return f"TENANT#{tenant_id}"


def sk_usuario(email):
    return f"USUARIO#{email.strip().lower()}"


def sk_tenant(tenant_id):
    return f"TENANT#{tenant_id}"
