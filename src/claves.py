"""Emision del JWT.

El hash de contrasenas vive en password.py, que no depende de PyJWT ni de
JWT_SECRET: asi el seed puede hashear sin levantar el entorno de la Lambda.
"""
import os
from datetime import datetime, timedelta, timezone

import jwt

HORAS_VALIDEZ = 12
SECRETO = os.environ["JWT_SECRET"]


def emitir_token(usuario_id, tenant_id, rol, email):
    """El tenant_id va DENTRO del token: es lo que hace el aislamiento.

    El authorizer compartido lo extrae y lo entrega a los 6 microservicios por
    el requestContext. Ningun microservicio llama a ms-identidad por HTTP.
    """
    ahora = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": usuario_id,
            "tenant_id": tenant_id,
            "rol": rol,
            "email": email,
            "iat": ahora,
            "exp": ahora + timedelta(hours=HORAS_VALIDEZ),
        },
        SECRETO,
        algorithm="HS256",
    )
