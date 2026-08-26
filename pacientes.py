# Pacientes.py
# Módulo de Gestión de Pacientes - OpenHIS-UNLaM
# Sprint 1: HU-01 (Alta) y HU-02 (Búsqueda)
import sqlite3
from datetime import datetime
# --- CONEXIÓN A LA BASE DE DATOS ---
def conectar_bd():
    """Establece conexión con la base de datos Salud.db"""
    return sqlite3.connect('BD/Salud.db')

# --- HU-01: REGISTRAR UN NUEVO PACIENTE (CREATE) ---
def registrar_paciente():
    print("\n" + "="*50)
    print(" ALTA DE NUEVO PACIENTE")
    print("="*50)

    # Solicitar datos al usuario (administrativo)
    dni = input("DNI: ")
    nombre = input("Nombre(s): ")
    apellido = input("Apellido(s): ")
    fecha_nac = input("Fecha de nacimiento (YYYY-MM-DD): ")
    sexo = input("Sexo (M/F): ")
    telefono = input("Teléfono: ")
    email = input("Email: ")
    domicilio = input("Domicilio: ")
    obra_social = input("Obra Social: ")

    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()

        # La validación de DNI duplicado la hace la BD gracias a
        "UNIQUE"
        cursor.execute("""
        INSERT INTO Pacientes
        (dni, nombre, apellido, fecha_nacimiento, sexo, telefono,
        email, domicilio, obra_social)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (dni, nombre, apellido, fecha_nac, sexo, telefono, email,
        domicilio, obra_social))

        conexion.commit()

        # Obtener el ID del nuevo registro
        nuevo_id = cursor.lastrowid
        print("\n✅ ¡PACIENTE REGISTRADO CON ÉXITO!")
        print(f" Número de Historia Clínica: {nuevo_id}")

        conexion.close()

    except sqlite3.IntegrityError:
        print("\n❌ ERROR: Ya existe un paciente con ese DNI.")
        print(" Verifique que el DNI no esté duplicado.")
    except Exception as e:
        print(f"\n❌ ERROR inesperado: {e}")
        
# --- HU-02: BUSCAR UN PACIENTE POR DNI (READ) ---
def buscar_paciente():
    print("\n" + "="*50)
    print(" BÚSQUEDA DE PACIENTE")
    print("="*50)

    dni = input("Ingrese el DNI del paciente a buscar: ")

    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()

        cursor.execute("SELECT * FROM Pacientes WHERE dni = ?",
        (dni,))
        paciente = cursor.fetchone()

        if paciente:
            print("\n✅ PACIENTE ENCONTRADO:")
            print("-" * 40)
            print(f"ID (HC): {paciente[0]}")
            print(f"DNI: {paciente[1]}")
            print(f"Nombre: {paciente[2]} {paciente[3]}")
            print(f"Fecha Nac.: {paciente[4]}")
            print(f"Sexo: {paciente[5]}")
            print(f"Teléfono: {paciente[6]}")
            print(f"Email: {paciente[7]}")
            print(f"Domicilio: {paciente[8]}")
            print(f"Obra Social: {paciente[9]}")
            print(f"Registro: {paciente[10]}")
            print("-" * 40)
        else:
            print("\n❌ Paciente no encontrado.")

        conexion.close()

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        
# --- MENÚ PRINCIPAL ---
def menu():
    while True:
        print("\n" + "="*50)
        print(" OPENHIS-UNLaM - GESTIÓN DE PACIENTES")
        print("="*50)
        print("1. Registrar nuevo paciente (HU-01)")
        print("2. Buscar paciente por DNI (HU-02)")
        print("3. Salir")
        print("-"*50)

        opcion = input("Seleccione una opción: ")

        if opcion == "1":
            registrar_paciente()
        elif opcion == "2":
            buscar_paciente()
        elif opcion == "3":
            print("\n👋 ¡Hasta luego!")
            break
        else:
            print("\n❌ Opción inválida. Intente nuevamente.")
    
# --- PUNTO DE ENTRADA ---
if __name__ == "__main__":
    print("\n🏥 HOSPITAL UNIVERSITARIO SAN JUSTO")
    print(" Sistema de Información Hospitalaria")
    print(" OpenHIS-UNLaM - Versión 0.1 (Sprint 1)")
    menu()
