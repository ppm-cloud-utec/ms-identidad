"""GET /tenants — publico. Alimenta el selector de organizacion del login.

Devuelve solo id y nombre, nunca cuantos usuarios tiene ni datos internos.

En un SaaS real el tenant se deduce del subdominio (acme.portafolio.com) y este
endpoint no existiria. Para la demo el frontend necesita un selector visible,
asi que se expone la lista minima a proposito.
"""
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
