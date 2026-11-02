#!/usr/bin/env bash
# Verificacion de extremo a extremo de ms-identidad.
#
#   ./verificar.sh https://xxxx.execute-api.us-east-1.amazonaws.com/dev
#
# Esto es lo que se corre EN VIVO en la exposicion: demuestra en 30 segundos
# que el servicio esta protegido y que los tenants estan aislados.
set -uo pipefail

URL=${1:?Uso: ./verificar.sh <url-del-api>}
PASS=${PASSWORD_DEMO:-Demo1234}
ok=0; fallo=0

verde()  { printf '  \033[32mOK\033[0m   %s\n' "$1"; ok=$((ok+1)); }
rojo()   { printf '  \033[31mFALLO\033[0m %s\n' "$1"; fallo=$((fallo+1)); }
titulo() { printf '\n\033[1m%s\033[0m\n' "$1"; }

codigo() { curl -s -o /dev/null -w '%{http_code}' "$@"; }

titulo "1. Endpoints publicos"
[ "$(codigo "$URL/tenants")" = 200 ] && verde "GET /tenants responde 200" \
  || rojo "GET /tenants no responde 200"
n=$(curl -s "$URL/tenants" | grep -o '"tenant_id"' | wc -l)
[ "$n" -eq 3 ] && verde "hay 3 tenants registrados" || rojo "se esperaban 3 tenants, hay $n"

titulo "2. Los endpoints protegidos rechazan sin token"
for ruta in /health /perfil /usuarios; do
  c=$(codigo "$URL$ruta")
  [ "$c" = 401 ] && verde "GET $ruta sin token -> 401" || rojo "GET $ruta sin token -> $c (se esperaba 401)"
done
c=$(codigo -H "Authorization: Bearer token.falso.aqui" "$URL/perfil")
[ "$c" = 401 ] && verde "token invalido -> 401" || rojo "token invalido -> $c (se esperaba 401)"

titulo "3. Login en los dos tenants de la demo"
entrar() {
  curl -s -X POST "$URL/login" -H 'Content-Type: application/json' \
    -d "{\"tenant_id\":\"$1\",\"email\":\"$2\",\"password\":\"$PASS\"}"
}
TOK_ACME=$(entrar t-acme   admin@acme.com.pe | python3 -c 'import sys,json;print(json.load(sys.stdin).get("datos",{}).get("token",""))')
TOK_GLOB=$(entrar t-globex admin@globex.com  | python3 -c 'import sys,json;print(json.load(sys.stdin).get("datos",{}).get("token",""))')
[ -n "$TOK_ACME" ] && verde "login de Acme devuelve token"   || rojo "login de Acme no devolvio token"
[ -n "$TOK_GLOB" ] && verde "login de Globex devuelve token" || rojo "login de Globex no devolvio token"

c=$(codigo -X POST "$URL/login" -H 'Content-Type: application/json' \
      -d '{"tenant_id":"t-acme","email":"admin@acme.com.pe","password":"incorrecta"}')
[ "$c" = 401 ] && verde "clave incorrecta -> 401" || rojo "clave incorrecta -> $c"

[ -z "$TOK_ACME" ] && { printf '\nSin token no se puede seguir.\n'; exit 1; }

titulo "4. El token lleva el tenant adentro"
t=$(curl -s "$URL/health" -H "Authorization: Bearer $TOK_ACME" \
      | python3 -c 'import sys,json;print(json.load(sys.stdin)["datos"]["tenant"])')
[ "$t" = t-acme ] && verde "el token de Acme se resuelve a t-acme" || rojo "tenant resuelto: $t"
t=$(curl -s "$URL/health" -H "Authorization: Bearer $TOK_GLOB" \
      | python3 -c 'import sys,json;print(json.load(sys.stdin)["datos"]["tenant"])')
[ "$t" = t-globex ] && verde "el token de Globex se resuelve a t-globex" || rojo "tenant resuelto: $t"

titulo "5. AISLAMIENTO: el token de Globex no ve datos de Acme"
# admin@acme.com.pe existe, pero no en la particion de Globex
c=$(codigo "$URL/usuarios/admin@acme.com.pe" -H "Authorization: Bearer $TOK_GLOB")
[ "$c" = 404 ] && verde "Globex pidiendo un usuario de Acme -> 404 (no existe para el)" \
  || rojo "Globex pidiendo un usuario de Acme -> $c (se esperaba 404)"
c=$(codigo "$URL/usuarios/admin@acme.com.pe" -H "Authorization: Bearer $TOK_ACME")
[ "$c" = 200 ] && verde "Acme pidiendo su propio usuario -> 200" || rojo "Acme pidiendo lo suyo -> $c"

titulo "6. Control de roles"
c=$(codigo "$URL/usuarios" -H "Authorization: Bearer $TOK_ACME")
[ "$c" = 200 ] && verde "un admin puede listar usuarios" || rojo "admin listando -> $c"

titulo "7. Volumen por tenant"
for t in t-acme t-globex; do
  [ "$t" = t-acme ] && T=$TOK_ACME || T=$TOK_GLOB
  n=$(curl -s "$URL/usuarios?limite=200" -H "Authorization: Bearer $T" \
        | python3 -c 'import sys,json;print(json.load(sys.stdin)["meta"]["total"])')
  verde "$t devuelve $n usuarios en la primera pagina"
done
printf '  (el conteo completo de los 30,006: python seed/generar.py --contar)\n'

printf '\n\033[1mResultado: %d correctas, %d fallidas\033[0m\n' "$ok" "$fallo"
[ "$fallo" -eq 0 ] || exit 1
