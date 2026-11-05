"""Hash y verificacion de contrasenas. Solo libreria estandar.

Vive aparte de claves.py a proposito: hashear una contrasena no necesita ni
PyJWT ni la variable JWT_SECRET. Si estuviera junto a la emision de tokens,
el seed (que solo hashea) no podria correr sin tener configurado el entorno
completo de la Lambda.

PBKDF2-HMAC-SHA256 con 200,000 iteraciones y salt de 16 bytes por usuario, que
es lo que recomienda OWASP. Se eligio sobre bcrypt y argon2 porque viene en la
libreria estandar y no obliga a compilar extensiones en C para el paquete de
la Lambda.
"""
import hmac
import base64
import hashlib
import secrets

ITERACIONES = 200_000


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
