"""Acceso a DynamoDB."""
import os

import boto3

_dynamo = boto3.resource("dynamodb")

REGISTRO_TENANTS = "TENANTS"


def tabla():
    return _dynamo.Table(os.environ["TABLA"])


def pk_tenant(tenant_id):
    """La particion de los usuarios de un tenant."""
    return f"TENANT#{tenant_id}"


def sk_usuario(email):
    return f"USUARIO#{email.strip().lower()}"


def sk_tenant(tenant_id):
    return f"TENANT#{tenant_id}"
