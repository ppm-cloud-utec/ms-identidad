"""GET /tenants — publico."""
from boto3.dynamodb.conditions import Key

from src import db
from src.respuesta import ok


def manejar(event, context):
    r = db.tabla().query(
        KeyConditionExpression=Key("pk").eq(db.REGISTRO_TENANTS),
        ProjectionExpression="tenant_id, nombre, rubro",
    )
    tenants = sorted(r.get("Items", []), key=lambda t: t["nombre"])
    return ok(tenants, meta={"total": len(tenants)})
