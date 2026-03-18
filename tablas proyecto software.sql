CREATE DATABASE taller_reparaciones;

use prueba1;

CREATE TABLE roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre_usuario VARCHAR(50) NOT NULL UNIQUE,
    contrasena_hash VARCHAR(255) NOT NULL,
    nombre_completo VARCHAR(100),
    email VARCHAR(100),
    rol_id INT NOT NULL,
    FOREIGN KEY (rol_id) REFERENCES roles(id)
);

CREATE TABLE clientes (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    nombre_completo VARCHAR(100) NOT NULL,
    telefono        VARCHAR(20),
    email           VARCHAR(100),
    direccion       VARCHAR(255),
    rfc             VARCHAR(20),                        -- útil para facturas
    tipo_cliente    ENUM('persona_fisica', 'empresa') DEFAULT 'persona_fisica',
    notas           TEXT,                               -- observaciones internas
    fecha_registro  DATETIME DEFAULT CURRENT_TIMESTAMP,
    activo          TINYINT(1) DEFAULT 1                -- 1 = activo, 0 = eliminado (baja lógica)
);

CREATE TABLE equipos (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    cliente_id      INT NOT NULL,
    tipo_equipo     VARCHAR(60) NOT NULL,               -- ej. Motosierra, Desbrozadora, Motobomba
    marca           VARCHAR(60) NOT NULL DEFAULT 'STIHL',
    modelo          VARCHAR(80),                        -- ej. MS 250, FS 94, MB 235
    numero_serie    VARCHAR(100),                       -- número de serie físico del equipo
    anio            YEAR,                               -- año de fabricación/compra
    color           VARCHAR(40),
    descripcion     TEXT,                               -- detalles adicionales o accesorios
    fecha_registro  DATETIME DEFAULT CURRENT_TIMESTAMP,
    activo          TINYINT(1) DEFAULT 1,

    FOREIGN KEY (cliente_id) REFERENCES clientes(id)
);

CREATE TABLE ordenes_servicio (
    id                    INT AUTO_INCREMENT PRIMARY KEY,
    folio                 VARCHAR(20) NOT NULL UNIQUE,         -- ej. OS-1025
    cliente_id            INT NOT NULL,
    equipo_id             INT NOT NULL,
    tecnico_id            INT,                                 -- puede asignarse despues
    descripcion_problema  TEXT NOT NULL,                       -- lo que reporta el cliente
    estado                ENUM(
                            'recibido',
                            'diagnosticando',
                            'esperando_refacciones',
                            'en_reparacion',
                            'listo',
                            'entregado'
                          ) DEFAULT 'recibido',
    prioridad             ENUM('normal', 'urgente') DEFAULT 'normal',
    fecha_ingreso         DATETIME DEFAULT CURRENT_TIMESTAMP,
    fecha_estimada        DATE,                                -- entrega estimada al cliente
    fecha_entrega_real    DATETIME,                            -- cuando se entregó fisicamente
    costo_estimado        DECIMAL(10,2),
    costo_final           DECIMAL(10,2),
    observaciones         TEXT,                               -- notas internas del taller

    FOREIGN KEY (cliente_id) REFERENCES clientes(id),
    FOREIGN KEY (equipo_id)  REFERENCES equipos(id),
    FOREIGN KEY (tecnico_id) REFERENCES usuarios(id)
);

DELIMITER $$
CREATE TRIGGER generar_folio
BEFORE INSERT ON ordenes_servicio
FOR EACH ROW
BEGIN
    DECLARE ultimo INT;
    SELECT COUNT(*) INTO ultimo FROM ordenes_servicio;
    SET NEW.folio = CONCAT('OS-', LPAD(ultimo + 1, 4, '0'));
END$$
DELIMITER ;

