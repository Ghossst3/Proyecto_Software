from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
import bcrypt
import os
import re  # para validaciones simples
from flask import jsonify
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

app = Flask(__name__)
app.secret_key = os.urandom(24)  # necesario para sesiones

# Configuración de la base de datos
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '2004',
    'database': 'prueba1'
}

def get_connection():
    return mysql.connector.connect(**DB_CONFIG)

# ─── CONTROL DE ROLES ─────────────────────────────────────────────────────────
ROLES_ADMIN    = ['dueño', 'Encargado_mostrador']
ROLES_TECNICOS = ['dueño', 'Encargado_mostrador', 'Tecnico']
ROLES_ALMACEN  = ['dueño', 'Encargado_mostrador', 'Almacenista']
ROLES_BITACORA = ['dueño', 'encargado_mostrador', 'Tecnico']
ROLES_TODOS    = ['dueño', 'Encargado_mostrador', 'Tecnico', 'Almacenista']

def verificar_rol(roles_permitidos):
    """Devuelve True si el usuario en sesión tiene un rol permitido."""
    return session.get('user_rol') in roles_permitidos

@app.route('/')
def home():
    # Si ya está logueado, redirigir al dashboard
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    mensaje = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password'].encode('utf-8')
        
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT u.*, r.nombre as rol_nombre FROM usuarios u JOIN roles r ON u.rol_id = r.id WHERE u.nombre_usuario = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if user and bcrypt.checkpw(password, user['contrasena_hash'].encode('utf-8')):
            # Iniciar sesión
            session['user_id'] = user['id']
            session['user_name'] = user['nombre_completo']
            session['user_rol'] = user['rol_nombre']
            flash('Inicio de sesión exitoso', 'success')
            return redirect(url_for('dashboard'))
        else:
            mensaje = 'Usuario o contraseña incorrectos'
    
    return render_template('login.html', mensaje=mensaje)

@app.route('/dashboard')
# dashboard con tabla de ultimas ordenes de servicio
def dashboard():
    if 'user_id' not in session:
        flash('Por favor inicia sesión primero', 'warning')
        return redirect(url_for('login'))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT
            os.folio, os.estado, os.fecha_ingreso,
            c.nombre_completo AS nombre_cliente,
            e.tipo_equipo, e.marca, e.modelo
        FROM ordenes_servicio os
        JOIN clientes c ON os.cliente_id = c.id
        JOIN equipos  e ON os.equipo_id  = e.id
        ORDER BY os.fecha_ingreso DESC
        LIMIT 5
    """)
    ultimas_ordenes = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('dashboard.html',
                           nombre=session['user_name'],
                           rol=session['user_rol'],
                           ultimas_ordenes=ultimas_ordenes)

@app.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada', 'info')
    return redirect(url_for('login'))
@app.route('/clientes')
def clientes():
    if 'user_id' not in session:
        flash('Por favor inicia sesión primero', 'warning')
        return redirect(url_for('login'))
    if not verificar_rol(ROLES_TODOS):
        flash('No tienes permiso para acceder a esta sección', 'error')
        return redirect(url_for('dashboard'))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM clientes WHERE activo = 1 ORDER BY nombre_completo")
    lista = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('clientes.html',
                           clientes=lista,
                           nombre=session['user_name'],
                           rol=session['user_rol'])


# ─── REGISTRAR CLIENTE ────────────────────────────────────────────────────────
@app.route('/clientes/nuevo', methods=['GET', 'POST'])
def nuevo_cliente():
    if 'user_id' not in session:
        flash('Por favor inicia sesión primero', 'warning')
        return redirect(url_for('login'))
    if not verificar_rol(ROLES_ADMIN):
        flash('No tienes permiso para realizar esta acción', 'error')
        return redirect(url_for('clientes'))

    if request.method == 'POST':
        nombre   = request.form['nombre_completo'].strip()
        telefono = request.form['telefono'].strip()
        email    = request.form['email'].strip()
        direccion= request.form['direccion'].strip()
        rfc      = request.form['rfc'].strip().upper()
        tipo     = request.form['tipo_cliente']
        notas    = request.form['notas'].strip()

        if not nombre:
            flash('El nombre del cliente es obligatorio', 'error')
            return redirect(url_for('nuevo_cliente'))

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO clientes
                (nombre_completo, telefono, email, direccion, rfc, tipo_cliente, notas)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (nombre, telefono, email, direccion, rfc, tipo, notas))
        conn.commit()
        cursor.close()
        conn.close()

        flash(f'Cliente "{nombre}" registrado correctamente', 'success')
        return redirect(url_for('clientes'))

    return render_template('nuevo_cliente.html',
                           nombre=session['user_name'],
                           rol=session['user_rol'])


# ─── EDITAR CLIENTE ───────────────────────────────────────────────────────────
@app.route('/clientes/editar/<int:cliente_id>', methods=['GET', 'POST'])
def editar_cliente(cliente_id):
    if 'user_id' not in session:
        flash('Por favor inicia sesión primero', 'warning')
        return redirect(url_for('login'))
    if not verificar_rol(ROLES_ADMIN):
        flash('No tienes permiso para realizar esta acción', 'error')
        return redirect(url_for('clientes'))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        nombre   = request.form['nombre_completo'].strip()
        telefono = request.form['telefono'].strip()
        email    = request.form['email'].strip()
        direccion= request.form['direccion'].strip()
        rfc      = request.form['rfc'].strip().upper()
        tipo     = request.form['tipo_cliente']
        notas    = request.form['notas'].strip()

        cursor.execute("""
            UPDATE clientes SET
                nombre_completo = %s,
                telefono        = %s,
                email           = %s,
                direccion       = %s,
                rfc             = %s,
                tipo_cliente    = %s,
                notas           = %s
            WHERE id = %s
        """, (nombre, telefono, email, direccion, rfc, tipo, notas, cliente_id))
        conn.commit()
        cursor.close()
        conn.close()

        flash(f'Cliente actualizado correctamente', 'success')
        return redirect(url_for('clientes'))

    # GET → cargar datos actuales
    cursor.execute("SELECT * FROM clientes WHERE id = %s", (cliente_id,))
    cliente = cursor.fetchone()
    cursor.close()
    conn.close()

    if not cliente:
        flash('Cliente no encontrado', 'error')
        return redirect(url_for('clientes'))

    return render_template('editar_cliente.html',
                           cliente=cliente,
                           nombre=session['user_name'],
                           rol=session['user_rol'])


# ─── ELIMINAR CLIENTE (baja lógica) ──────────────────────────────────────────
@app.route('/clientes/eliminar/<int:cliente_id>')
def eliminar_cliente(cliente_id):
    if 'user_id' not in session:
        flash('Por favor inicia sesión primero', 'warning')
        return redirect(url_for('login'))
    if not verificar_rol(ROLES_ADMIN):
        flash('No tienes permiso para realizar esta acción', 'error')
        return redirect(url_for('clientes'))

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE clientes SET activo = 0 WHERE id = %s", (cliente_id,))
    conn.commit()
    cursor.close()
    conn.close()

    flash('Cliente eliminado correctamente', 'success')
    return redirect(url_for('clientes'))

@app.route('/equipos')
def equipos():
    if 'user_id' not in session:
        flash('Por favor inicia sesión primero', 'warning')
        return redirect(url_for('login'))
    if not verificar_rol(ROLES_TODOS):
        flash('No tienes permiso para acceder a esta sección', 'error')
        return redirect(url_for('dashboard'))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    # JOIN para mostrar el nombre del cliente junto al equipo
    cursor.execute("""
        SELECT e.*, c.nombre_completo AS nombre_cliente
        FROM equipos e
        JOIN clientes c ON e.cliente_id = c.id
        WHERE e.activo = 1
        ORDER BY c.nombre_completo, e.tipo_equipo
    """)
    lista = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('equipos.html',
                           equipos=lista,
                           nombre=session['user_name'],
                           rol=session['user_rol'])


# ─── REGISTRAR EQUIPO ─────────────────────────────────────────────────────────
@app.route('/equipos/nuevo', methods=['GET', 'POST'])
def nuevo_equipo():
    if 'user_id' not in session:
        flash('Por favor inicia sesión primero', 'warning')
        return redirect(url_for('login'))
    if not verificar_rol(ROLES_ADMIN):
        flash('No tienes permiso para realizar esta acción', 'error')
        return redirect(url_for('equipos'))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        cliente_id   = request.form['cliente_id']
        tipo_equipo  = request.form['tipo_equipo'].strip()
        marca        = request.form['marca'].strip()
        modelo       = request.form['modelo'].strip()
        numero_serie = request.form['numero_serie'].strip()
        anio         = request.form['anio'].strip() or None
        color        = request.form['color'].strip()
        descripcion  = request.form['descripcion'].strip()

        if not tipo_equipo or not cliente_id:
            flash('El tipo de equipo y el cliente son obligatorios', 'error')
            return redirect(url_for('nuevo_equipo'))

        cursor.execute("""
            INSERT INTO equipos
                (cliente_id, tipo_equipo, marca, modelo, numero_serie, anio, color, descripcion)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (cliente_id, tipo_equipo, marca, modelo, numero_serie, anio, color, descripcion))
        conn.commit()
        cursor.close()
        conn.close()

        flash(f'Equipo "{marca} {modelo}" registrado correctamente', 'success')
        return redirect(url_for('equipos'))

    # GET → cargar lista de clientes para el select
    cursor.execute("SELECT id, nombre_completo FROM clientes WHERE activo = 1 ORDER BY nombre_completo")
    clientes = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('nuevo_equipo.html',
                           clientes=clientes,
                           nombre=session['user_name'],
                           rol=session['user_rol'])


