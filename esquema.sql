-- Generado automáticamente por base_datos.py. No hace falta editarlo.

CREATE TABLE duenos (
	id INTEGER NOT NULL, 
	nombre VARCHAR(100) NOT NULL, 
	email VARCHAR(100), 
	pin_hash VARCHAR(200), 
	tema VARCHAR(10) DEFAULT 'claro' NOT NULL, 
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
	permisos_empleado VARCHAR(200) DEFAULT 'panel_del_dia,stock,compras,vencimientos' NOT NULL, 
	hora_apertura VARCHAR(5), 
	hora_cierre VARCHAR(5), 
	turnos_config TEXT, 
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

CREATE TABLE configuracion_gimnasio (
	id INTEGER NOT NULL, 
	comercio_id INTEGER NOT NULL, 
	horas_cancelacion INTEGER DEFAULT '2' NOT NULL, 
	clases_sobrantes VARCHAR(20) DEFAULT 'vencen' NOT NULL, 
	vencimiento VARCHAR(20) DEFAULT 'dias_plan' NOT NULL, 
	dias_aviso INTEGER DEFAULT '7' NOT NULL, 
	reservas_web BOOLEAN DEFAULT 0 NOT NULL, 
	codigo_web VARCHAR(20), 
	PRIMARY KEY (id), 
	UNIQUE (comercio_id), 
	FOREIGN KEY(comercio_id) REFERENCES comercios (id), 
	UNIQUE (codigo_web)
);

CREATE TABLE configuracion_telegram (
	id INTEGER NOT NULL, 
	comercio_id INTEGER NOT NULL, 
	telegram_chat_id VARCHAR(30), 
	token_vinculacion VARCHAR(40), 
	activo BOOLEAN DEFAULT 1 NOT NULL, 
	eventos VARCHAR(100) DEFAULT 'apertura,cierre,relevo,stock' NOT NULL, 
	conectado DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (comercio_id), 
	FOREIGN KEY(comercio_id) REFERENCES comercios (id)
);

CREATE TABLE disciplinas (
	id INTEGER NOT NULL, 
	comercio_id INTEGER NOT NULL, 
	nombre VARCHAR(100) NOT NULL, 
	activa BOOLEAN DEFAULT 1 NOT NULL, 
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

CREATE TABLE planes (
	id INTEGER NOT NULL, 
	comercio_id INTEGER NOT NULL, 
	nombre VARCHAR(100) NOT NULL, 
	precio FLOAT NOT NULL, 
	duracion_meses INTEGER, 
	duracion_dias INTEGER NOT NULL, 
	cantidad_clases INTEGER, 
	activo BOOLEAN DEFAULT 1 NOT NULL, 
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

CREATE TABLE clases (
	id INTEGER NOT NULL, 
	comercio_id INTEGER NOT NULL, 
	disciplina_id INTEGER NOT NULL, 
	dia_semana VARCHAR(20) NOT NULL, 
	hora_inicio VARCHAR(10) NOT NULL, 
	duracion_minutos INTEGER DEFAULT '60' NOT NULL, 
	profesor VARCHAR(100), 
	cupo_maximo INTEGER NOT NULL, 
	activa BOOLEAN DEFAULT 1 NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(comercio_id) REFERENCES comercios (id), 
	FOREIGN KEY(disciplina_id) REFERENCES disciplinas (id)
);

CREATE TABLE compras (
	id INTEGER NOT NULL, 
	comercio_id INTEGER NOT NULL, 
	proveedor_id INTEGER, 
	fecha DATETIME NOT NULL, 
	total FLOAT NOT NULL, 
	cargada_por VARCHAR(100), 
	PRIMARY KEY (id), 
	FOREIGN KEY(comercio_id) REFERENCES comercios (id), 
	FOREIGN KEY(proveedor_id) REFERENCES proveedores (id)
);

CREATE TABLE planes_disciplinas (
	id INTEGER NOT NULL, 
	comercio_id INTEGER NOT NULL, 
	plan_id INTEGER NOT NULL, 
	disciplina_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT actividad_una_vez_por_plan UNIQUE (plan_id, disciplina_id), 
	FOREIGN KEY(comercio_id) REFERENCES comercios (id), 
	FOREIGN KEY(plan_id) REFERENCES planes (id), 
	FOREIGN KEY(disciplina_id) REFERENCES disciplinas (id)
);

CREATE TABLE productos (
	id INTEGER NOT NULL, 
	comercio_id INTEGER NOT NULL, 
	proveedor_id INTEGER, 
	codigo VARCHAR(20) NOT NULL, 
	codigo_barras VARCHAR(30), 
	nombre VARCHAR(100) NOT NULL, 
	categoria VARCHAR(50), 
	precio_costo FLOAT NOT NULL, 
	precio_venta FLOAT NOT NULL, 
	stock INTEGER NOT NULL, 
	stock_minimo INTEGER NOT NULL, 
	activo BOOLEAN NOT NULL, 
	dias_duracion INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(comercio_id) REFERENCES comercios (id), 
	FOREIGN KEY(proveedor_id) REFERENCES proveedores (id)
);

CREATE TABLE relevos_caja (
	id INTEGER NOT NULL, 
	caja_id INTEGER NOT NULL, 
	comercio_id INTEGER NOT NULL, 
	fecha_hora DATETIME NOT NULL, 
	turno VARCHAR(50), 
	empleado_sale VARCHAR(100) NOT NULL, 
	empleado_entra VARCHAR(100) NOT NULL, 
	efectivo_esperado_turno FLOAT NOT NULL, 
	efectivo_contado FLOAT NOT NULL, 
	diferencia FLOAT NOT NULL, 
	nota VARCHAR(200), 
	PRIMARY KEY (id), 
	FOREIGN KEY(caja_id) REFERENCES cajas (id), 
	FOREIGN KEY(comercio_id) REFERENCES comercios (id)
);

CREATE TABLE socios (
	id INTEGER NOT NULL, 
	comercio_id INTEGER NOT NULL, 
	nombre VARCHAR(100) NOT NULL, 
	dni VARCHAR(20) NOT NULL, 
	telefono VARCHAR(30), 
	email VARCHAR(100), 
	fecha_alta DATETIME NOT NULL, 
	plan_id INTEGER, 
	fecha_vencimiento DATE, 
	clases_restantes INTEGER DEFAULT '0' NOT NULL, 
	estado VARCHAR(20) DEFAULT 'al_dia' NOT NULL, 
	activo BOOLEAN DEFAULT 1 NOT NULL, 
	nota VARCHAR(200), 
	PRIMARY KEY (id), 
	CONSTRAINT socio_unico_por_comercio UNIQUE (comercio_id, dni), 
	FOREIGN KEY(comercio_id) REFERENCES comercios (id), 
	FOREIGN KEY(plan_id) REFERENCES planes (id)
);

CREATE TABLE ventas (
	id INTEGER NOT NULL, 
	comercio_id INTEGER NOT NULL, 
	caja_id INTEGER, 
	fecha DATETIME NOT NULL, 
	medio_pago VARCHAR(20) NOT NULL, 
	total FLOAT NOT NULL, 
	anulada DATETIME, 
	responsable_turno VARCHAR(100), 
	PRIMARY KEY (id), 
	FOREIGN KEY(comercio_id) REFERENCES comercios (id), 
	FOREIGN KEY(caja_id) REFERENCES cajas (id)
);

CREATE TABLE ajustes_caja (
	id INTEGER NOT NULL, 
	caja_id INTEGER NOT NULL, 
	fecha DATETIME NOT NULL, 
	hecho_por VARCHAR(100) NOT NULL, 
	tipo VARCHAR(20) NOT NULL, 
	venta_id INTEGER, 
	monto FLOAT NOT NULL, 
	motivo VARCHAR(200) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(caja_id) REFERENCES cajas (id), 
	FOREIGN KEY(venta_id) REFERENCES ventas (id)
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

CREATE TABLE cuotas_cobradas (
	id INTEGER NOT NULL, 
	comercio_id INTEGER NOT NULL, 
	socio_id INTEGER NOT NULL, 
	plan_id INTEGER NOT NULL, 
	venta_id INTEGER, 
	caja_id INTEGER, 
	relevo_id INTEGER, 
	fecha DATETIME NOT NULL, 
	monto FLOAT NOT NULL, 
	medio_pago VARCHAR(20) NOT NULL, 
	cobrada_por VARCHAR(100), 
	clases_cargadas INTEGER, 
	clases_antes INTEGER, 
	clases_despues INTEGER, 
	vence_antes DATE, 
	vence_nuevo DATE NOT NULL, 
	anulada DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(comercio_id) REFERENCES comercios (id), 
	FOREIGN KEY(socio_id) REFERENCES socios (id), 
	FOREIGN KEY(plan_id) REFERENCES planes (id), 
	UNIQUE (venta_id), 
	FOREIGN KEY(venta_id) REFERENCES ventas (id), 
	FOREIGN KEY(caja_id) REFERENCES cajas (id), 
	FOREIGN KEY(relevo_id) REFERENCES relevos_caja (id)
);

CREATE TABLE lotes (
	id INTEGER NOT NULL, 
	comercio_id INTEGER NOT NULL, 
	producto_id INTEGER NOT NULL, 
	fecha DATETIME NOT NULL, 
	cantidad INTEGER NOT NULL, 
	vence DATE NOT NULL, 
	origen VARCHAR(20) NOT NULL, 
	cargado_por VARCHAR(100), 
	PRIMARY KEY (id), 
	FOREIGN KEY(comercio_id) REFERENCES comercios (id), 
	FOREIGN KEY(producto_id) REFERENCES productos (id)
);

CREATE TABLE mermas (
	id INTEGER NOT NULL, 
	comercio_id INTEGER NOT NULL, 
	producto_id INTEGER NOT NULL, 
	fecha DATETIME NOT NULL, 
	cantidad INTEGER NOT NULL, 
	costo_unitario FLOAT NOT NULL, 
	motivo VARCHAR(100) NOT NULL, 
	hecho_por VARCHAR(100), 
	PRIMARY KEY (id), 
	FOREIGN KEY(comercio_id) REFERENCES comercios (id), 
	FOREIGN KEY(producto_id) REFERENCES productos (id)
);

CREATE TABLE reservas (
	id INTEGER NOT NULL, 
	comercio_id INTEGER NOT NULL, 
	clase_id INTEGER NOT NULL, 
	socio_id INTEGER NOT NULL, 
	fecha_reserva DATE NOT NULL, 
	estado VARCHAR(20) DEFAULT 'reservado' NOT NULL, 
	creada DATETIME NOT NULL, 
	origen VARCHAR(20) DEFAULT 'recepcion' NOT NULL, 
	hecha_por VARCHAR(100), 
	clase_descontada BOOLEAN DEFAULT 0 NOT NULL, 
	cancelada DATETIME, 
	clase_devuelta BOOLEAN DEFAULT 0 NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(comercio_id) REFERENCES comercios (id), 
	FOREIGN KEY(clase_id) REFERENCES clases (id), 
	FOREIGN KEY(socio_id) REFERENCES socios (id)
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

CREATE TABLE asistencias (
	id INTEGER NOT NULL, 
	comercio_id INTEGER NOT NULL, 
	socio_id INTEGER NOT NULL, 
	fecha_hora DATETIME NOT NULL, 
	resultado VARCHAR(20) NOT NULL, 
	motivo VARCHAR(200), 
	reserva_id INTEGER, 
	registrado_por VARCHAR(100), 
	PRIMARY KEY (id), 
	FOREIGN KEY(comercio_id) REFERENCES comercios (id), 
	FOREIGN KEY(socio_id) REFERENCES socios (id), 
	FOREIGN KEY(reserva_id) REFERENCES reservas (id)
);
