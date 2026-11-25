import os
import uuid

import pytest
from playwright.sync_api import expect

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@test.com")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin123")


def uniq():
    return uuid.uuid4().hex[:8]


def login(page, email=ADMIN_EMAIL, password=ADMIN_PASS):
    page.goto("/")
    page.fill("#email", email)
    page.fill("#password", password)
    page.click("#login-btn")


@pytest.fixture
def logged_page(page):
    login(page)
    expect(page.locator("#app-section")).to_be_visible()
    return page


def fill_user(page, name, email, password="Pass1234", role="user"):
    page.fill("#user-name", name)
    page.fill("#user-email", email)
    page.fill("#user-password", password)
    page.select_option("#user-role", role)
    page.click("#user-save")


def user_row(page, email):
    return page.locator("#users-body tr", has_text=email)


def product_row(page, name):
    return page.locator("#products-body tr", has_text=name)


def fill_product(page, name, price, stock):
    page.fill("#product-name", name)
    page.fill("#product-price", str(price))
    page.fill("#product-stock", str(stock))
    page.click("#product-save")


# ---------------------------------------------------------------- Login / sesión
def test_login_muestra_formulario(page):
    page.goto("/")
    expect(page.locator("#login-section")).to_be_visible()
    expect(page.locator("#app-section")).to_be_hidden()
    expect(page.locator("#login-btn")).to_be_visible()


def test_login_valido_entra_al_panel(page):
    login(page)
    expect(page.locator("#app-section")).to_be_visible()
    expect(page.locator("#welcome")).to_contain_text("Admin")


def test_login_invalido_muestra_error(page):
    login(page, password="incorrecta")
    expect(page.locator("#login-error")).to_have_text("Credenciales inválidas")
    expect(page.locator("#app-section")).to_be_hidden()


def test_sesion_persiste_al_recargar(logged_page):
    logged_page.reload()
    expect(logged_page.locator("#app-section")).to_be_visible()


def test_cerrar_sesion(logged_page):
    logged_page.click("#logout-btn")
    expect(logged_page.locator("#login-section")).to_be_visible()
    expect(logged_page.locator("#app-section")).to_be_hidden()


def test_cambiar_entre_usuarios_y_productos(logged_page):
    logged_page.click("#tab-products")
    expect(logged_page.locator("#products-section")).to_be_visible()
    expect(logged_page.locator("#users-section")).to_be_hidden()
    logged_page.click("#tab-users")
    expect(logged_page.locator("#users-section")).to_be_visible()
    expect(logged_page.locator("#products-section")).to_be_hidden()


# ---------------------------------------------------------------- CRUD Users (UI)
def test_ui_crear_usuario(logged_page):
    u = uniq()
    email = f"ui_{u}@test.com"
    fill_user(logged_page, f"Usuario {u}", email)
    expect(user_row(logged_page, email)).to_contain_text(f"Usuario {u}")


def test_ui_correo_duplicado_muestra_error(logged_page):
    u = uniq()
    email = f"ui_{u}@test.com"
    fill_user(logged_page, "Primero", email)
    expect(user_row(logged_page, email)).to_be_visible()
    fill_user(logged_page, "Segundo", email)
    expect(logged_page.locator("#user-error")).to_have_text("Email ya existe")


def test_ui_editar_usuario(logged_page):
    u = uniq()
    email = f"ui_{u}@test.com"
    fill_user(logged_page, "Antes", email)
    user_row(logged_page, email).locator(".edit-user").click()
    expect(logged_page.locator("#user-name")).to_have_value("Antes")
    logged_page.fill("#user-name", f"Despues {u}")
    logged_page.click("#user-save")
    expect(user_row(logged_page, email)).to_contain_text(f"Despues {u}")


def test_ui_eliminar_usuario(logged_page):
    email = f"ui_{uniq()}@test.com"
    fill_user(logged_page, "Borrar", email)
    expect(user_row(logged_page, email)).to_be_visible()
    user_row(logged_page, email).locator(".delete-user").click()
    expect(user_row(logged_page, email)).to_have_count(0)


# ---------------------------------------------------------------- CRUD Productos (UI)
def test_ui_crear_producto(logged_page):
    name = f"Prod {uniq()}"
    logged_page.click("#tab-products")
    fill_product(logged_page, name, 19.99, 7)
    expect(product_row(logged_page, name)).to_contain_text("19.99")


def test_ui_editar_producto(logged_page):
    name = f"Prod {uniq()}"
    logged_page.click("#tab-products")
    fill_product(logged_page, name, 10, 1)
    product_row(logged_page, name).locator(".edit-product").click()
    expect(logged_page.locator("#product-name")).to_have_value(name)
    logged_page.fill("#product-price", "99.5")
    logged_page.click("#product-save")
    expect(product_row(logged_page, name)).to_contain_text("99.50")


def test_ui_eliminar_producto(logged_page):
    name = f"Prod {uniq()}"
    logged_page.click("#tab-products")
    fill_product(logged_page, name, 5, 2)
    expect(product_row(logged_page, name)).to_be_visible()
    product_row(logged_page, name).locator(".delete-product").click()
    expect(product_row(logged_page, name)).to_have_count(0)