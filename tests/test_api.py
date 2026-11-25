import os
import uuid

import pytest

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@test.com")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin123")


def uniq():
    return uuid.uuid4().hex[:8]


# ---------------------------------------------------------------- Health
def test_health(api):
    r = api.get("/api/health", auth=False)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ---------------------------------------------------------------- Login
def test_login_ok(api):
    r = api.post("/api/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, auth=False)
    assert r.status_code == 200
    body = r.json()
    assert body["token"]
    assert body["user"]["email"] == ADMIN_EMAIL
    assert body["user"]["role"] == "admin"


def test_login_no_filtra_password(api):
    r = api.post("/api/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, auth=False)
    assert "password" not in r.json()["user"]


def test_login_password_incorrecta(api):
    r = api.post("/api/login", json={"email": ADMIN_EMAIL, "password": "incorrecta"}, auth=False)
    assert r.status_code == 401
    assert r.json()["error"] == "Credenciales inválidas"


def test_login_usuario_inexistente(api):
    r = api.post("/api/login", json={"email": f"{uniq()}@nadie.com", "password": "x"}, auth=False)
    assert r.status_code == 401


def test_login_credenciales_vacias(api):
    r = api.post("/api/login", json={"email": "", "password": ""}, auth=False)
    assert r.status_code == 401


# ---------------------------------------------------------------- Autorización
def test_users_requiere_token(api):
    assert api.get("/api/users", auth=False).status_code == 401


def test_products_requiere_token(api):
    assert api.get("/api/products", auth=False).status_code == 401


def test_token_invalido_rechazado(api):
    assert api.get("/api/users", token="abc.def.ghi").status_code == 401


# ---------------------------------------------------------------- CRUD Users
def test_users_listar(api):
    r = api.get("/api/users")
    assert r.status_code == 200
    assert ADMIN_EMAIL in [u["email"] for u in r.json()]


def test_users_crear(api):
    email = f"u_{uniq()}@test.com"
    r = api.post("/api/users", json={"name": "Nuevo", "email": email, "password": "Pass1234", "role": "user"})
    assert r.status_code == 201
    assert r.json()["email"] == email
    assert "password" not in r.json()


def test_users_crear_campos_faltantes(api):
    r = api.post("/api/users", json={"name": "Sin correo"})
    assert r.status_code == 400


def test_users_correo_duplicado(api, make_user):
    u = make_user()
    r = api.post("/api/users", json={"name": "Dup", "email": u["email"], "password": "Pass1234"})
    assert r.status_code == 409


def test_users_obtener_por_id(api, make_user):
    u = make_user()
    r = api.get(f"/api/users/{u['id']}")
    assert r.status_code == 200
    assert r.json()["email"] == u["email"]


def test_users_obtener_inexistente(api):
    assert api.get("/api/users/999999").status_code == 404


def test_users_actualizar(api, make_user):
    u = make_user()
    r = api.put(f"/api/users/{u['id']}", json={"name": "Editado", "email": u["email"], "role": "admin"})
    assert r.status_code == 200
    g = api.get(f"/api/users/{u['id']}").json()
    assert g["name"] == "Editado"
    assert g["role"] == "admin"


def test_users_eliminar(api, make_user):
    u = make_user()
    assert api.delete(f"/api/users/{u['id']}").status_code == 200
    assert api.get(f"/api/users/{u['id']}").status_code == 404


def test_users_eliminar_inexistente(api):
    assert api.delete("/api/users/999999").status_code == 404


def test_usuario_nuevo_puede_iniciar_sesion(api, make_user):
    u = make_user()
    r = api.post("/api/login", json={"email": u["email"], "password": u["password"]}, auth=False)
    assert r.status_code == 200
    assert r.json()["user"]["email"] == u["email"]


# ---------------------------------------------------------------- CRUD Productos
def test_products_listar(api, make_product):
    p = make_product()
    r = api.get("/api/products")
    assert r.status_code == 200
    assert p["id"] in [x["id"] for x in r.json()]


def test_products_crear(api):
    r = api.post("/api/products", json={"name": "Laptop", "price": 999.99, "stock": 5})
    assert r.status_code == 201
    body = r.json()
    assert body["price"] == 999.99
    assert body["stock"] == 5


@pytest.mark.parametrize("payload", [{"price": 10}, {"name": "Sin precio"}])
def test_products_crear_campos_faltantes(api, payload):
    assert api.post("/api/products", json=payload).status_code == 400


def test_products_obtener_por_id(api, make_product):
    p = make_product()
    r = api.get(f"/api/products/{p['id']}")
    assert r.status_code == 200
    assert r.json()["name"] == p["name"]


def test_products_obtener_inexistente(api):
    assert api.get("/api/products/999999").status_code == 404


def test_products_actualizar(api, make_product):
    p = make_product()
    r = api.put(f"/api/products/{p['id']}", json={"name": "Actualizado", "price": 50, "stock": 9})
    assert r.status_code == 200
    g = api.get(f"/api/products/{p['id']}").json()
    assert g["name"] == "Actualizado"
    assert g["price"] == 50
    assert g["stock"] == 9


def test_products_eliminar(api, make_product):
    p = make_product()
    assert api.delete(f"/api/products/{p['id']}").status_code == 200


def test_products_eliminado_ya_no_existe(api, make_product):
    p = make_product()
    api.delete(f"/api/products/{p['id']}")
    assert api.get(f"/api/products/{p['id']}").status_code == 404