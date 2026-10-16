-- Generado automáticamente por base_datos.py. No hace falta editarlo.

CREATE TABLE duenos (
	id INTEGER NOT NULL, 
	nombre VARCHAR(100) NOT NULL, 
	email VARCHAR(100), 
	pin_hash VARCHAR(200), 
	PRIMARY KEY (id)
);

CREATE TABLE comercios (
	id INTEGER NOT NULL, 
	dueno_id INTEGER NOT NULL, 
	nombre VARCHAR(100) NOT NULL, 
	rubro VARCHAR(30) NOT NULL, 
	direccion VARCHAR(150), 
	usa_ticket BOOLEAN NOT NULL, 
	resumen_semanal BOOLEAN DEFAULT 0 NOT NULL, 
	permisos_empleado VARCHAR(200) DEFAULT 'panel_del_dia,stock' NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(dueno_id) REFERENCES duenos (id)
);

CREATE TABLE cajas (
	id INTEGER NOT NULL, 
	comercio_id INTEGER NOT NULL, 
	responsable VARCHAR(100) NOT NULL, 
	abierta DATETIME NOT NULL, 
	monto_inicial FLOAT NOT NULL, 
	cerrada DATETIME, 
	efectivo_esperado FLOAT, 
	efectivo_contado FLOAT, 
	nota VARCHAR(200), 
	PRIMARY KEY (id), 
	FOREIGN KEY(comercio_id) REFERENCES comercios (id)
);

CREATE TABLE gastos (
	id INTEGER NOT NULL, 
	comercio_id INTEGER NOT NULL, 
	fecha DATE NOT NULL, 
	categoria VARCHAR(50) NOT NULL, 
	descripcion VARCHAR(150), 
	monto FLOAT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(comercio_id) REFERENCES comercios (id)
);

CREATE TABLE proveedores (
	id INTEGER NOT NULL, 
	comercio_id INTEGER NOT NULL, 
	nombre VARCHAR(100) NOT NULL, 
	telefono VARCHAR(30), 
	PRIMARY KEY (id), 
	FOREIGN KEY(comercio_id) REFERENCES comercios (id)
);

CREATE TABLE compras (
	id INTEGER NOT NULL, 
	comercio_id INTEGER NOT NULL, 
	proveedor_id INTEGER, 
	fecha DATETIME NOT NULL, 
	total FLOAT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(comercio_id) REFERENCES comercios (id), 
	FOREIGN KEY(proveedor_id) REFERENCES proveedores (id)
);

CREATE TABLE productos (
	id INTEGER NOT NULL, 
	comercio_id INTEGER NOT NULL, 
	proveedor_id INTEGER, 
	codigo VARCHAR(20) NOT NULL, 
	nombre VARCHAR(100) NOT NULL, 
	categoria VARCHAR(50), 
	precio_costo FLOAT NOT NULL, 
	precio_venta FLOAT NOT NULL, 
	stock INTEGER NOT NULL, 
	stock_minimo INTEGER NOT NULL, 
	activo BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(comercio_id) REFERENCES comercios (id), 
	FOREIGN KEY(proveedor_id) REFERENCES proveedores (id)
);

CREATE TABLE ventas (
	id INTEGER NOT NULL, 
	comercio_id INTEGER NOT NULL, 
	caja_id INTEGER, 
	fecha DATETIME NOT NULL, 
	medio_pago VARCHAR(20) NOT NULL, 
	total FLOAT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(comercio_id) REFERENCES comercios (id), 
	FOREIGN KEY(caja_id) REFERENCES cajas (id)
);

CREATE TABLE compras_detalle (
	id INTEGER NOT NULL, 
	compra_id INTEGER NOT NULL, 
	producto_id INTEGER NOT NULL, 
	cantidad INTEGER NOT NULL, 
	costo_unitario FLOAT NOT NULL, 
	subtotal FLOAT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(compra_id) REFERENCES compras (id), 
	FOREIGN KEY(producto_id) REFERENCES productos (id)
);

CREATE TABLE tickets (
	id INTEGER NOT NULL, 
	venta_id INTEGER NOT NULL, 
	numero VARCHAR(20) NOT NULL, 
	fecha_emision DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (venta_id), 
	FOREIGN KEY(venta_id) REFERENCES ventas (id)
);

CREATE TABLE ventas_detalle (
	id INTEGER NOT NULL, 
	venta_id INTEGER NOT NULL, 
	producto_id INTEGER NOT NULL, 
	cantidad INTEGER NOT NULL, 
	precio_unitario FLOAT NOT NULL, 
	costo_unitario FLOAT NOT NULL, 
	subtotal FLOAT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(venta_id) REFERENCES ventas (id), 
	FOREIGN KEY(producto_id) REFERENCES productos (id)
);