# ─── EDITAR EQUIPO ────────────────────────────────────────────────────────────
@app.route('/equipos/editar/<int:equipo_id>', methods=['GET', 'POST'])
def editar_equipo(equipo_id):
    if 'user_id' not in session:
        flash('Por favor inicia sesión primero', 'warning')
        return redirect(url_for('login'))
    if not verificar_rol(ROLES_ADMIN):
        flash('No tienes permiso para realizar esta acción', 'error')
        return redirect(url_for('equipos'))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        cliente_id   = request.form['cliente_id']
        tipo_equipo  = request.form['tipo_equipo'].strip()
        marca        = request.form['marca'].strip()
        modelo       = request.form['modelo'].strip()
        numero_serie = request.form['numero_serie'].strip()
        anio         = request.form['anio'].strip() or None
        color        = request.form['color'].strip()
        descripcion  = request.form['descripcion'].strip()

        cursor.execute("""
            UPDATE equipos SET
                cliente_id   = %s,
                tipo_equipo  = %s,
                marca        = %s,
                modelo       = %s,
                numero_serie = %s,
                anio         = %s,
                color        = %s,
                descripcion  = %s
            WHERE id = %s
        """, (cliente_id, tipo_equipo, marca, modelo, numero_serie, anio, color, descripcion, equipo_id))
        conn.commit()
        cursor.close()
        conn.close()

        flash('Equipo actualizado correctamente', 'success')
        return redirect(url_for('equipos'))

    # GET → cargar datos del equipo y lista de clientes
    cursor.execute("SELECT * FROM equipos WHERE id = %s", (equipo_id,))
    equipo = cursor.fetchone()

    cursor.execute("SELECT id, nombre_completo FROM clientes WHERE activo = 1 ORDER BY nombre_completo")
    clientes = cursor.fetchall()
    cursor.close()
    conn.close()

    if not equipo:
        flash('Equipo no encontrado', 'error')
        return redirect(url_for('equipos'))

    return render_template('editar_equipo.html',
                           equipo=equipo,
                           clientes=clientes,
                           nombre=session['user_name'],
                           rol=session['user_rol'])


# ─── EQUIPOS DE UN CLIENTE ESPECÍFICO (útil para órdenes) ────────────────────
@app.route('/equipos/cliente/<int:cliente_id>')
def equipos_por_cliente(cliente_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, tipo_equipo, marca, modelo, numero_serie
        FROM equipos
        WHERE cliente_id = %s AND activo = 1
        ORDER BY tipo_equipo
    """, (cliente_id,))
    lista = cursor.fetchall()
    cursor.close()
    conn.close()

    # Devuelve JSON → lo usaremos en órdenes de servicio con JavaScript
    from flask import jsonify
    return jsonify(lista)


# ─── ELIMINAR EQUIPO (baja lógica) ───────────────────────────────────────────
@app.route('/equipos/eliminar/<int:equipo_id>')
def eliminar_equipo(equipo_id):
    if 'user_id' not in session:
        flash('Por favor inicia sesión primero', 'warning')
        return redirect(url_for('login'))
    if not verificar_rol(ROLES_ADMIN):
        flash('No tienes permiso para realizar esta acción', 'error')
        return redirect(url_for('equipos'))

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE equipos SET activo = 0 WHERE id = %s", (equipo_id,))
    conn.commit()
    cursor.close()
    conn.close()

    flash('Equipo eliminado correctamente', 'success')
    return redirect(url_for('equipos'))


# ─── LISTAR ÓRDENES ───────────────────────────────────────────────────────────
@app.route('/ordenes')
def ordenes():
    if 'user_id' not in session:
        flash('Por favor inicia sesión primero', 'warning')
        return redirect(url_for('login'))
    if not verificar_rol(ROLES_TODOS):
        flash('No tienes permiso para acceder a esta sección', 'error')
        return redirect(url_for('dashboard'))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT
            os.*,
            c.nombre_completo   AS nombre_cliente,
            e.tipo_equipo, e.marca, e.modelo,
            u.nombre_completo   AS nombre_tecnico
        FROM ordenes_servicio os
        JOIN clientes c  ON os.cliente_id  = c.id
        JOIN equipos  e  ON os.equipo_id   = e.id
        LEFT JOIN usuarios u ON os.tecnico_id = u.id
        ORDER BY
            FIELD(os.estado, 'recibido','diagnosticando','esperando_refacciones','en_reparacion','listo','entregado'),
            os.prioridad DESC,
            os.fecha_ingreso DESC
    """)
    lista = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('ordenes.html',
                           ordenes=lista,
                           nombre=session['user_name'],
                           rol=session['user_rol'])


