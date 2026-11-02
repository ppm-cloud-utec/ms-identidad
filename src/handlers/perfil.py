"""GET /perfil — quien soy, segun el token."""
from src import db
from src.respuesta import error, ok, tenant_de
from src.claves import SECRETO  # noqa: F401  (valida que la env exista al cargar)


def manejar(event, context):
    autorizador = event["requestContext"]["authorizer"]
    tenant_id = tenant_de(event)
    email = autorizador.get("email")

    if not email:
        return error("TOKEN_INCOMPLETO", "El token no trae email", 401)

    item = db.tabla().get_item(
        Key={"pk": db.pk_tenant(tenant_id), "sk": db.sk_usuario(email)}
    ).get("Item")

    if not item:
        return error("NO_ENCONTRADO", "El usuario del token ya no existe", 404)

    item.pop("password_hash", None)
    item.pop("pk", None)
    item.pop("sk", None)
    return ok(item)
