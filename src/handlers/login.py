"""POST /login — publico, es la unica puerta de entrada sin token."""
from botocore.exceptions import ClientError

from src import db
from src.claves import emitir_token, verificar
from src.respuesta import cuerpo_de, error, ok


def manejar(event, context):
    cuerpo = cuerpo_de(event)
    tenant_id = (cuerpo.get("tenant_id") or "").strip()
    email = (cuerpo.get("email") or "").strip().lower()
    password = cuerpo.get("password") or ""

    if not (tenant_id and email and password):
        return error("DATOS_INCOMPLETOS", "Se requiere tenant_id, email y password")

    try:
        item = db.tabla().get_item(
            Key={"pk": db.pk_tenant(tenant_id), "sk": db.sk_usuario(email)}
        ).get("Item")
    except ClientError:
        return error("ERROR_BD", "No se pudo consultar el usuario", 500)

    # Mismo mensaje si el usuario no existe o si la clave esta mal: no le
    # decimos a un atacante cuales correos estan registrados.
    if not item or not verificar(password, item["password_hash"]):
        return error("CREDENCIALES_INVALIDAS", "Email o contrasena incorrectos", 401)

    if not item.get("activo", True):
        return error("USUARIO_INACTIVO", "La cuenta esta desactivada", 403)

    token = emitir_token(item["usuario_id"], tenant_id, item["rol"], email)
    return ok({
        "token": token,
        "usuario": {
            "usuario_id": item["usuario_id"],
            "email": email,
            "nombre": item["nombre"],
            "rol": item["rol"],
            "tenant_id": tenant_id,
        },
    })