# ─── DETALLE DE UNA ORDEN ─────────────────────────────────────────────────────
@app.route('/ordenes/<int:orden_id>')
def detalle_orden(orden_id):
    if 'user_id' not in session:
        flash('Por favor inicia sesión primero', 'warning')
        return redirect(url_for('login'))
    if not verificar_rol(ROLES_TODOS):
        flash('No tienes permiso para acceder a esta sección', 'error')
        return redirect(url_for('dashboard'))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT
            os.*,
            c.nombre_completo AS nombre_cliente, c.telefono, c.email,
            e.tipo_equipo, e.marca, e.modelo, e.numero_serie, e.anio, e.color,
            u.nombre_completo AS nombre_tecnico
        FROM ordenes_servicio os
        JOIN clientes c  ON os.cliente_id  = c.id
        JOIN equipos  e  ON os.equipo_id   = e.id
        LEFT JOIN usuarios u ON os.tecnico_id = u.id
        WHERE os.id = %s
    """, (orden_id,))
    orden = cursor.fetchone()

    if not orden:
        cursor.close()
        conn.close()
        flash('Orden no encontrada', 'error')
        return redirect(url_for('ordenes'))

    # Últimos 3 avances de bitácora
    cursor.execute("""
        SELECT b.descripcion, b.estado_anterior, b.estado_nuevo,
               b.fecha_hora, u.nombre_completo AS usuario_nombre
        FROM bitacora_orden b
        JOIN usuarios u ON b.usuario_id = u.id
        WHERE b.orden_id = %s
        ORDER BY b.fecha_hora DESC
        LIMIT 3
    """, (orden_id,))
    ultimos_avances = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('detalle_orden.html',
                           orden=orden,
                           ultimos_avances=ultimos_avances,
                           puede_agregar_bitacora=verificar_rol(ROLES_BITACORA),
                           nombre=session['user_name'],
                           rol=session['user_rol'])


# ─── NUEVA ORDEN ──────────────────────────────────────────────────────────────
@app.route('/ordenes/nueva', methods=['GET', 'POST'])
def nueva_orden():
    if 'user_id' not in session:
        flash('Por favor inicia sesión primero', 'warning')
        return redirect(url_for('login'))
    if not verificar_rol(ROLES_TECNICOS):
        flash('No tienes permiso para realizar esta acción', 'error')
        return redirect(url_for('ordenes'))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        cliente_id           = request.form['cliente_id']
        equipo_id            = request.form['equipo_id']
        tecnico_id           = request.form['tecnico_id'] or None
        descripcion_problema = request.form['descripcion_problema'].strip()
        prioridad            = request.form['prioridad']
        fecha_estimada       = request.form['fecha_estimada'] or None
        costo_estimado       = request.form['costo_estimado'] or None
        observaciones        = request.form['observaciones'].strip()

        if not descripcion_problema or not cliente_id or not equipo_id:
            flash('Cliente, equipo y descripción del problema son obligatorios', 'error')
            return redirect(url_for('nueva_orden'))

        cursor.execute("""
            INSERT INTO ordenes_servicio
                (folio, cliente_id, equipo_id, tecnico_id,
                 descripcion_problema, prioridad,
                 fecha_estimada, costo_estimado, observaciones)
            VALUES ('', %s, %s, %s, %s, %s, %s, %s, %s)
        """, (cliente_id, equipo_id, tecnico_id,
              descripcion_problema, prioridad,
              fecha_estimada, costo_estimado, observaciones))
        conn.commit()
        cursor.close()
        conn.close()

        flash('Orden de servicio creada correctamente', 'success')
        return redirect(url_for('ordenes'))

    # GET → cargar clientes y técnicos para los selects
    cursor.execute("SELECT id, nombre_completo FROM clientes WHERE activo = 1 ORDER BY nombre_completo")
    clientes = cursor.fetchall()

    cursor.execute("""
        SELECT u.id, u.nombre_completo
        FROM usuarios u
        JOIN roles r ON u.rol_id = r.id
        WHERE r.nombre IN ('tecnico', 'Tecnico', 'TECNICO')
        ORDER BY u.nombre_completo
    """)
    tecnicos = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('nueva_orden.html',
                           clientes=clientes,
                           tecnicos=tecnicos,
                           nombre=session['user_name'],
                           rol=session['user_rol'])


# ─── CAMBIAR ESTADO DE UNA ORDEN ──────────────────────────────────────────────
@app.route('/ordenes/<int:orden_id>/estado', methods=['POST'])
def cambiar_estado(orden_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if not verificar_rol(ROLES_TECNICOS):
        flash('No tienes permiso para realizar esta acción', 'error')
        return redirect(url_for('detalle_orden', orden_id=orden_id))

    nuevo_estado = request.form['estado']
    estados_validos = ['recibido','diagnosticando','esperando_refacciones',
                       'en_reparacion','listo','entregado']

    if nuevo_estado not in estados_validos:
        flash('Estado no válido', 'error')
        return redirect(url_for('detalle_orden', orden_id=orden_id))

    conn = get_connection()
    cursor = conn.cursor()

    # Si se marca como entregado, registrar fecha real
    if nuevo_estado == 'entregado':
        cursor.execute("""
            UPDATE ordenes_servicio
            SET estado = %s, fecha_entrega_real = NOW()
            WHERE id = %s
        """, (nuevo_estado, orden_id))
    else:
        cursor.execute("UPDATE ordenes_servicio SET estado = %s WHERE id = %s",
                       (nuevo_estado, orden_id))

    conn.commit()
    cursor.close()
    conn.close()

    flash('Estado actualizado correctamente', 'success')
    return redirect(url_for('detalle_orden', orden_id=orden_id))


# ─── EDITAR ORDEN ─────────────────────────────────────────────────────────────
@app.route('/ordenes/editar/<int:orden_id>', methods=['GET', 'POST'])
def editar_orden(orden_id):
    if 'user_id' not in session:
        flash('Por favor inicia sesión primero', 'warning')
        return redirect(url_for('login'))
    if not verificar_rol(ROLES_TECNICOS):
        flash('No tienes permiso para realizar esta acción', 'error')
        return redirect(url_for('detalle_orden', orden_id=orden_id))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        tecnico_id           = request.form['tecnico_id'] or None
        descripcion_problema = request.form['descripcion_problema'].strip()
        prioridad            = request.form['prioridad']
        fecha_estimada       = request.form['fecha_estimada'] or None
        costo_estimado       = request.form['costo_estimado'] or None
        costo_final          = request.form['costo_final'] or None
        observaciones        = request.form['observaciones'].strip()

        cursor.execute("""
            UPDATE ordenes_servicio SET
                tecnico_id           = %s,
                descripcion_problema = %s,
                prioridad            = %s,
                fecha_estimada       = %s,
                costo_estimado       = %s,
                costo_final          = %s,
                observaciones        = %s
            WHERE id = %s
        """, (tecnico_id, descripcion_problema, prioridad,
              fecha_estimada, costo_estimado, costo_final,
              observaciones, orden_id))
        conn.commit()
        cursor.close()
        conn.close()

        flash('Orden actualizada correctamente', 'success')
        return redirect(url_for('detalle_orden', orden_id=orden_id))

    # GET
    cursor.execute("SELECT * FROM ordenes_servicio WHERE id = %s", (orden_id,))
    orden = cursor.fetchone()

    cursor.execute("""
        SELECT u.id, u.nombre_completo FROM usuarios u
        JOIN roles r ON u.rol_id = r.id
        WHERE r.nombre IN ('tecnico','Tecnico','TECNICO')
    """)
    tecnicos = cursor.fetchall()
    cursor.close()
    conn.close()

    if not orden:
        flash('Orden no encontrada', 'error')
        return redirect(url_for('ordenes'))

    return render_template('editar_orden.html',
                           orden=orden,
                           tecnicos=tecnicos,
                           nombre=session['user_name'],
                           rol=session['user_rol'])

# ─── LISTAR REFACCIONES ───────────────────────────────────────────────────────
@app.route('/refacciones')
def refacciones():
    if 'user_id' not in session:
        flash('Por favor inicia sesión primero', 'warning')
        return redirect(url_for('login'))
    if not verificar_rol(ROLES_TECNICOS):
        flash('No tienes permiso para acceder a esta sección', 'error')
        return redirect(url_for('dashboard'))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT * FROM refacciones
        WHERE activo = 1
        ORDER BY
            stock_actual <= stock_minimo DESC,
            categoria, nombre
    """)
    lista = cursor.fetchall()
    cursor.close()
    conn.close()

    # Forzar conversión a int para evitar error de comparación en Jinja
    for r in lista:
        r['stock_actual'] = int(r['stock_actual'] or 0)
        r['stock_minimo'] = int(r['stock_minimo'] or 0)
        r['stock_bajo'] = r['stock_actual'] <= r['stock_minimo']

    return render_template('refacciones.html',
                           refacciones=lista,
                           nombre=session['user_name'],
                           rol=session['user_rol'])


# ─── NUEVA REFACCIÓN ──────────────────────────────────────────────────────────
@app.route('/refacciones/nueva', methods=['GET', 'POST'])
def nueva_refaccion():
    if 'user_id' not in session:
        flash('Por favor inicia sesión primero', 'warning')
        return redirect(url_for('login'))
    if not verificar_rol(ROLES_TECNICOS):
        flash('No tienes permiso para realizar esta acción', 'error')
        return redirect(url_for('refacciones'))

    if request.method == 'POST':
        nombre           = request.form['nombre'].strip()
        descripcion      = request.form['descripcion'].strip()
        categoria        = request.form['categoria'].strip()
        marca_compatible = request.form['marca_compatible'].strip()
        unidad           = request.form['unidad']
        stock_actual     = int(request.form['stock_actual'] or 0)
        stock_minimo     = int(request.form['stock_minimo'] or 2)
        precio_compra    = request.form['precio_compra'] or None
        precio_venta     = request.form['precio_venta'] or None
        ubicacion        = request.form['ubicacion'].strip()

        if not nombre:
            flash('El nombre de la refacción es obligatorio', 'error')
            return redirect(url_for('nueva_refaccion'))

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO refacciones
                (codigo, nombre, descripcion, categoria, marca_compatible,
                 unidad, stock_actual, stock_minimo, precio_compra, precio_venta, ubicacion)
            VALUES ('', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (nombre, descripcion, categoria, marca_compatible,
              unidad, stock_actual, stock_minimo,
              precio_compra, precio_venta, ubicacion))
        conn.commit()
        cursor.close()
        conn.close()

        flash(f'Refacción "{nombre}" registrada correctamente', 'success')
        return redirect(url_for('refacciones'))

    return render_template('nueva_refaccion.html',
                           nombre=session['user_name'],
                           rol=session['user_rol'])