CREATE TABLE refacciones (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    codigo            VARCHAR(30) NOT NULL UNIQUE,          -- clave interna ej. REF-0001
    nombre            VARCHAR(120) NOT NULL,
    descripcion       TEXT,
    categoria         VARCHAR(60),                          -- Carburador, Filtro, Cadena, etc.
    marca_compatible  VARCHAR(100),                         -- ej. STIHL MS 250, universal
    unidad            ENUM('pieza','litro','metro','par','kit','caja') DEFAULT 'pieza',
    stock_actual      INT NOT NULL DEFAULT 0,
    stock_minimo      INT NOT NULL DEFAULT 2,               -- alerta si stock <= este valor
    precio_compra     DECIMAL(10,2),
    precio_venta      DECIMAL(10,2),
    ubicacion         VARCHAR(60),                          -- ej. Estante A-3
    activo            TINYINT(1) DEFAULT 1,
    fecha_registro    DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Trigger para generar código automático REF-0001, REF-0002...
DELIMITER $$
CREATE TRIGGER generar_codigo_refaccion
BEFORE INSERT ON refacciones
FOR EACH ROW
BEGIN
    DECLARE ultimo INT;
    SELECT COUNT(*) INTO ultimo FROM refacciones;
    SET NEW.codigo = CONCAT('REF-', LPAD(ultimo + 1, 4, '0'));
END$$
DELIMITER ;

CREATE TABLE refacciones_orden (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    orden_id        INT NOT NULL,
    refaccion_id    INT NOT NULL,
    cantidad        INT NOT NULL DEFAULT 1,
    precio_unitario DECIMAL(10,2) NOT NULL,       -- precio al momento de usarse
    subtotal        DECIMAL(10,2) GENERATED ALWAYS AS (cantidad * precio_unitario) STORED,
    notas           VARCHAR(255),
    fecha_registro  DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (orden_id)     REFERENCES ordenes_servicio(id),
    FOREIGN KEY (refaccion_id) REFERENCES refacciones(id)
);

-- Trigger: al agregar refacción a orden → descontar stock automáticamente
DELIMITER $$
CREATE TRIGGER descontar_stock_al_agregar
AFTER INSERT ON refacciones_orden
FOR EACH ROW
BEGIN
    UPDATE refacciones
    SET stock_actual = stock_actual - NEW.cantidad
    WHERE id = NEW.refaccion_id;
END$$

-- Trigger: al eliminar refacción de orden → devolver stock
CREATE TRIGGER devolver_stock_al_eliminar
AFTER DELETE ON refacciones_orden
FOR EACH ROW
BEGIN
    UPDATE refacciones
    SET stock_actual = stock_actual + OLD.cantidad
    WHERE id = OLD.refaccion_id;
END$$

DELIMITER ;

CREATE TABLE cotizaciones (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    folio             VARCHAR(20) NOT NULL UNIQUE,      -- ej. COT-0001
    orden_id          INT,                              -- opcional: vinculada a una orden
    cliente_id        INT NOT NULL,
    creado_por        INT NOT NULL,                     -- usuario que la generó
    estado            ENUM('borrador','enviada','aprobada','rechazada','vencida') DEFAULT 'borrador',
    fecha_emision     DATETIME DEFAULT CURRENT_TIMESTAMP,
    fecha_vencimiento DATE,
    subtotal          DECIMAL(10,2) DEFAULT 0,
    descuento         DECIMAL(10,2) DEFAULT 0,
    total             DECIMAL(10,2) DEFAULT 0,
    notas             TEXT,                             -- visible al cliente
    notas_internas    TEXT,

    FOREIGN KEY (orden_id)   REFERENCES ordenes_servicio(id),
    FOREIGN KEY (cliente_id) REFERENCES clientes(id),
    FOREIGN KEY (creado_por) REFERENCES usuarios(id)
);

-- Items de cada cotización (conceptos / líneas)
CREATE TABLE cotizacion_items (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    cotizacion_id   INT NOT NULL,
    descripcion     VARCHAR(255) NOT NULL,
    cantidad        DECIMAL(10,2) NOT NULL DEFAULT 1,
    precio_unitario DECIMAL(10,2) NOT NULL,
    subtotal        DECIMAL(10,2) GENERATED ALWAYS AS (cantidad * precio_unitario) STORED,

    FOREIGN KEY (cotizacion_id) REFERENCES cotizaciones(id) ON DELETE CASCADE
);

-- Trigger folio automático COT-0001, COT-0002...
DELIMITER $$
CREATE TRIGGER generar_folio_cotizacion
BEFORE INSERT ON cotizaciones
FOR EACH ROW
BEGIN
    DECLARE ultimo INT;
    SELECT COUNT(*) INTO ultimo FROM cotizaciones;
    SET NEW.folio = CONCAT('COT-', LPAD(ultimo + 1, 4, '0'));
END$$
DELIMITER ;

ALTER TABLE usuarios
    ADD COLUMN activo TINYINT(1) NOT NULL DEFAULT 1;

CREATE TABLE bitacora_orden (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    orden_id        INT NOT NULL,
    usuario_id      INT NOT NULL,
    descripcion     TEXT NOT NULL,
    estado_anterior VARCHAR(50),              -- estado antes del cambio (NULL si no cambió)
    estado_nuevo    VARCHAR(50),              -- estado después del cambio (NULL si no cambió)
    fecha_hora      DATETIME DEFAULT CURRENT_TIMESTAMP,
 
    FOREIGN KEY (orden_id)   REFERENCES ordenes_servicio(id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);