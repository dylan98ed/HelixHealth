# ================================================================
# Auditoria_utiles.py
# FUNCIONES HELPER PARA REGISTRAR AUDITORÍA - OpenHIS-UNLaM
# ================================================================
#
# Este módulo provee funciones que los demás módulos pueden usar
# para registrar acciones en la tabla Auditoria.
#
# USO:
#   from Auditoria_utiles import auditar_alta, auditar_baja
#   auditar_alta("Pacientes", 5, "Paciente Juan Pérez creado", datos)
#
# TIPOS DE ACCIÓN:
#   A = Alta, M = Modificación, B = Baja, R = Reactivación
#   L = Login, X = Logout, E = Exportación, I = Importación, C = Conflicto
# ================================================================

import sqlite3
import os
import json
from datetime import datetime

# Ruta a la base de datos (relativa a la carpeta principal)
RUTA_BD = 'BD/Salud.db'

# Ruta al archivo de sesión (guarda el usuario actual)
RUTA_SESION = '.sesion'


# ================================================================
# TIPOS DE ACCIÓN
# ================================================================

class TipoAccion:
    """Constantes para los tipos de acción"""
    ALTA = 'A'
    MODIFICACION = 'M'
    BAJA = 'B'
    REACTIVACION = 'R'
    LOGIN = 'L'
    LOGOUT = 'X'
    EXPORTACION = 'E'
    IMPORTACION = 'I'
    CONFLICTO = 'C'

    @staticmethod
    def descripcion(tipo):
        return {
            'A': 'Alta',
            'M': 'Modificación',
            'B': 'Baja',
            'R': 'Reactivación',
            'L': 'Inicio de sesión',
            'X': 'Cierre de sesión',
            'E': 'Exportación',
            'I': 'Importación',
            'C': 'Conflicto'
        }.get(tipo, 'Desconocida')


# ================================================================
# GESTIÓN DE SESIÓN (usuario actual)
# ================================================================

def guardar_sesion(usuario_id, usuario_nombre):
    """
    Guarda el usuario actual en un archivo .sesion.
    Se llama desde el menú principal después del login.
    """
    try:
        with open(RUTA_SESION, 'w', encoding='utf-8') as f:
            f.write(f"{usuario_id}|{usuario_nombre}")
        return True
    except Exception as e:
        print(f"[ERROR] No se pudo guardar la sesión: {e}")
        return False


def limpiar_sesion():
    """Elimina el archivo de sesión (logout)"""
    try:
        if os.path.exists(RUTA_SESION):
            os.remove(RUTA_SESION)
        return True
    except Exception:
        return False


def obtener_usuario_actual():
    """
    Lee el usuario actual desde el archivo .sesion.
    Retorna: (usuario_id, usuario_nombre) o (0, 'Desconocido')
    """
    try:
        if os.path.exists(RUTA_SESION):
            with open(RUTA_SESION, 'r', encoding='utf-8') as f:
                contenido = f.read().strip()
                partes = contenido.split('|')
                if len(partes) >= 2:
                    return int(partes[0]), partes[1]
    except Exception:
        pass
    return 0, 'Desconocido'


# ================================================================
# CONEXIÓN A BASE DE DATOS
# ================================================================

def conectar_bd():
    """Conecta a la base de datos de auditoría"""
    return sqlite3.connect(RUTA_BD)


# ================================================================
# FUNCIÓN GENÉRICA DE REGISTRO
# ================================================================