# ─── EDITAR REFACCIÓN ─────────────────────────────────────────────────────────
@app.route('/refacciones/editar/<int:ref_id>', methods=['GET', 'POST'])
def editar_refaccion(ref_id):
    if 'user_id' not in session:
        flash('Por favor inicia sesión primero', 'warning')
        return redirect(url_for('login'))
    if not verificar_rol(ROLES_ADMIN):
        flash('No tienes permiso para realizar esta acción', 'error')
        return redirect(url_for('refacciones'))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        nombre           = request.form['nombre'].strip()
        descripcion      = request.form['descripcion'].strip()
        categoria        = request.form['categoria'].strip()
        marca_compatible = request.form['marca_compatible'].strip()
        unidad           = request.form['unidad']
        stock_actual     = int(request.form['stock_actual'] or 0)
        stock_minimo     = int(request.form['stock_minimo'] or 2)
        precio_compra    = request.form['precio_compra'] or None
        precio_venta     = request.form['precio_venta'] or None
        ubicacion        = request.form['ubicacion'].strip()

        cursor.execute("""
            UPDATE refacciones SET
                nombre           = %s,
                descripcion      = %s,
                categoria        = %s,
                marca_compatible = %s,
                unidad           = %s,
                stock_actual     = %s,
                stock_minimo     = %s,
                precio_compra    = %s,
                precio_venta     = %s,
                ubicacion        = %s
            WHERE id = %s
        """, (nombre, descripcion, categoria, marca_compatible,
              unidad, stock_actual, stock_minimo,
              precio_compra, precio_venta, ubicacion, ref_id))
        conn.commit()
        cursor.close()
        conn.close()

        flash('Refacción actualizada correctamente', 'success')
        return redirect(url_for('refacciones'))

    cursor.execute("SELECT * FROM refacciones WHERE id = %s", (ref_id,))
    ref = cursor.fetchone()
    cursor.close()
    conn.close()

    if not ref:
        flash('Refacción no encontrada', 'error')
        return redirect(url_for('refacciones'))

    return render_template('editar_refaccion.html',
                           ref=ref,
                           nombre=session['user_name'],
                           rol=session['user_rol'])


# ─── AJUSTE RÁPIDO DE STOCK (entrada / salida) ────────────────────────────────
@app.route('/refacciones/stock/<int:ref_id>', methods=['POST'])
def ajustar_stock(ref_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if not verificar_rol(ROLES_ALMACEN):
        flash('No tienes permiso para realizar esta acción', 'error')
        return redirect(url_for('refacciones'))

    operacion = request.form['operacion']   # 'entrada' o 'salida'
    cantidad  = int(request.form['cantidad'] or 0)

    if cantidad <= 0:
        flash('La cantidad debe ser mayor a cero', 'error')
        return redirect(url_for('refacciones'))

    conn = get_connection()
    cursor = conn.cursor()

    if operacion == 'entrada':
        cursor.execute("UPDATE refacciones SET stock_actual = stock_actual + %s WHERE id = %s",
                       (cantidad, ref_id))
        flash(f'Entrada de {cantidad} unidad(es) registrada', 'success')
    elif operacion == 'salida':
        # Verificar que hay suficiente stock
        cursor2 = conn.cursor(dictionary=True)
        cursor2.execute("SELECT stock_actual, nombre FROM refacciones WHERE id = %s", (ref_id,))
        ref = cursor2.fetchone()
        cursor2.close()
        if ref['stock_actual'] < cantidad:
            flash(f'Stock insuficiente. Solo hay {ref["stock_actual"]} unidad(es) de {ref["nombre"]}', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('refacciones'))
        cursor.execute("UPDATE refacciones SET stock_actual = stock_actual - %s WHERE id = %s",
                       (cantidad, ref_id))
        flash(f'Salida de {cantidad} unidad(es) registrada', 'success')

    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('refacciones'))


# ─── ELIMINAR REFACCIÓN (baja lógica) ────────────────────────────────────────
@app.route('/refacciones/eliminar/<int:ref_id>')
def eliminar_refaccion(ref_id):
    if 'user_id' not in session:
        flash('Por favor inicia sesión primero', 'warning')
        return redirect(url_for('login'))
    if not verificar_rol(ROLES_ADMIN):
        flash('No tienes permiso para realizar esta acción', 'error')
        return redirect(url_for('refacciones'))

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE refacciones SET activo = 0 WHERE id = %s", (ref_id,))
    conn.commit()
    cursor.close()
    conn.close()

    flash('Refacción eliminada del inventario', 'success')
    return redirect(url_for('refacciones'))

