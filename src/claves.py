"""Hash de contrasenas y emision de JWT.

El hash usa pbkdf2_hmac de la libreria estandar: no necesita compilar nada
(bcrypt y argon2 requieren extensiones en C, que complican el empaquetado de
la Lambda). 200,000 iteraciones de SHA-256 es lo que recomienda OWASP.
"""
import os
import hmac
import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt

ITERACIONES = 200_000
HORAS_VALIDEZ = 12
SECRETO = os.environ["JWT_SECRET"]


def hashear(password):
    """Devuelve 'pbkdf2$<iteraciones>$<salt>$<hash>', todo en una cadena."""
    sal = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), sal, ITERACIONES)
    return "pbkdf2${}${}${}".format(
        ITERACIONES,
        base64.b64encode(sal).decode(),
        base64.b64encode(dk).decode(),
    )


def verificar(password, guardado):
    """Compara en tiempo constante para no filtrar informacion por el tiempo."""
    try:
        algo, iteraciones, sal_b64, hash_b64 = guardado.split("$")
        if algo != "pbkdf2":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), base64.b64decode(sal_b64), int(iteraciones)
        )
        return hmac.compare_digest(dk, base64.b64decode(hash_b64))
    except (ValueError, TypeError):
        return False


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
