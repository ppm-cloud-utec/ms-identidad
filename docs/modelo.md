# Modelo de datos — ms-identidad

**Motor:** DynamoDB · **Tabla:** `ms-identidad-identidad-dev` (single-table design)
**Facturación:** PAY_PER_REQUEST (no hay capacidad provisionada que ajustar)

## Claves

| Clave | Formato | Por qué |
|---|---|---|
| `pk` (HASH) | `TENANT#<tenant_id>` para usuarios · `TENANTS` para el registro de organizaciones | el aislamiento vive en la partición: una query jamás puede cruzar tenants |
| `sk` (RANGE) | `USUARIO#<email>` · `TENANT#<tenant_id>` | el email es único dentro del tenant, así el login es un `GetItem` directo sin índices ni scans |

**Por qué el email es la sort key y no el `usuario_id`:** el login recibe email
y contraseña. Si la clave fuera el `usuario_id`, habría que mantener un índice
secundario global por email y el login costaría una query extra. Con el email
como `sk`, entrar es una sola lectura de 1 RCU. El `usuario_id` (UUID v4) se
guarda como atributo y es lo que los otros 5 microservicios referencian.

## Los 2 tipos de item

### Tenant (organización)

```json
{
  "pk": "TENANTS",
  "sk": "TENANT#t-acme",
  "tenant_id": "t-acme",
  "nombre": "Acme Ingenieria",
  "rubro": "construccion",
  "activo": true
}
```

Viven todos en la partición `TENANTS` porque son pocos (3) y se listan juntos
para el selector de organización del login.

### Usuario

```json
{
  "pk": "TENANT#t-acme",
  "sk": "USUARIO#admin@acme.com.pe",
  "usuario_id": "8f14e45f-ceea-467a-9f1b-2c3d4e5f6a7b",
  "tenant_id": "t-acme",
  "email": "admin@acme.com.pe",
  "nombre": "Admin Acme Ingenieria",
  "rol": "admin",
  "activo": true,
  "password_hash": "pbkdf2$200000$<salt b64>$<hash b64>"
}
```

El `password_hash` **nunca** sale en una respuesta de la API: cada handler lo
quita antes de serializar.

## Índices secundarios

**Ninguno.** El diseño de claves cubre los tres accesos del servicio:

| Consulta | Operación | Costo |
|---|---|---|
| login (tenant + email) | `GetItem` | 1 lectura |
| listar usuarios del tenant | `Query` con `begins_with(sk, "USUARIO#")` | 1 query paginada |
| listar organizaciones | `Query` sobre `pk = "TENANTS"` | 1 query de 3 items |

Agregar un GSI sin necesidad duplica el costo de cada escritura, así que no se
puso ninguno.

## Roles

| Rol | Puede |
|---|---|
| `admin` | crear, editar y desactivar usuarios de su organización |
| `pmo` | listar usuarios; en los otros microservicios prioriza y aprueba presupuestos |
| `pm` | su perfil; en los otros microservicios planifica y registra gastos |
| `miembro` | su perfil; completa sus tareas |

## Volumen de datos

| Tipo de item | t-acme | t-globex | t-initech | Total |
|---|---|---|---|---|
| Tenant | 1 | 1 | 1 | **3** |
| Usuario | 10,001 | 10,001 | 10,001 | **30,003** |
| | | | | **30,006** |

Los tres tenants tienen **proporciones de rol distintas** según su rubro, a
propósito: si los datos fueran idénticos, el multi-tenancy se vería falso.

| Rol | t-acme (construcción) | t-globex (consultoría) | t-initech (software) |
|---|---|---|---|
| admin | 10 | 10 | 10 |
| pmo | 40 | 90 | 30 |
| pm | 950 | **2,500** | 460 |
| miembro | 9,000 | 7,400 | **9,500** |

Globex tiene 2,500 PM porque en consultoría cada cliente es un proyecto;
Initech concentra todo en miembros porque es un equipo de producto.

## Seguridad

- **Hash:** PBKDF2-HMAC-SHA256 con 200,000 iteraciones y salt de 16 bytes por
  usuario (lo que recomienda OWASP). Se eligió sobre bcrypt/argon2 porque viene
  en la librería estándar y no obliga a compilar extensiones en C para el
  paquete de la Lambda.
- **Comparación en tiempo constante** (`hmac.compare_digest`) para no filtrar
  información por el tiempo de respuesta.
- **Mismo mensaje de error** si el usuario no existe o si la contraseña está
  mal: no se le confirma a un atacante qué correos están registrados.
- **Baja lógica, no borrado:** desactivar un usuario pone `activo: false`. Si se
  borrara, los `usuario_id` que los otros microservicios guardan como
  responsables de proyectos y tareas quedarían huérfanos.
- Los 30,000 usuarios ficticios **comparten un hash precalculado** (clave
  `Demo1234`). Hashear cada uno con los 200,000 ciclos tomaría ~25 minutos; con
  uno solo el seed corre en segundos y el login sigue siendo real.