# ─── VER REFACCIONES DE UNA ORDEN ─────────────────────────────────────────────
# Esta ruta ya está cubierta dentro de detalle_orden,
# pero también se expone como JSON para uso interno.
@app.route('/ordenes/<int:orden_id>/refacciones')
def refacciones_de_orden(orden_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if not verificar_rol(ROLES_TECNICOS):
        flash('No tienes permiso para acceder a esta sección', 'error')
        return redirect(url_for('dashboard'))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT
            ro.id, ro.cantidad, ro.precio_unitario, ro.subtotal, ro.notas,
            r.nombre AS nombre_refaccion, r.codigo, r.unidad
        FROM refacciones_orden ro
        JOIN refacciones r ON ro.refaccion_id = r.id
        WHERE ro.orden_id = %s
        ORDER BY ro.fecha_registro
    """, (orden_id,))
    items = cursor.fetchall()

    # Calcular total de refacciones
    total = sum(float(i['subtotal'] or 0) for i in items)

    # Forzar tipos para Jinja
    for i in items:
        i['cantidad']        = int(i['cantidad'])
        i['precio_unitario'] = float(i['precio_unitario'])
        i['subtotal']        = float(i['subtotal'] or 0)

    cursor.close()
    conn.close()

    return {'items': items, 'total': total}


# ─── AGREGAR REFACCIÓN A ORDEN ────────────────────────────────────────────────
@app.route('/ordenes/<int:orden_id>/refacciones/agregar', methods=['GET', 'POST'])
def agregar_refaccion_orden(orden_id):
    if 'user_id' not in session:
        flash('Por favor inicia sesión primero', 'warning')
        return redirect(url_for('login'))
    if not verificar_rol(ROLES_TECNICOS):
        flash('No tienes permiso para realizar esta acción', 'error')
        return redirect(url_for('detalle_orden', orden_id=orden_id))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        refaccion_id    = int(request.form['refaccion_id'])
        cantidad        = int(request.form['cantidad'] or 1)
        precio_unitario = float(request.form['precio_unitario'] or 0)
        notas           = request.form['notas'].strip()

        # Verificar stock disponible
        cursor.execute("SELECT stock_actual, nombre FROM refacciones WHERE id = %s", (refaccion_id,))
        ref = cursor.fetchone()

        if not ref:
            flash('Refacción no encontrada', 'error')
            return redirect(url_for('agregar_refaccion_orden', orden_id=orden_id))

        if int(ref['stock_actual']) < cantidad:
            flash(f'Stock insuficiente. Solo hay {ref["stock_actual"]} unidad(es) de "{ref["nombre"]}"', 'error')
            return redirect(url_for('agregar_refaccion_orden', orden_id=orden_id))

        # Insertar — el trigger descuenta el stock automáticamente
        cursor.execute("""
            INSERT INTO refacciones_orden
                (orden_id, refaccion_id, cantidad, precio_unitario, notas)
            VALUES (%s, %s, %s, %s, %s)
        """, (orden_id, refaccion_id, cantidad, precio_unitario, notas))

        # Actualizar costo_final de la orden sumando todos los subtotales
        cursor.execute("""
            UPDATE ordenes_servicio
            SET costo_final = (
                SELECT COALESCE(SUM(subtotal), 0)
                FROM refacciones_orden
                WHERE orden_id = %s
            )
            WHERE id = %s
        """, (orden_id, orden_id))

        conn.commit()
        cursor.close()
        conn.close()

        flash(f'Refacción "{ref["nombre"]}" agregada correctamente a la orden', 'success')
        return redirect(url_for('detalle_orden', orden_id=orden_id))

    # GET → cargar orden + refacciones disponibles con stock
    cursor.execute("""
        SELECT os.*, c.nombre_completo AS nombre_cliente,
               e.tipo_equipo, e.marca, e.modelo
        FROM ordenes_servicio os
        JOIN clientes c ON os.cliente_id = c.id
        JOIN equipos  e ON os.equipo_id  = e.id
        WHERE os.id = %s
    """, (orden_id,))
    orden = cursor.fetchone()

    if not orden:
        flash('Orden no encontrada', 'error')
        return redirect(url_for('ordenes'))

    cursor.execute("""
        SELECT id, codigo, nombre, unidad, stock_actual, precio_venta
        FROM refacciones
        WHERE activo = 1 AND stock_actual > 0
        ORDER BY nombre
    """)
    refacciones_disponibles = cursor.fetchall()

    # Refacciones ya agregadas a esta orden
    cursor.execute("""
        SELECT ro.id, ro.cantidad, ro.precio_unitario, ro.subtotal, ro.notas,
               r.nombre AS nombre_refaccion, r.codigo, r.unidad
        FROM refacciones_orden ro
        JOIN refacciones r ON ro.refaccion_id = r.id
        WHERE ro.orden_id = %s
        ORDER BY ro.fecha_registro
    """, (orden_id,))
    items_actuales = cursor.fetchall()

    for i in items_actuales:
        i['cantidad']        = int(i['cantidad'])
        i['precio_unitario'] = float(i['precio_unitario'])
        i['subtotal']        = float(i['subtotal'] or 0)

    for r in refacciones_disponibles:
        r['stock_actual'] = int(r['stock_actual'])
        r['precio_venta'] = float(r['precio_venta'] or 0)

    total_refacciones = sum(i['subtotal'] for i in items_actuales)

    cursor.close()
    conn.close()

    return render_template('refacciones_orden.html',
                           orden=orden,
                           refacciones_disponibles=refacciones_disponibles,
                           items_actuales=items_actuales,
                           total_refacciones=total_refacciones,
                           nombre=session['user_name'],
                           rol=session['user_rol'])


# ─── ELIMINAR REFACCIÓN DE ORDEN ──────────────────────────────────────────────
@app.route('/ordenes/refacciones/eliminar/<int:item_id>', methods=['POST'])
def eliminar_refaccion_orden(item_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if not verificar_rol(ROLES_TECNICOS):
        flash('No tienes permiso para realizar esta acción', 'error')
        return redirect(url_for('ordenes'))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Obtener orden_id antes de eliminar para redirigir correctamente
    cursor.execute("SELECT orden_id FROM refacciones_orden WHERE id = %s", (item_id,))
    item = cursor.fetchone()

    if not item:
        flash('Registro no encontrado', 'error')
        cursor.close()
        conn.close()
        return redirect(url_for('ordenes'))

    orden_id = item['orden_id']

    # Eliminar — el trigger devuelve el stock automáticamente
    cursor.execute("DELETE FROM refacciones_orden WHERE id = %s", (item_id,))

    # Recalcular costo_final de la orden
    cursor.execute("""
        UPDATE ordenes_servicio
        SET costo_final = (
            SELECT COALESCE(SUM(subtotal), 0)
            FROM refacciones_orden
            WHERE orden_id = %s
        )
        WHERE id = %s
    """, (orden_id, orden_id))

    conn.commit()
    cursor.close()
    conn.close()

    flash('Refacción eliminada de la orden y stock restaurado', 'success')
    return redirect(url_for('agregar_refaccion_orden', orden_id=orden_id))

# ─── LISTAR COTIZACIONES ──────────────────────────────────────────────────────
@app.route('/cotizaciones')
def cotizaciones():
    if 'user_id' not in session:
        flash('Por favor inicia sesión primero', 'warning')
        return redirect(url_for('login'))
    if not verificar_rol(ROLES_TECNICOS):
        flash('No tienes permiso para acceder a esta sección', 'error')
        return redirect(url_for('dashboard'))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT c.*, cl.nombre_completo AS nombre_cliente,
               u.nombre_completo AS creado_por_nombre
        FROM cotizaciones c
        JOIN clientes  cl ON c.cliente_id  = cl.id
        JOIN usuarios  u  ON c.creado_por  = u.id
        ORDER BY c.fecha_emision DESC
    """)
    lista = cursor.fetchall()
    cursor.close()
    conn.close()

    for c in lista:
        c['subtotal'] = float(c['subtotal'] or 0)
        c['total']    = float(c['total']    or 0)
        c['descuento']= float(c['descuento']or 0)

    return render_template('cotizaciones.html',
                           cotizaciones=lista,
                           nombre=session['user_name'],
                           rol=session['user_rol'])


# ─── NUEVA COTIZACIÓN ─────────────────────────────────────────────────────────
@app.route('/cotizaciones/nueva', methods=['GET', 'POST'])
def nueva_cotizacion():
    if 'user_id' not in session:
        flash('Por favor inicia sesión primero', 'warning')
        return redirect(url_for('login'))
    if not verificar_rol(ROLES_TECNICOS):
        flash('No tienes permiso para realizar esta acción', 'error')
        return redirect(url_for('cotizaciones'))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        cliente_id        = request.form['cliente_id']
        orden_id          = request.form.get('orden_id') or None
        fecha_vencimiento = request.form['fecha_vencimiento'] or None
        descuento         = float(request.form.get('descuento') or 0)
        notas             = request.form.get('notas', '').strip()
        notas_internas    = request.form.get('notas_internas', '').strip()

        # Recoger items dinámicos del formulario
        descripciones     = request.form.getlist('descripcion[]')
        cantidades        = request.form.getlist('cantidad[]')
        precios           = request.form.getlist('precio_unitario[]')

        if not descripciones or not any(d.strip() for d in descripciones):
            flash('Agrega al menos un concepto a la cotización', 'error')
            return redirect(url_for('nueva_cotizacion'))

        # Calcular subtotal y total
        subtotal = sum(
            float(c or 0) * float(p or 0)
            for c, p in zip(cantidades, precios)
        )
        total = max(subtotal - descuento, 0)

        # Insertar cotización
        cursor.execute("""
            INSERT INTO cotizaciones
                (folio, cliente_id, orden_id, creado_por,
                 fecha_vencimiento, subtotal, descuento, total,
                 notas, notas_internas)
            VALUES ('', %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (cliente_id, orden_id, session['user_id'],
              fecha_vencimiento, subtotal, descuento, total,
              notas, notas_internas))
        cotizacion_id = cursor.lastrowid

        # Insertar items
        for desc, cant, precio in zip(descripciones, cantidades, precios):
            if desc.strip():
                cursor.execute("""
                    INSERT INTO cotizacion_items
                        (cotizacion_id, descripcion, cantidad, precio_unitario)
                    VALUES (%s, %s, %s, %s)
                """, (cotizacion_id, desc.strip(),
                      float(cant or 1), float(precio or 0)))

        conn.commit()
        cursor.close()
        conn.close()

        flash('Cotización creada correctamente', 'success')
        return redirect(url_for('detalle_cotizacion', cotizacion_id=cotizacion_id))

    # GET → clientes y órdenes para los selects
    cursor.execute("SELECT id, nombre_completo FROM clientes WHERE activo=1 ORDER BY nombre_completo")
    clientes = cursor.fetchall()

    cursor.execute("""
        SELECT os.id, os.folio, c.nombre_completo AS nombre_cliente
        FROM ordenes_servicio os
        JOIN clientes c ON os.cliente_id = c.id
        WHERE os.estado NOT IN ('entregado')
        ORDER BY os.fecha_ingreso DESC
    """)
    ordenes = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('nueva_cotizacion.html',
                           clientes=clientes,
                           ordenes=ordenes,
                           nombre=session['user_name'],
                           rol=session['user_rol'])


# ─── DETALLE COTIZACIÓN ───────────────────────────────────────────────────────
@app.route('/cotizaciones/<int:cotizacion_id>')
def detalle_cotizacion(cotizacion_id):
    if 'user_id' not in session:
        flash('Por favor inicia sesión primero', 'warning')
        return redirect(url_for('login'))
    if not verificar_rol(ROLES_TECNICOS):
        flash('No tienes permiso para acceder a esta sección', 'error')
        return redirect(url_for('dashboard'))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT c.*, cl.nombre_completo AS nombre_cliente,
               cl.telefono, cl.email,
               u.nombre_completo AS creado_por_nombre,
               os.folio AS orden_folio
        FROM cotizaciones c
        JOIN clientes  cl ON c.cliente_id = cl.id
        JOIN usuarios  u  ON c.creado_por = u.id
        LEFT JOIN ordenes_servicio os ON c.orden_id = os.id
        WHERE c.id = %s
    """, (cotizacion_id,))
    cot = cursor.fetchone()

    if not cot:
        flash('Cotización no encontrada', 'error')
        return redirect(url_for('cotizaciones'))

    cursor.execute("""
        SELECT * FROM cotizacion_items
        WHERE cotizacion_id = %s ORDER BY id
    """, (cotizacion_id,))
    items = cursor.fetchall()
    cursor.close()
    conn.close()

    for i in items:
        i['cantidad']        = float(i['cantidad'])
        i['precio_unitario'] = float(i['precio_unitario'])
        i['subtotal']        = float(i['subtotal'] or 0)

    cot['subtotal']  = float(cot['subtotal']  or 0)
    cot['descuento'] = float(cot['descuento'] or 0)
    cot['total']     = float(cot['total']     or 0)

    return render_template('detalle_cotizacion.html',
                           cot=cot,
                           items=items,
                           nombre=session['user_name'],
                           rol=session['user_rol'])


