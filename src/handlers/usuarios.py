"""CRUD de usuarios dentro del tenant del token.

Todas las operaciones estan encerradas en la particion del tenant: ni siquiera
un admin puede tocar usuarios de otra organizacion, porque el tenant_id sale
del token y no de la request.
"""
import uuid

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from src import db, roles
from src.claves import hashear
from src.respuesta import cuerpo_de, error, ok, tenant_de


def crear(event, context):
    """POST /usuarios — solo admin."""
    negado = roles.exige(event, roles.ADMIN)
    if negado:
        return negado

    tenant_id = tenant_de(event)
    cuerpo = cuerpo_de(event)
    email = (cuerpo.get("email") or "").strip().lower()
    nombre = (cuerpo.get("nombre") or "").strip()
    password = cuerpo.get("password") or ""
    rol = cuerpo.get("rol") or roles.MIEMBRO

    if not (email and nombre and password):
        return error("DATOS_INCOMPLETOS", "Se requiere email, nombre y password")
    if "@" not in email:
        return error("EMAIL_INVALIDO", f"'{email}' no parece un correo")
    if len(password) < 8:
        return error("PASSWORD_DEBIL", "La contrasena debe tener al menos 8 caracteres")
    if rol not in roles.TODOS:
        return error("ROL_INVALIDO", f"Roles validos: {', '.join(roles.TODOS)}")

    item = {
        "pk": db.pk_tenant(tenant_id),
        "sk": db.sk_usuario(email),
        "usuario_id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "email": email,
        "nombre": nombre,
        "rol": rol,
        "activo": True,
        "password_hash": hashear(password),
    }

    try:
        db.tabla().put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(sk)",
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return error("EMAIL_DUPLICADO", f"Ya existe un usuario con {email}", 409)
        raise

    item.pop("password_hash")
    item.pop("pk")
    item.pop("sk")
    return ok(item, estado=201)


def listar(event, context):
    """GET /usuarios?rol=pm&cursor=...&limite=50 — admin y pmo."""
    negado = roles.exige(event, roles.ADMIN, roles.PMO)
    if negado:
        return negado

    tenant_id = tenant_de(event)
    q = event.get("queryStringParameters") or {}
    limite = min(int(q.get("limite", 50)), 200)

    args = {
        # begins_with sobre el sk deja fuera el item de metadata del tenant
        "KeyConditionExpression": Key("pk").eq(db.pk_tenant(tenant_id))
        & Key("sk").begins_with("USUARIO#"),
        "ProjectionExpression": "usuario_id, email, nombre, #r, activo",
        "ExpressionAttributeNames": {"#r": "rol"},
        "Limit": limite,
    }
    if q.get("rol"):
        # Se arma a mano en vez de con Attr() para no chocar con el
        # ExpressionAttributeNames que ya declaramos arriba.
        args["FilterExpression"] = "#r = :rol"
        args["ExpressionAttributeValues"] = {":rol": q["rol"]}
    if q.get("cursor"):
        args["ExclusiveStartKey"] = {
            "pk": db.pk_tenant(tenant_id),
            "sk": db.sk_usuario(q["cursor"]),
        }

    r = db.tabla().query(**args)
    meta = {"total": r["Count"]}
    if r.get("LastEvaluatedKey"):
        meta["cursor"] = r["LastEvaluatedKey"]["sk"].removeprefix("USUARIO#")
    return ok(r.get("Items", []), meta=meta)


def obtener(event, context):
    """GET /usuarios/{email}"""
    tenant_id = tenant_de(event)
    email = (event["pathParameters"]["email"] or "").strip().lower()

    item = db.tabla().get_item(
        Key={"pk": db.pk_tenant(tenant_id), "sk": db.sk_usuario(email)}
    ).get("Item")

    if not item:
        return error("NO_ENCONTRADO", f"No existe el usuario {email}", 404)

    for campo in ("password_hash", "pk", "sk"):
        item.pop(campo, None)
    return ok(item)


def actualizar(event, context):
    """PUT /usuarios/{email} — cambia nombre, rol o activo. Solo admin."""
    negado = roles.exige(event, roles.ADMIN)
    if negado:
        return negado

    tenant_id = tenant_de(event)
    email = (event["pathParameters"]["email"] or "").strip().lower()
    cuerpo = cuerpo_de(event)

    cambios, valores, nombres = [], {}, {}
    if "nombre" in cuerpo:
        cambios.append("nombre = :n")
        valores[":n"] = cuerpo["nombre"].strip()
    if "rol" in cuerpo:
        if cuerpo["rol"] not in roles.TODOS:
            return error("ROL_INVALIDO", f"Roles validos: {', '.join(roles.TODOS)}")
        cambios.append("#r = :r")
        valores[":r"] = cuerpo["rol"]
        nombres["#r"] = "rol"
    if "activo" in cuerpo:
        cambios.append("activo = :a")
        valores[":a"] = bool(cuerpo["activo"])

    if not cambios:
        return error("SIN_CAMBIOS", "Envia al menos nombre, rol o activo")

    args = {
        "Key": {"pk": db.pk_tenant(tenant_id), "sk": db.sk_usuario(email)},
        "UpdateExpression": "SET " + ", ".join(cambios),
        "ExpressionAttributeValues": valores,
        "ConditionExpression": "attribute_exists(sk)",
        "ReturnValues": "ALL_NEW",
    }
    if nombres:
        args["ExpressionAttributeNames"] = nombres

    try:
        r = db.tabla().update_item(**args)
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return error("NO_ENCONTRADO", f"No existe el usuario {email}", 404)
        raise

    item = r["Attributes"]
    for campo in ("password_hash", "pk", "sk"):
        item.pop(campo, None)
    return ok(item)


def desactivar(event, context):
    """DELETE /usuarios/{email} — baja logica, no borra. Solo admin.

    No se borra el registro porque otros microservicios guardan el usuario_id
    como responsable de proyectos y tareas; si desapareciera, esas referencias
    quedarian huerfanas.
    """
    negado = roles.exige(event, roles.ADMIN)
    if negado:
        return negado

    tenant_id = tenant_de(event)
    email = (event["pathParameters"]["email"] or "").strip().lower()

    try:
        db.tabla().update_item(
            Key={"pk": db.pk_tenant(tenant_id), "sk": db.sk_usuario(email)},
            UpdateExpression="SET activo = :f",
            ExpressionAttributeValues={":f": False},
            ConditionExpression="attribute_exists(sk)",
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return error("NO_ENCONTRADO", f"No existe el usuario {email}", 404)
        raise

    return ok({"email": email, "activo": False})
