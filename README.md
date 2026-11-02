# ms-identidad

Tenants, usuarios, roles y emisión de JWT. **Es el que emite los tokens que
usan los otros 5 microservicios.**

- **Responsable:** @Osomar1705
- **Base de datos:** DynamoDB · partition key prefijada por tenant
- **Runtime:** Python 3.12 · Serverless Framework · us-east-1

## Endpoints

### Públicos

| Método | Ruta | Qué hace |
|---|---|---|
| POST | `/login` | recibe `{tenant_id, email, password}` y devuelve el JWT |
| GET | `/tenants` | lista las organizaciones (alimenta el selector del login) |

### Protegidos por el authorizer compartido

| Método | Ruta | Rol | Qué hace |
|---|---|---|---|
| GET | `/health` | cualquiera | verifica el servicio y devuelve el tenant del token |
| GET | `/perfil` | cualquiera | datos del usuario dueño del token |
| POST | `/usuarios` | admin | crea un usuario en el tenant del token |
| GET | `/usuarios` | admin, pmo | lista paginada, filtrable por `?rol=` |
| GET | `/usuarios/{email}` | cualquiera | un usuario del tenant |
| PUT | `/usuarios/{email}` | admin | cambia nombre, rol o activo |
| DELETE | `/usuarios/{email}` | admin | baja lógica (`activo: false`) |

Son **7 endpoints protegidos**, por encima del mínimo de 5 que pide el enunciado.

## El token

```json
{
  "sub": "<usuario_id>",
  "tenant_id": "t-acme",
  "rol": "admin",
  "email": "admin@acme.com.pe",
  "iat": 1762000000,
  "exp": 1762043200
}
```

Firmado con HS256 y el `JWT_SECRET` que vive en SSM. Vale 12 horas.

**El `tenant_id` va dentro del token: eso es lo que hace el aislamiento.** El
authorizer compartido lo extrae y lo entrega a los 6 microservicios por el
`requestContext`. Ninguno llama a `ms-identidad` por HTTP.

## Desplegar

`infra-compartida` tiene que estar desplegado antes (de ahí salen el
`JWT_SECRET`, el topic SNS y el authorizer).

```bash
pip install -r requirements.txt
npm install
sls deploy
```

## Cargar datos

```bash
export TABLA=ms-identidad-identidad-dev
python seed/generar.py            # 30,006 registros en 3 tenants
python seed/generar.py --contar   # verificar
```

Usuarios de la demo, todos con la clave `Demo1234`:

| Tenant | Admin |
|---|---|
| `t-acme` | `admin@acme.com.pe` |
| `t-globex` | `admin@globex.com` |
| `t-initech` | `admin@initech.io` |

## Probar

```bash
./verificar.sh https://xxxx.execute-api.us-east-1.amazonaws.com/dev
```

El script hace login en dos tenants, prueba los endpoints, y **verifica que el
token de Globex no pueda leer datos de Acme**. Es lo que se corre en vivo en la
exposición.

## Documentación

- [Modelo de datos](docs/modelo.md) — claves, items, roles, volumen y seguridad
- [Arquitectura general](https://github.com/ppm-cloud-utec/infra-compartida/blob/main/docs/arquitectura.md)