# ─── CAMBIAR ESTADO COTIZACIÓN ────────────────────────────────────────────────
@app.route('/cotizaciones/<int:cotizacion_id>/estado', methods=['POST'])
def cambiar_estado_cotizacion(cotizacion_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if not verificar_rol(ROLES_TECNICOS):
        flash('No tienes permiso para realizar esta acción', 'error')
        return redirect(url_for('detalle_cotizacion', cotizacion_id=cotizacion_id))

    nuevo_estado = request.form['estado']
    estados_validos = ['borrador','enviada','aprobada','rechazada','vencida']

    if nuevo_estado not in estados_validos:
        flash('Estado no válido', 'error')
        return redirect(url_for('detalle_cotizacion', cotizacion_id=cotizacion_id))

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE cotizaciones SET estado = %s WHERE id = %s",
                   (nuevo_estado, cotizacion_id))
    conn.commit()
    cursor.close()
    conn.close()

    flash('Estado de cotización actualizado', 'success')
    return redirect(url_for('detalle_cotizacion', cotizacion_id=cotizacion_id))


# ─── ELIMINAR COTIZACIÓN ──────────────────────────────────────────────────────
@app.route('/cotizaciones/eliminar/<int:cotizacion_id>')
def eliminar_cotizacion(cotizacion_id):
    if 'user_id' not in session:
        flash('Por favor inicia sesión primero', 'warning')
        return redirect(url_for('login'))
    if not verificar_rol(ROLES_ADMIN):
        flash('No tienes permiso para realizar esta acción', 'error')
        return redirect(url_for('cotizaciones'))

    conn = get_connection()
    cursor = conn.cursor()
    # ON DELETE CASCADE elimina los items automáticamente
    cursor.execute("DELETE FROM cotizaciones WHERE id = %s", (cotizacion_id,))
    conn.commit()
    cursor.close()
    conn.close()

    flash('Cotización eliminada correctamente', 'success')
    return redirect(url_for('cotizaciones'))

# ─── REPORTES ─────────────────────────────────────────────────────────────────
@app.route('/reportes')
def reportes():
    if 'user_id' not in session:
        flash('Por favor inicia sesión primero', 'warning')
        return redirect(url_for('login'))
    if not verificar_rol(ROLES_ADMIN):
        flash('No tienes permiso para acceder a esta sección', 'error')
        return redirect(url_for('dashboard'))

    # Rango de fechas (por defecto: mes actual)
    hoy      = date.today()
    desde    = request.args.get('desde', hoy.replace(day=1).strftime('%Y-%m-%d'))
    hasta    = request.args.get('hasta', hoy.strftime('%Y-%m-%d'))

    conn   = get_connection()
    cursor = conn.cursor(dictionary=True)

    # ── 1. KPIs generales ─────────────────────────────────────────────────────
    cursor.execute("""
        SELECT
            COUNT(*) AS total_ordenes,
            SUM(estado = 'entregado') AS entregadas,
            SUM(estado IN ('recibido','diagnosticando','esperando_refacciones','en_reparacion','listo')) AS en_proceso,
            SUM(prioridad = 'urgente') AS urgentes,
            COALESCE(SUM(costo_final), 0) AS ingresos_total
        FROM ordenes_servicio
        WHERE DATE(fecha_ingreso) BETWEEN %s AND %s
    """, (desde, hasta))
    kpis = cursor.fetchone()

    cursor.execute("""
        SELECT COUNT(*) AS total_cotizaciones,
               SUM(estado = 'aprobada') AS aprobadas,
               COALESCE(SUM(CASE WHEN estado='aprobada' THEN total ELSE 0 END), 0) AS monto_aprobado
        FROM cotizaciones
        WHERE DATE(fecha_emision) BETWEEN %s AND %s
    """, (desde, hasta))
    kpis_cot = cursor.fetchone()

    cursor.execute("""
        SELECT COUNT(*) AS refacciones_bajo_stock
        FROM refacciones
        WHERE activo = 1 AND stock_actual <= stock_minimo
    """)
    kpis_ref = cursor.fetchone()

    # ── 2. Órdenes por estado ─────────────────────────────────────────────────
    cursor.execute("""
        SELECT estado, COUNT(*) AS total
        FROM ordenes_servicio
        WHERE DATE(fecha_ingreso) BETWEEN %s AND %s
        GROUP BY estado
        ORDER BY FIELD(estado,'recibido','diagnosticando','esperando_refacciones',
                              'en_reparacion','listo','entregado')
    """, (desde, hasta))
    ordenes_por_estado = cursor.fetchall()

    # ── 3. Ingresos por día (para gráfica) ────────────────────────────────────
    cursor.execute("""
        SELECT DATE(fecha_ingreso) AS dia,
               COUNT(*) AS num_ordenes,
               COALESCE(SUM(costo_final), 0) AS ingresos
        FROM ordenes_servicio
        WHERE DATE(fecha_ingreso) BETWEEN %s AND %s
        GROUP BY dia ORDER BY dia
    """, (desde, hasta))
    ingresos_dia = cursor.fetchall()

    # ── 4. Técnicos con más órdenes ───────────────────────────────────────────
    cursor.execute("""
        SELECT u.nombre_completo AS tecnico,
               COUNT(*) AS total_ordenes,
               SUM(os.estado = 'entregado') AS entregadas
        FROM ordenes_servicio os
        JOIN usuarios u ON os.tecnico_id = u.id
        WHERE DATE(os.fecha_ingreso) BETWEEN %s AND %s
        GROUP BY u.id ORDER BY total_ordenes DESC
        LIMIT 5
    """, (desde, hasta))
    top_tecnicos = cursor.fetchall()

    # ── 5. Refacciones más usadas ─────────────────────────────────────────────
    cursor.execute("""
        SELECT r.nombre, r.codigo, SUM(ro.cantidad) AS total_usado
        FROM refacciones_orden ro
        JOIN refacciones r ON ro.refaccion_id = r.id
        JOIN ordenes_servicio os ON ro.orden_id = os.id
        WHERE DATE(os.fecha_ingreso) BETWEEN %s AND %s
        GROUP BY r.id ORDER BY total_usado DESC
        LIMIT 8
    """, (desde, hasta))
    top_refacciones = cursor.fetchall()

    # ── 6. Clientes con más órdenes ───────────────────────────────────────────
    cursor.execute("""
        SELECT c.nombre_completo AS cliente, COUNT(*) AS total
        FROM ordenes_servicio os
        JOIN clientes c ON os.cliente_id = c.id
        WHERE DATE(os.fecha_ingreso) BETWEEN %s AND %s
        GROUP BY c.id ORDER BY total DESC
        LIMIT 5
    """, (desde, hasta))
    top_clientes = cursor.fetchall()

    # ── 7. Stock bajo (alerta) ────────────────────────────────────────────────
    cursor.execute("""
        SELECT nombre, codigo, stock_actual, stock_minimo, unidad
        FROM refacciones
        WHERE activo = 1 AND stock_actual <= stock_minimo
        ORDER BY stock_actual ASC
        LIMIT 10
    """)
    stock_bajo = cursor.fetchall()

    cursor.close()
    conn.close()

    # Forzar tipos numéricos
    kpis['ingresos_total']            = float(kpis['ingresos_total'] or 0)
    kpis['total_ordenes']             = int(kpis['total_ordenes'] or 0)
    kpis['entregadas']                = int(kpis['entregadas'] or 0)
    kpis['en_proceso']                = int(kpis['en_proceso'] or 0)
    kpis['urgentes']                  = int(kpis['urgentes'] or 0)

    kpis_cot['monto_aprobado']        = float(kpis_cot['monto_aprobado'] or 0)
    kpis_cot['total_cotizaciones']    = int(kpis_cot['total_cotizaciones'] or 0)
    kpis_cot['aprobadas']             = int(kpis_cot['aprobadas'] or 0)

    kpis_ref['refacciones_bajo_stock']= int(kpis_ref['refacciones_bajo_stock'] or 0)

    for e in ordenes_por_estado:
        e['total'] = int(e['total'] or 0)

    for i in ingresos_dia:
        i['ingresos']    = float(i['ingresos'] or 0)
        i['num_ordenes'] = int(i['num_ordenes'] or 0)
        i['dia']         = i['dia'].strftime('%d/%m')

    for t in top_tecnicos:
        t['total_ordenes'] = int(t['total_ordenes'] or 0)
        t['entregadas']    = int(t['entregadas'] or 0)

    for r in top_refacciones:
        r['total_usado'] = int(r['total_usado'] or 0)

    for c in top_clientes:
        c['total'] = int(c['total'] or 0)

    for s in stock_bajo:
        s['stock_actual'] = int(s['stock_actual'] or 0)
        s['stock_minimo'] = int(s['stock_minimo'] or 0)

    return render_template('reportes.html',
                           kpis=kpis,
                           kpis_cot=kpis_cot,
                           kpis_ref=kpis_ref,
                           ordenes_por_estado=ordenes_por_estado,
                           ingresos_dia=ingresos_dia,
                           top_tecnicos=top_tecnicos,
                           top_refacciones=top_refacciones,
                           top_clientes=top_clientes,
                           stock_bajo=stock_bajo,
                           desde=desde,
                           hasta=hasta,
                           nombre=session['user_name'],
                           rol=session['user_rol'])

