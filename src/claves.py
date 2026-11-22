"""Emision del JWT."""
import os
from datetime import datetime, timedelta, timezone

import jwt

from src import secretos

HORAS_VALIDEZ = 12
def _secreto():
    return secretos.de_entorno("JWT_SECRET_NOMBRE")


def emitir_token(usuario_id, tenant_id, rol, email):
    """El tenant_id va DENTRO del token: es lo que hace el aislamiento."""
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
        _secreto(),
        algorithm="HS256",
    )
