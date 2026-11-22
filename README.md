# ms-identidad

Inicio de sesion, emision del token JWT, usuarios y organizaciones.

Parte del proyecto final de Cloud Computing (CS2032), Grupo 4. Todas las rutas cuelgan de la API compartida `ppm-api-dev` bajo `/identidad` y, salvo el login, piden el token JWT.

Base de datos: DynamoDB (tabla ms-identidad-identidad-dev, clave TENANT#<id>).

## Endpoints

- POST /identidad/login
- GET /identidad/tenants
- GET /identidad/health
- GET /identidad/perfil
- POST /identidad/usuarios
- GET /identidad/usuarios
- GET /identidad/usuarios/{email}
- PUT /identidad/usuarios/{email}
- DELETE /identidad/usuarios/{email}

## Eventos

No publica ni consume eventos.

## Despliegue

Requiere que `infra-compartida` ya este desplegado.

```bash
npm install
npx serverless deploy
```

## Datos de prueba

```bash
python seed/generar.py
python seed/generar.py --contar
```