# ─── LISTAR USUARIOS ──────────────────────────────────────────────────────────
@app.route('/usuarios')
def usuarios():
    if 'user_id' not in session:
        flash('Por favor inicia sesión primero', 'warning')
        return redirect(url_for('login'))
 
    if not verificar_rol(ROLES_ADMIN):
        flash('No tienes permiso para acceder a esta sección', 'error')
        return redirect(url_for('dashboard'))
 
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT u.id, u.nombre_usuario, u.nombre_completo, u.email,
               u.activo, r.nombre AS rol
        FROM usuarios u
        JOIN roles r ON u.rol_id = r.id
        ORDER BY u.activo DESC, r.nombre, u.nombre_completo
    """)
    lista = cursor.fetchall()
    cursor.close()
    conn.close()
 
    for u in lista:
        u['activo'] = int(u['activo'])
 
    return render_template('usuarios.html',
                           lista=lista,
                           nombre=session['user_name'],
                           rol=session['user_rol'])
 
 
# ─── NUEVO USUARIO ────────────────────────────────────────────────────────────
@app.route('/usuarios/nuevo', methods=['GET', 'POST'])
def nuevo_usuario():
    if 'user_id' not in session:
        flash('Por favor inicia sesión primero', 'warning')
        return redirect(url_for('login'))
 
    if not verificar_rol(ROLES_ADMIN):
        flash('No tienes permiso para acceder a esta sección', 'error')
        return redirect(url_for('dashboard'))
 
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
 
    if request.method == 'POST':
        nombre_usuario  = request.form['nombre_usuario'].strip()
        nombre_completo = request.form['nombre_completo'].strip()
        email           = request.form['email'].strip()
        rol_id          = int(request.form['rol_id'])
        password        = request.form['password']
        password_conf   = request.form['password_conf']
 
        # Validaciones
        if password != password_conf:
            flash('Las contraseñas no coinciden', 'error')
            return redirect(url_for('nuevo_usuario'))
 
        if len(password) < 6:
            flash('La contraseña debe tener al menos 6 caracteres', 'error')
            return redirect(url_for('nuevo_usuario'))
 
        # Verificar que el nombre de usuario no exista
        cursor.execute("SELECT id FROM usuarios WHERE nombre_usuario = %s", (nombre_usuario,))
        if cursor.fetchone():
            flash(f'El nombre de usuario "{nombre_usuario}" ya está en uso', 'error')
            return redirect(url_for('nuevo_usuario'))
 
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
 
        cursor.execute("""
            INSERT INTO usuarios
                (nombre_usuario, contrasena_hash, nombre_completo, email, rol_id, activo)
            VALUES (%s, %s, %s, %s, %s, 1)
        """, (nombre_usuario, password_hash, nombre_completo, email, rol_id))
 
        conn.commit()
        cursor.close()
        conn.close()
 
        flash(f'Usuario "{nombre_completo}" creado correctamente', 'success')
        return redirect(url_for('usuarios'))
 
    # GET → cargar roles disponibles
    cursor.execute("SELECT id, nombre FROM roles ORDER BY nombre")
    roles = cursor.fetchall()
    cursor.close()
    conn.close()
 
    return render_template('nuevo_usuario.html',
                           roles=roles,
                           nombre=session['user_name'],
                           rol=session['user_rol'])
 
 
# ─── EDITAR USUARIO ───────────────────────────────────────────────────────────
@app.route('/usuarios/editar/<int:user_id>', methods=['GET', 'POST'])
def editar_usuario(user_id):
    if 'user_id' not in session:
        flash('Por favor inicia sesión primero', 'warning')
        return redirect(url_for('login'))
 
    if not verificar_rol(ROLES_ADMIN):
        flash('No tienes permiso para acceder a esta sección', 'error')
        return redirect(url_for('dashboard'))
 
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
 
    if request.method == 'POST':
        nombre_usuario  = request.form['nombre_usuario'].strip()
        nombre_completo = request.form['nombre_completo'].strip()
        email           = request.form['email'].strip()
        rol_id          = int(request.form['rol_id'])
 
        # Verificar nombre de usuario único (excluyendo el actual)
        cursor.execute("""
            SELECT id FROM usuarios
            WHERE nombre_usuario = %s AND id != %s
        """, (nombre_usuario, user_id))
        if cursor.fetchone():
            flash(f'El nombre de usuario "{nombre_usuario}" ya está en uso', 'error')
            return redirect(url_for('editar_usuario', user_id=user_id))
 
        cursor.execute("""
            UPDATE usuarios SET
                nombre_usuario  = %s,
                nombre_completo = %s,
                email           = %s,
                rol_id          = %s
            WHERE id = %s
        """, (nombre_usuario, nombre_completo, email, rol_id, user_id))
 
        conn.commit()
        cursor.close()
        conn.close()
 
        flash('Usuario actualizado correctamente', 'success')
        return redirect(url_for('usuarios'))
 
    # GET → cargar datos del usuario
    cursor.execute("""
        SELECT u.*, r.nombre AS rol_nombre
        FROM usuarios u JOIN roles r ON u.rol_id = r.id
        WHERE u.id = %s
    """, (user_id,))
    usuario = cursor.fetchone()
 
    if not usuario:
        flash('Usuario no encontrado', 'error')
        return redirect(url_for('usuarios'))
 
    cursor.execute("SELECT id, nombre FROM roles ORDER BY nombre")
    roles = cursor.fetchall()
    cursor.close()
    conn.close()
 
    return render_template('editar_usuario.html',
                           usuario=usuario,
                           roles=roles,
                           nombre=session['user_name'],
                           rol=session['user_rol'])
 
 
# ─── CAMBIAR CONTRASEÑA ───────────────────────────────────────────────────────
@app.route('/usuarios/password/<int:user_id>', methods=['POST'])
def cambiar_password(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
 
    if not verificar_rol(ROLES_ADMIN):
        flash('No tienes permiso para realizar esta acción', 'error')
        return redirect(url_for('dashboard'))
 
    password      = request.form['password']
    password_conf = request.form['password_conf']
 
    if password != password_conf:
        flash('Las contraseñas no coinciden', 'error')
        return redirect(url_for('editar_usuario', user_id=user_id))
 
    if len(password) < 6:
        flash('La contraseña debe tener al menos 6 caracteres', 'error')
        return redirect(url_for('editar_usuario', user_id=user_id))
 
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
 
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET contrasena_hash = %s WHERE id = %s",
                   (password_hash, user_id))
    conn.commit()
    cursor.close()
    conn.close()
 
    flash('Contraseña actualizada correctamente', 'success')
    return redirect(url_for('editar_usuario', user_id=user_id))
 
 
# ─── ACTIVAR / DESACTIVAR USUARIO ────────────────────────────────────────────
@app.route('/usuarios/toggle/<int:user_id>', methods=['POST'])
def toggle_usuario(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
 
    if not verificar_rol(ROLES_ADMIN):
        flash('No tienes permiso para realizar esta acción', 'error')
        return redirect(url_for('dashboard'))
 
    # No permitir desactivarse a sí mismo
    if user_id == session['user_id']:
        flash('No puedes desactivar tu propia cuenta', 'error')
        return redirect(url_for('usuarios'))
 
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
 
    cursor.execute("SELECT activo, nombre_completo FROM usuarios WHERE id = %s", (user_id,))
    usuario = cursor.fetchone()
 
    if not usuario:
        flash('Usuario no encontrado', 'error')
        return redirect(url_for('usuarios'))
 
    nuevo_estado = 0 if int(usuario['activo']) == 1 else 1
    accion = 'desactivado' if nuevo_estado == 0 else 'activado'
 
    cursor.execute("UPDATE usuarios SET activo = %s WHERE id = %s", (nuevo_estado, user_id))
    conn.commit()
    cursor.close()
    conn.close()
 
    flash(f'Usuario "{usuario["nombre_completo"]}" {accion} correctamente', 'success')
    return redirect(url_for('usuarios'))

# ─── HELPER: registrar entrada en bitácora ────────────────────────────────────
def registrar_bitacora(cursor, orden_id, usuario_id, descripcion,
                       estado_anterior=None, estado_nuevo=None):
    """Inserta una entrada en la bitácora. cursor debe estar abierto."""
    cursor.execute("""
        INSERT INTO bitacora_orden
            (orden_id, usuario_id, descripcion, estado_anterior, estado_nuevo)
        VALUES (%s, %s, %s, %s, %s)
    """, (orden_id, usuario_id, descripcion, estado_anterior, estado_nuevo))
 
 
# ─── VER BITÁCORA COMPLETA DE UNA ORDEN (página separada) ────────────────────
@app.route('/ordenes/<int:orden_id>/bitacora')
def bitacora_orden(orden_id):
    if 'user_id' not in session:
        flash('Por favor inicia sesión primero', 'warning')
        return redirect(url_for('login'))
    if not verificar_rol(ROLES_TODOS):
        flash('No tienes permiso para acceder a esta sección', 'error')
        return redirect(url_for('dashboard'))
 
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
 
    # Datos de la orden
    cursor.execute("""
        SELECT os.*, c.nombre_completo AS nombre_cliente,
               e.tipo_equipo, e.marca, e.modelo
        FROM ordenes_servicio os
        JOIN clientes c ON os.cliente_id = c.id
        JOIN equipos  e ON os.equipo_id  = e.id
        WHERE os.id = %s
    """, (orden_id,))
    orden = cursor.fetchone()
 
    if not orden:
        flash('Orden no encontrada', 'error')
        return redirect(url_for('ordenes'))
 
    # Entradas de bitacora
    cursor.execute("""
        SELECT b.*, u.nombre_completo AS usuario_nombre, u.nombre_usuario
        FROM bitacora_orden b
        JOIN usuarios u ON b.usuario_id = u.id
        WHERE b.orden_id = %s
        ORDER BY b.fecha_hora DESC
    """, (orden_id,))
    entradas = cursor.fetchall()
    cursor.close()
    conn.close()
 
    return render_template('bitacora_orden.html',
                           orden=orden,
                           entradas=entradas,
                           puede_agregar=verificar_rol(ROLES_BITACORA),
                           nombre=session['user_name'],
                           rol=session['user_rol'])
 
 
# ─── AGREGAR ENTRADA A BITÁCORA ───────────────────────────────────────────────
@app.route('/ordenes/<int:orden_id>/bitacora/agregar', methods=['POST'])
def agregar_bitacora(orden_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if not verificar_rol(ROLES_BITACORA):
        flash('No tienes permiso para registrar avances', 'error')
        return redirect(url_for('detalle_orden', orden_id=orden_id))
 
    descripcion  = request.form.get('descripcion', '').strip()
    cambiar_estado_bit = request.form.get('cambiar_estado') == '1'
    nuevo_estado = request.form.get('estado_nuevo', '').strip()
 
    if not descripcion:
        flash('La descripción del avance es obligatoria', 'error')
        return redirect(request.referrer or url_for('detalle_orden', orden_id=orden_id))
 
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
 
    # Obtener estado actual de la orden
    cursor.execute("SELECT estado FROM ordenes_servicio WHERE id = %s", (orden_id,))
    orden = cursor.fetchone()
    if not orden:
        flash('Orden no encontrada', 'error')
        cursor.close()
        conn.close()
        return redirect(url_for('ordenes'))
 
    estado_anterior = orden['estado']
    estado_registrado = None
 
    # Cambiar estado si se solicito
    estados_validos = ['recibido', 'diagnosticando', 'esperando_refacciones',
                       'en_reparacion', 'listo', 'entregado']
 
    if cambiar_estado_bit and nuevo_estado in estados_validos and nuevo_estado != estado_anterior:
        cursor.execute("UPDATE ordenes_servicio SET estado = %s WHERE id = %s",
                       (nuevo_estado, orden_id))
        estado_registrado = nuevo_estado
 
    # Registrar en bitacora
    registrar_bitacora(
        cursor, orden_id, session['user_id'],
        descripcion,
        estado_anterior if estado_registrado else None,
        estado_registrado
    )
 
    conn.commit()
    cursor.close()
    conn.close()
 
    flash('Avance registrado correctamente', 'success')
 
    # Redirigir a donde vino (detalle o bitácora)
    origen = request.form.get('origen', 'detalle')
    if origen == 'bitacora':
        return redirect(url_for('bitacora_orden', orden_id=orden_id))
    return redirect(url_for('detalle_orden', orden_id=orden_id))
 
 
# ─── ELIMINAR ENTRADA DE BITÁCORA (solo admin) ───────────────────────────────
@app.route('/bitacora/eliminar/<int:entrada_id>', methods=['POST'])
def eliminar_bitacora(entrada_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if not verificar_rol(ROLES_ADMIN):
        flash('No tienes permiso para eliminar entradas', 'error')
        return redirect(url_for('ordenes'))
 
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
 
    cursor.execute("SELECT orden_id FROM bitacora_orden WHERE id = %s", (entrada_id,))
    entrada = cursor.fetchone()
 
    if not entrada:
        flash('Entrada no encontrada', 'error')
        cursor.close()
        conn.close()
        return redirect(url_for('ordenes'))
 
    orden_id = entrada['orden_id']
    cursor.execute("DELETE FROM bitacora_orden WHERE id = %s", (entrada_id,))
    conn.commit()
    cursor.close()
    conn.close()
 
    flash('Entrada eliminada de la bitácora', 'success')
    return redirect(url_for('bitacora_orden', orden_id=orden_id))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