def registrar_auditoria(
    usuario_id,
    usuario_nombre,
    tabla,
    registro_id,
    tipo,
    descripcion="",
    datos_anteriores=None,
    datos_nuevos=None,
    origen_sistema=None,
    origen_id_externo=None,
    payload_referencia=None
):
    """
    Registra una acción en la tabla de auditoría.

    Parámetros:
        usuario_id (int): ID del usuario que hace la acción
        usuario_nombre (str): Nombre del usuario
        tabla (str): Nombre de la tabla afectada
        registro_id (int): ID del registro afectado
        tipo (str): Tipo de acción ('A', 'M', 'B', 'R', 'L', 'X', 'E', 'I', 'C')
        descripcion (str): Descripción legible
        datos_anteriores (dict): Opcional, datos antes del cambio
        datos_nuevos (dict): Opcional, datos después del cambio
        origen_sistema (str): Para FHIR, hospital origen/destino
        origen_id_externo (str): Para FHIR, ID externo
        payload_referencia (str): Para FHIR, ruta al archivo XML/JSON

    Retorna:
        (True, id_auditoria) si tuvo éxito
        (False, mensaje_error) si falló
    """
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()

        datos_ant_json = json.dumps(datos_anteriores, ensure_ascii=False, default=str) if datos_anteriores else None
        datos_nuevos_json = json.dumps(datos_nuevos, ensure_ascii=False, default=str) if datos_nuevos else None

        cursor.execute("""
            INSERT INTO Auditoria 
            (usuario_id, usuario_nombre, tabla_afectada, registro_id, 
             tipo_accion, descripcion, datos_anteriores, datos_nuevos,
             origen_sistema, origen_id_externo, payload_referencia)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            usuario_id,
            usuario_nombre,
            tabla,
            registro_id,
            tipo,
            descripcion,
            datos_ant_json,
            datos_nuevos_json,
            origen_sistema,
            origen_id_externo,
            payload_referencia
        ))

        conexion.commit()
        nuevo_id = cursor.lastrowid
        conexion.close()

        return True, nuevo_id

    except Exception as e:
        print(f"[ERROR] Error al registrar auditoría: {e}")
        return False, f"Error al registrar auditoría: {e}"


# ================================================================
# FUNCIONES DE CONVENIENCIA (usan el usuario actual automáticamente)
# ================================================================

def auditar_alta(tabla, registro_id, descripcion="", datos=None):
    """Registra un ALTA usando el usuario actual"""
    uid, unombre = obtener_usuario_actual()
    return registrar_auditoria(
        usuario_id=uid, usuario_nombre=unombre,
        tabla=tabla, registro_id=registro_id,
        tipo=TipoAccion.ALTA,
        descripcion=descripcion or f"Alta en {tabla}",
        datos_nuevos=datos
    )


def auditar_modificacion(tabla, registro_id, descripcion="", datos_ant=None, datos_nuevos=None):
    """Registra una MODIFICACIÓN usando el usuario actual"""
    uid, unombre = obtener_usuario_actual()
    return registrar_auditoria(
        usuario_id=uid, usuario_nombre=unombre,
        tabla=tabla, registro_id=registro_id,
        tipo=TipoAccion.MODIFICACION,
        descripcion=descripcion or f"Modificación en {tabla}",
        datos_anteriores=datos_ant,
        datos_nuevos=datos_nuevos
    )


def auditar_baja(tabla, registro_id, descripcion="", datos=None):
    """Registra una BAJA usando el usuario actual"""
    uid, unombre = obtener_usuario_actual()
    return registrar_auditoria(
        usuario_id=uid, usuario_nombre=unombre,
        tabla=tabla, registro_id=registro_id,
        tipo=TipoAccion.BAJA,
        descripcion=descripcion or f"Baja en {tabla}",
        datos_anteriores=datos
    )


def auditar_reactivacion(tabla, registro_id, descripcion="", datos=None):
    """Registra una REACTIVACIÓN usando el usuario actual"""
    uid, unombre = obtener_usuario_actual()
    return registrar_auditoria(
        usuario_id=uid, usuario_nombre=unombre,
        tabla=tabla, registro_id=registro_id,
        tipo=TipoAccion.REACTIVACION,
        descripcion=descripcion or f"Reactivación en {tabla}",
        datos_nuevos=datos
    )


def auditar_login(usuario_id, usuario_nombre, usuario_login=""):
    """Registra un LOGIN"""
    return registrar_auditoria(
        usuario_id=usuario_id, usuario_nombre=usuario_nombre,
        tabla="Sistema", registro_id=usuario_id,
        tipo=TipoAccion.LOGIN,
        descripcion=f"Inicio de sesión: {usuario_login or usuario_nombre}"
    )


def auditar_logout(usuario_id, usuario_nombre, usuario_login=""):
    """Registra un LOGOUT"""
    return registrar_auditoria(
        usuario_id=usuario_id, usuario_nombre=usuario_nombre,
        tabla="Sistema", registro_id=usuario_id,
        tipo=TipoAccion.LOGOUT,
        descripcion=f"Cierre de sesión: {usuario_login or usuario_nombre}"
    )


# ================================================================
# FUNCIONES DE EXPORTACIÓN / IMPORTACIÓN (para FHIR)
# ================================================================

def auditar_exportacion(tabla, registro_id, descripcion="", destino="", payload_referencia="", datos=None):
    """Registra una EXPORTACIÓN de datos"""
    uid, unombre = obtener_usuario_actual()
    return registrar_auditoria(
        usuario_id=uid, usuario_nombre=unombre,
        tabla=tabla, registro_id=registro_id,
        tipo=TipoAccion.EXPORTACION,
        descripcion=descripcion or f"Exportación de {tabla}",
        datos_nuevos=datos,
        origen_sistema=destino,
        payload_referencia=payload_referencia
    )


def auditar_importacion(tabla, registro_id, descripcion="", origen="", id_externo="", payload_referencia="", datos=None):
    """Registra una IMPORTACIÓN de datos"""
    uid, unombre = obtener_usuario_actual()
    return registrar_auditoria(
        usuario_id=uid, usuario_nombre=unombre,
        tabla=tabla, registro_id=registro_id,
        tipo=TipoAccion.IMPORTACION,
        descripcion=descripcion or f"Importación de {tabla}",
        datos_nuevos=datos,
        origen_sistema=origen,
        origen_id_externo=id_externo,
        payload_referencia=payload_referencia
    )


def auditar_conflicto(tabla, registro_id, descripcion="", origen="", id_externo="", payload_referencia="", datos_ant=None, datos_nuevos=None):
    """Registra un CONFLICTO durante importación"""
    uid, unombre = obtener_usuario_actual()
    return registrar_auditoria(
        usuario_id=uid, usuario_nombre=unombre,
        tabla=tabla, registro_id=registro_id,
        tipo=TipoAccion.CONFLICTO,
        descripcion=descripcion or f"Conflicto en {tabla}",
        datos_anteriores=datos_ant,
        datos_nuevos=datos_nuevos,
        origen_sistema=origen,
        origen_id_externo=id_externo,
        payload_referencia=payload_referencia
    )


# ================================================================
# CONSULTAS (para visor de auditoría futuro)
# ================================================================

def listar_auditoria(limite=100, tabla=None, usuario_id=None, tipo=None, origen=None):
    """Lista registros de auditoría con filtros opcionales"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()

        where = []
        params = []

        if tabla:
            where.append("tabla_afectada = ?")
            params.append(tabla)
        if usuario_id:
            where.append("usuario_id = ?")
            params.append(usuario_id)
        if tipo:
            where.append("tipo_accion = ?")
            params.append(tipo)
        if origen:
            where.append("origen_sistema = ?")
            params.append(origen)

        where_sql = "WHERE " + " AND ".join(where) if where else ""
        params.append(limite)

        cursor.execute(f"""
            SELECT 
                id, fecha_hora, usuario_nombre, tabla_afectada,
                registro_id, tipo_accion, descripcion,
                origen_sistema, origen_id_externo, payload_referencia
            FROM Auditoria
            {where_sql}
            ORDER BY fecha_hora DESC
            LIMIT ?
        """, params)

        resultados = cursor.fetchall()
        conexion.close()
        return resultados
    except Exception as e:
        print(f"[ERROR] {e}")
        return []


def contar_auditoria():
    """Cuenta total de registros en auditoría"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("SELECT COUNT(*) FROM Auditoria")
        total = cursor.fetchone()[0]
        conexion.close()
        return total
    except Exception:
        return 0


# ================================================================
# TEST (solo si se ejecuta directamente)
# ================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("🧪 TEST DEL MÓDULO DE AUDITORÍA")
    print("=" * 70)

    print(f"\n📊 Registros en auditoría: {contar_auditoria()}")

    print("\n📋 Tipos de acción disponibles:")
    for tipo in ['A', 'M', 'B', 'R', 'L', 'X', 'E', 'I', 'C']:
        print(f"   {tipo} = {TipoAccion.descripcion(tipo)}")

    print("\n📌 Usuario actual en sesión:")
    uid, unombre = obtener_usuario_actual()
    print(f"   ID: {uid}")
    print(f"   Nombre: {unombre}")

    print("\n✅ Módulo listo para usar")
    print("=" * 70)
