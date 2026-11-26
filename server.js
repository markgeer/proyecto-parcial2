const tel = require('./telemetry'); // debe ir primero, antes de express
const express = require('express');
const Database = require('better-sqlite3');
const jwt = require('jsonwebtoken');
const bcrypt = require('bcryptjs');
const path = require('path');

const app = express();
app.use(tel.requestObserver);
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

const SECRET = process.env.JWT_SECRET || 'secreto123';
const db = tel.traceDb(new Database(process.env.DB_PATH || 'data.db'));

db.exec(`
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
  password TEXT NOT NULL, role TEXT DEFAULT 'user');
CREATE TABLE IF NOT EXISTS products(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL, price REAL NOT NULL, stock INTEGER DEFAULT 0);
`);

// Usuario admin por defecto
if (!db.prepare('SELECT 1 FROM users WHERE email=?').get('admin@test.com')) {
  db.prepare('INSERT INTO users(name,email,password,role) VALUES (?,?,?,?)')
    .run('Admin', 'admin@test.com', bcrypt.hashSync('admin123', 8), 'admin');
}

// Middleware de autenticación
function auth(req, res, next) {
  const h = req.headers.authorization || '';
  try {
    req.user = jwt.verify(h.replace('Bearer ', ''), SECRET);
    next();
  } catch {
    res.status(401).json({ error: 'No autorizado' });
  }
}

app.get('/api/health', (req, res) => res.json({ status: 'ok' }));

// ---------- LOGIN ----------
app.post('/api/login', (req, res) => {
  const { email, password } = req.body || {};
  const u = db.prepare('SELECT * FROM users WHERE email=?').get(email);
  if (!u || !bcrypt.compareSync(password || '', u.password))
    return res.status(401).json({ error: 'Credenciales inválidas' });
  const token = jwt.sign({ id: u.id, email: u.email, role: u.role }, SECRET, { expiresIn: '8h' });
  res.json({ token, user: { id: u.id, name: u.name, email: u.email, role: u.role } });
});

// ---------- CRUD USERS ----------
app.get('/api/users', auth, (req, res) =>
  res.json(db.prepare('SELECT id,name,email,role FROM users').all()));

app.get('/api/users/:id', auth, (req, res) => {
  const u = db.prepare('SELECT id,name,email,role FROM users WHERE id=?').get(req.params.id);
  u ? res.json(u) : res.status(404).json({ error: 'No encontrado' });
});

app.post('/api/users', auth, (req, res) => {
  const { name, email, password, role } = req.body || {};
  if (!name || !email || !password) return res.status(400).json({ error: 'Faltan campos' });
  try {
    const r = db.prepare('INSERT INTO users(name,email,password,role) VALUES (?,?,?,?)')
      .run(name, email, bcrypt.hashSync(password, 8), role || 'user');
    res.status(201).json({ id: r.lastInsertRowid, name, email, role: role || 'user' });
  } catch {
    res.status(409).json({ error: 'Email ya existe' });
  }
});

app.put('/api/users/:id', auth, (req, res) => {
  const { name, email, role } = req.body || {};
  const r = db.prepare('UPDATE users SET name=?, email=?, role=? WHERE id=?')
    .run(name, email, role || 'user', req.params.id);
  r.changes ? res.json({ id: +req.params.id, name, email, role }) : res.status(404).json({ error: 'No encontrado' });
});

app.delete('/api/users/:id', auth, (req, res) => {
  const r = db.prepare('DELETE FROM users WHERE id=?').run(req.params.id);
  r.changes ? res.json({ ok: true }) : res.status(404).json({ error: 'No encontrado' });
});

// ---------- CRUD PRODUCTOS ----------
app.get('/api/products', auth, (req, res) =>
  res.json(db.prepare('SELECT * FROM products').all()));

app.get('/api/products/:id', auth, (req, res) => {
  const p = db.prepare('SELECT * FROM products WHERE id=?').get(req.params.id);
  p ? res.json(p) : res.status(404).json({ error: 'No encontrado' });
});

app.post('/api/products', auth, (req, res) => {
  const { name, price, stock } = req.body || {};
  if (!name || price == null) return res.status(400).json({ error: 'Faltan campos' });
  const r = db.prepare('INSERT INTO products(name,price,stock) VALUES (?,?,?)').run(name, price, stock || 0);
  res.status(201).json({ id: r.lastInsertRowid, name, price, stock: stock || 0 });
});

app.put('/api/products/:id', auth, (req, res) => {
  const { name, price, stock } = req.body || {};
  const r = db.prepare('UPDATE products SET name=?, price=?, stock=? WHERE id=?')
    .run(name, price, stock || 0, req.params.id);
  r.changes ? res.json({ id: +req.params.id, name, price, stock }) : res.status(404).json({ error: 'No encontrado' });
});

app.delete('/api/products/:id', auth, (req, res) => {
  const r = db.prepare('DELETE FROM products WHERE id=?').run(req.params.id);
  r.changes ? res.json({ ok: true }) : res.status(404).json({ error: 'No encontrado' });
});

// Manejo de errores: registra la excepción en logs y trazas
app.use((err, req, res, next) => {
  tel.logError(err, req);
  res.status(err.status || 500).json({ error: err.status && err.status < 500 ? err.message : 'Error interno' });
});

module.exports = app;

if (require.main === module) {
  app.listen(process.env.PORT || 3000, () =>
    tel.log('INFO', 'Aplicación iniciada', { port: process.env.PORT || 3000, telemetria: tel.enabled }));
}