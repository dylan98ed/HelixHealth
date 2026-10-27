# ================================================================
# _Pacientes_def_app.pyw
# SPRINT 3 - MÓDULO DE GESTIÓN DE PACIENTES (INDEPENDIENTE)
# CON AUDITORÍA COMPLETA
# ================================================================
#
# FUNCIONALIDADES:
#   ✅ Registrar paciente (CREATE) - HU-01
#   ✅ Buscar paciente por DNI (READ) - HU-02
#   ✅ Modificar datos del paciente (UPDATE)
#   ✅ Baja lógica de paciente (DELETE lógico - activo = 0)
#   ✅ Reactivar paciente (si fue dado de baja)
#   ✅ Ver listado de pacientes activos
#   ✅ Ver listado de pacientes inactivos
#   ✅ AUDITORÍA: Alta, Modificación, Baja, Reactivación
#   ✅ Interfaz gráfica con Tkinter
#
# NOTA IMPORTANTE:
#   Los signos vitales son un módulo INDEPENDIENTE
#   (_Signos_vitales_def_app.pyw)
#
#   El borrado es LÓGICO (activo = 0). Los datos se conservan
#   para auditoría y para evitar eliminar información clínica.
# ================================================================

import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime

# ----------------------------------------------------------------
# IMPORTAR FUNCIONES DE AUDITORÍA
# ----------------------------------------------------------------
from Auditoria_utiles import (
    auditar_alta,
    auditar_modificacion,
    auditar_baja,
    auditar_reactivacion
)


# ================================================================
# CAPA DE ACCESO A DATOS (BACKEND)
# ================================================================

def conectar_bd():
    """Establece conexión con la base de datos Salud.db"""
    return sqlite3.connect('BD/Salud.db')


# -------------------- CRUD DE PACIENTES --------------------

def registrar_paciente(datos):
    """
    HU-01: Registrar nuevo paciente (CREATE)
    """
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        
        cursor.execute("""
            INSERT INTO Pacientes 
            (dni, nombre, apellido, fecha_nacimiento, sexo, 
             telefono, email, domicilio, obra_social, activo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datos['dni'],
            datos['nombre'],
            datos['apellido'],
            datos['fecha_nac'],
            datos['sexo'],
            datos.get('telefono', ''),
            datos.get('email', ''),
            datos.get('domicilio', ''),
            datos.get('obra_social', ''),
            1  # activo
        ))
        
        conexion.commit()
        nuevo_id = cursor.lastrowid
        conexion.close()
        print(f"[DEBUG] Paciente registrado con ID: {nuevo_id}")
        
        # ✅ AUDITORÍA
        auditar_alta(
            tabla="Pacientes",
            registro_id=nuevo_id,
            descripcion=f"Paciente {datos['nombre']} {datos['apellido']} (DNI: {datos['dni']}) creado",
            datos=datos
        )
        
        return True, nuevo_id
        
    except sqlite3.IntegrityError:
        return False, "❌ DNI duplicado. Ya existe un paciente con ese DNI."
    except Exception as e:
        print(f"[ERROR] Error en registrar_paciente: {e}")
        return False, f"❌ Error: {e}"


def buscar_paciente(dni):
    """
    HU-02: Buscar paciente por DNI (READ)
    Busca tanto activos como inactivos para permitir reactivación
    """
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("SELECT * FROM Pacientes WHERE dni = ?", (dni,))
        paciente = cursor.fetchone()
        conexion.close()
        
        if paciente:
            return {
                'id': paciente[0],
                'dni': paciente[1],
                'nombre': paciente[2],
                'apellido': paciente[3],
                'fecha_nac': paciente[4],
                'sexo': paciente[5],
                'telefono': paciente[6] or '',
                'email': paciente[7] or '',
                'domicilio': paciente[8] or '',
                'obra_social': paciente[9] or '',
                'fecha_registro': paciente[10],
                'activo': paciente[11] if len(paciente) > 11 else 1
            }
        return None
        
    except Exception as e:
        print(f"[ERROR] Error en buscar_paciente: {e}")
        return None


def buscar_paciente_por_id(paciente_id):
    """Busca un paciente por su ID"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("SELECT * FROM Pacientes WHERE id = ?", (paciente_id,))
        paciente = cursor.fetchone()
        conexion.close()
        
        if paciente:
            return {
                'id': paciente[0],
                'dni': paciente[1],
                'nombre': paciente[2],
                'apellido': paciente[3],
                'fecha_nac': paciente[4],
                'sexo': paciente[5],
                'telefono': paciente[6] or '',
                'email': paciente[7] or '',
                'domicilio': paciente[8] or '',
                'obra_social': paciente[9] or '',
                'fecha_registro': paciente[10],
                'activo': paciente[11] if len(paciente) > 11 else 1
            }
        return None
    except Exception as e:
        print(f"[ERROR] Error en buscar_paciente_por_id: {e}")
        return None


def listar_pacientes(activos=True):
    """
    Lista pacientes según su estado
    activos=True: solo activos
    activos=False: solo inactivos
    """
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        
        if activos:
            cursor.execute("""
                SELECT id, dni, nombre, apellido, telefono, activo 
                FROM Pacientes 
                WHERE activo = 1
                ORDER BY apellido, nombre
            """)
        else:
            cursor.execute("""
                SELECT id, dni, nombre, apellido, telefono, activo 
                FROM Pacientes 
                WHERE activo = 0
                ORDER BY apellido, nombre
            """)
        
        pacientes = cursor.fetchall()
        conexion.close()
        print(f"[DEBUG] Pacientes {'activos' if activos else 'inactivos'}: {len(pacientes)}")
        return pacientes
        
    except Exception as e:
        print(f"[ERROR] Error en listar_pacientes: {e}")
        return []


def modificar_paciente(paciente_id, datos):
    """Modifica datos de un paciente"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        
        # Obtener datos anteriores para auditoría
        cursor.execute("""
            SELECT telefono, email, domicilio, obra_social 
            FROM Pacientes WHERE id = ?
        """, (paciente_id,))
        anterior = cursor.fetchone()
        
        cursor.execute("""
            UPDATE Pacientes 
            SET telefono = ?, email = ?, domicilio = ?, obra_social = ?
            WHERE id = ?
        """, (
            datos.get('telefono', ''),
            datos.get('email', ''),
            datos.get('domicilio', ''),
            datos.get('obra_social', ''),
            paciente_id
        ))
        
        conexion.commit()
        afectados = cursor.rowcount
        conexion.close()
        
        if afectados > 0:
            # ✅ AUDITORÍA
            auditar_modificacion(
                tabla="Pacientes",
                registro_id=paciente_id,
                descripcion=f"Paciente modificado (ID: {paciente_id})",
                datos_ant={
                    'telefono': anterior[0],
                    'email': anterior[1],
                    'domicilio': anterior[2],
                    'obra_social': anterior[3]
                } if anterior else None,
                datos_nuevos=datos
            )
            return True, "✅ Paciente modificado correctamente."
        return False, "❌ No se encontró el paciente."
        
    except Exception as e:
        print(f"[ERROR] Error en modificar_paciente: {e}")
        return False, f"❌ Error: {e}"


def dar_baja_paciente(paciente_id):
    """
    Baja LÓGICA de paciente (DELETE lógico - activo = 0)
    
    IMPORTANTE: Los datos NO se eliminan. Se marca como inactivo.
    Los signos vitales y prescripciones se conservan.
    """
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        
        # Obtener datos antes de dar de baja
        cursor.execute("SELECT id, activo, dni, nombre, apellido FROM Pacientes WHERE id = ?", (paciente_id,))
        resultado = cursor.fetchone()
        
        if not resultado:
            conexion.close()
            return False, "❌ No se encontró el paciente."
        
        if resultado[1] == 0:
            conexion.close()
            return False, "❌ El paciente ya estaba dado de baja."
        
        # Baja lógica: activo = 0
        cursor.execute("UPDATE Pacientes SET activo = 0 WHERE id = ?", (paciente_id,))
        conexion.commit()
        conexion.close()
        
        print(f"[DEBUG] Paciente {paciente_id} dado de baja (lógica)")
        
        # ✅ AUDITORÍA
        auditar_baja(
            tabla="Pacientes",
            registro_id=paciente_id,
            descripcion=f"Paciente {resultado[3]} {resultado[4]} (DNI: {resultado[2]}) dado de baja",
            datos={
                'dni': resultado[2],
                'nombre': resultado[3],
                'apellido': resultado[4]
            }
        )
        
        return True, "✅ Paciente dado de baja correctamente.\nLos signos vitales y prescripciones se conservan."
        
    except Exception as e:
        print(f"[ERROR] Error en dar_baja_paciente: {e}")
        return False, f"❌ Error: {e}"


def reactivar_paciente(paciente_id):
    """Reactiva un paciente dado de baja (activo = 1)"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        
        # Obtener datos antes de reactivar
        cursor.execute("SELECT dni, nombre, apellido FROM Pacientes WHERE id = ?", (paciente_id,))
        datos = cursor.fetchone()
        
        cursor.execute("UPDATE Pacientes SET activo = 1 WHERE id = ?", (paciente_id,))
        conexion.commit()
        afectados = cursor.rowcount
        conexion.close()
        
        if afectados > 0:
            # ✅ AUDITORÍA
            auditar_reactivacion(
                tabla="Pacientes",
                registro_id=paciente_id,
                descripcion=f"Paciente {datos[1]} {datos[2]} (DNI: {datos[0]}) reactivado" if datos else f"Paciente ID {paciente_id} reactivado",
                datos={'dni': datos[0], 'nombre': datos[1], 'apellido': datos[2]} if datos else None
            )
            return True, "✅ Paciente reactivado correctamente."
        return False, "❌ No se encontró el paciente."
        
    except Exception as e:
        return False, f"❌ Error: {e}"


def contar_signos_vitales_paciente(paciente_id):
    """Cuenta los signos vitales asociados a un paciente"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("SELECT COUNT(*) FROM SignosVitales WHERE paciente_id = ?", (paciente_id,))
        total = cursor.fetchone()[0]
        conexion.close()
        return total
    except Exception as e:
        return 0


def contar_prescripciones_paciente(paciente_id):
    """Cuenta las prescripciones asociadas a un paciente"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("SELECT COUNT(*) FROM Prescripciones WHERE paciente_id = ?", (paciente_id,))
        total = cursor.fetchone()[0]
        conexion.close()
        return total
    except Exception as e:
        return 0


# ================================================================
# CAPA DE PRESENTACIÓN (FRONTEND)
# ================================================================

class AppPacientes:
    """Aplicación de gestión de pacientes (independiente de signos vitales)"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("OpenHIS-UNLaM - Gestión de Pacientes")
        self.root.geometry("1050x650")
        self.root.configure(bg='#f0f0f0')
        
        # Centrar la ventana
        self.root.update_idletasks()
        ancho = self.root.winfo_width()
        alto = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (ancho // 2)
        y = (self.root.winfo_screenheight() // 2) - (alto // 2)
        self.root.geometry(f'{ancho}x{alto}+{x}+{y}')
        
        # ---------- FRAME PRINCIPAL ----------
        self.frame_principal = tk.Frame(self.root, bg='#f0f0f0')
        self.frame_principal.pack(fill='both', expand=True, padx=20, pady=20)
        
        # ---------- TÍTULO ----------
        titulo = tk.Label(
            self.frame_principal,
            text="👤 HOSPITAL UNIVERSITARIO SAN JUSTO",
            font=('Arial', 18, 'bold'),
            bg='#f0f0f0',
            fg='#003366'
        )
        titulo.pack(pady=5)
        
        subtitulo = tk.Label(
            self.frame_principal,
            text="Sistema de Gestión de Pacientes - Sprint 3",
            font=('Arial', 11),
            bg='#f0f0f0',
            fg='#666666'
        )
        subtitulo.pack(pady=2)
        
        tk.Frame(self.frame_principal, height=2, bg='#cccccc').pack(fill='x', pady=10)
        
        # ---------- BOTONES PRINCIPALES ----------
        frame_botones = tk.Frame(self.frame_principal, bg='#f0f0f0')
        frame_botones.pack(pady=10)
        
        estilo_boton = {
            'font': ('Arial', 10, 'bold'),
            'padx': 15,
            'pady': 8,
            'relief': 'raised',
            'bd': 2
        }
        
        self.btn_registrar = tk.Button(
            frame_botones,
            text="📋 Registrar Paciente",
            bg='#4CAF50',
            fg='white',
            command=self.abrir_registro,
            **estilo_boton
        )
        self.btn_registrar.pack(side='left', padx=3)
        
        self.btn_buscar = tk.Button(
            frame_botones,
            text="🔍 Buscar Paciente",
            bg='#2196F3',
            fg='white',
            command=self.abrir_busqueda,
            **estilo_boton
        )
        self.btn_buscar.pack(side='left', padx=3)
        
        self.btn_modificar = tk.Button(
            frame_botones,
            text="✏️ Modificar Paciente",
            bg='#FF9800',
            fg='white',
            command=self.abrir_modificacion,
            **estilo_boton
        )
        self.btn_modificar.pack(side='left', padx=3)
        
        self.btn_baja = tk.Button(
            frame_botones,
            text="🗑️ Dar de Baja",
            bg='#f44336',
            fg='white',
            command=self.dar_baja_paciente,
            **estilo_boton
        )
        self.btn_baja.pack(side='left', padx=3)
        
        # --- SEPARADOR ---
        tk.Frame(frame_botones, width=10, bg='#f0f0f0').pack(side='left')
        
        self.btn_ver_activos = tk.Button(
            frame_botones,
            text="📊 Ver Activos",
            bg='#607D8B',
            fg='white',
            command=lambda: self.ver_pacientes(activos=True),
            **estilo_boton
        )
        self.btn_ver_activos.pack(side='left', padx=3)
        
        self.btn_ver_inactivos = tk.Button(
            frame_botones,
            text="📋 Ver Inactivos",
            bg='#9E9E9E',
            fg='white',
            command=lambda: self.ver_pacientes(activos=False),
            **estilo_boton
        )
        self.btn_ver_inactivos.pack(side='left', padx=3)
        
        tk.Frame(self.frame_principal, height=2, bg='#cccccc').pack(fill='x', pady=10)
        
        # ---------- LABEL DE RESULTADOS ----------
        self.label_resultados = tk.Label(
            self.frame_principal,
            text="Seleccione una acción para comenzar",
            font=('Arial', 11, 'italic'),
            bg='#f0f0f0',
            fg='#666666'
        )
        self.label_resultados.pack(pady=5)
        
        # ---------- TABLA DE PACIENTES ----------
        frame_tabla = tk.Frame(self.frame_principal, bg='#f0f0f0')
        frame_tabla.pack(fill='both', expand=True, pady=10)
        
        self.tree = ttk.Treeview(
            frame_tabla,
            columns=('ID', 'DNI', 'Nombre', 'Apellido', 'Teléfono', 'Estado'),
            show='headings',
            height=12,
            selectmode='browse'
        )
        
        columnas = [
            ('ID', 'HC', 50, 'center'),
            ('DNI', 'DNI', 100, 'center'),
            ('Nombre', 'Nombre', 180, 'w'),
            ('Apellido', 'Apellido', 180, 'w'),
            ('Teléfono', 'Teléfono', 120, 'center'),
            ('Estado', 'Estado', 80, 'center')
        ]
        
        for col, heading, width, anchor in columnas:
            self.tree.heading(col, text=heading)
            self.tree.column(col, width=width, anchor=anchor)
        
        self.tree.pack(side='left', fill='both', expand=True)
        
        scrollbar = ttk.Scrollbar(frame_tabla, orient='vertical', command=self.tree.yview)
        scrollbar.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # Evento doble clic
        self.tree.bind('<Double-1>', self.on_doble_click)
        
        # ---------- ESTADO ----------
        self.label_estado = tk.Label(
            self.frame_principal,
            text="✅ OpenHIS-UNLaM",
            font=('Arial', 9),
            bg='#f0f0f0',
            fg='#666666'
        )
        self.label_estado.pack(side='bottom', pady=5)
        
        # Cargar pacientes activos al iniciar
        self.ver_pacientes(activos=True)
    
    # ============================================================
    # MÉTODOS DE LA APLICACIÓN
    # ============================================================
    
    def ver_pacientes(self, activos=True):
        """Actualiza la tabla con pacientes según su estado"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        pacientes = listar_pacientes(activos=activos)
        
        for p in pacientes:
            estado = "✅ Activo" if p[5] == 1 else "🚫 Inactivo"
            self.tree.insert('', 'end', values=(p[0], p[1], p[2], p[3], p[4] or '', estado))
        
        tipo = "activos" if activos else "inactivos"
        self.label_resultados.config(text=f"📊 Total de pacientes {tipo}: {len(pacientes)}")
    
    def on_doble_click(self, event):
        """Maneja el doble clic en la tabla"""
        seleccion = self.tree.selection()
        if not seleccion:
            return
        
        item = self.tree.item(seleccion[0])
        valores = item['values']
        if not valores:
            return
        
        paciente_id = valores[0]
        paciente = buscar_paciente_por_id(paciente_id)
        if paciente:
            self.ver_detalle_paciente(paciente)
    
    def ver_detalle_paciente(self, paciente):
        """Muestra el detalle completo de un paciente"""
        ventana = tk.Toplevel(self.root)
        ventana.title(f"Detalle - {paciente['nombre']} {paciente['apellido']}")
        ventana.geometry("500x550")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()
        
        estado = "✅ Activo" if paciente['activo'] == 1 else "🚫 Inactivo"
        
        tk.Label(
            ventana,
            text=f"👤 DATOS DEL PACIENTE",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0',
            fg='#003366'
        ).pack(pady=10)
        
        frame_detalle = tk.Frame(ventana, bg='#f0f0f0')
        frame_detalle.pack(padx=30, pady=10, fill='both', expand=True)
        
        # Contar registros relacionados
        total_signos = contar_signos_vitales_paciente(paciente['id'])
        total_prescripciones = contar_prescripciones_paciente(paciente['id'])
        
        detalles = [
            ('🏥 Historia Clínica', paciente['id']),
            ('📋 DNI', paciente['dni']),
            ('👤 Nombre', paciente['nombre']),
            ('👤 Apellido', paciente['apellido']),
            ('📅 Fecha Nacimiento', paciente['fecha_nac']),
            ('⚧️ Sexo', paciente['sexo']),
            ('📞 Teléfono', paciente['telefono'] or 'No registrado'),
            ('✉️ Email', paciente['email'] or 'No registrado'),
            ('🏠 Domicilio', paciente['domicilio'] or 'No registrado'),
            ('🏢 Obra Social', paciente['obra_social'] or 'No registrada'),
            ('📅 Fecha Registro', paciente['fecha_registro']),
            ('📊 Estado', estado),
            ('❤️ Signos Vitales', f"{total_signos} registros"),
            ('💊 Prescripciones', f"{total_prescripciones} prescripciones")
        ]
        
        for label, value in detalles:
            frame = tk.Frame(frame_detalle, bg='#f0f0f0')
            frame.pack(fill='x', pady=2)
            tk.Label(
                frame,
                text=f"{label}:",
                width=20,
                anchor='w',
                bg='#f0f0f0',
                font=('Arial', 10, 'bold')
            ).pack(side='left')
            tk.Label(
                frame,
                text=str(value),
                anchor='w',
                bg='#f0f0f0',
                font=('Arial', 10),
                wraplength=300,
                justify='left'
            ).pack(side='left', padx=5)
        
        frame_botones = tk.Frame(ventana, bg='#f0f0f0')
        frame_botones.pack(pady=15)
        
        # Botones según estado
        if paciente['activo'] == 1:
            tk.Button(
                frame_botones,
                text="✏️ Modificar",
                bg='#FF9800',
                fg='white',
                font=('Arial', 10, 'bold'),
                padx=15,
                pady=5,
                command=lambda: [ventana.destroy(), self.abrir_modificacion_con_id(paciente['id'])]
            ).pack(side='left', padx=5)
            
            tk.Button(
                frame_botones,
                text="🗑️ Dar de Baja",
                bg='#f44336',
                fg='white',
                font=('Arial', 10, 'bold'),
                padx=15,
                pady=5,
                command=lambda: [ventana.destroy(), self.baja_con_id(paciente['id'])]
            ).pack(side='left', padx=5)
        else:
            tk.Button(
                frame_botones,
                text="♻️ Reactivar",
                bg='#4CAF50',
                fg='white',
                font=('Arial', 10, 'bold'),
                padx=15,
                pady=5,
                command=lambda: [ventana.destroy(), self.reactivar_con_id(paciente['id'])]
            ).pack(side='left', padx=5)
        
        tk.Button(
            frame_botones,
            text="❌ Cerrar",
            bg='#9E9E9E',
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=5,
            command=ventana.destroy
        ).pack(side='left', padx=5)
    
    # ---------- REGISTRAR PACIENTE ----------
    def abrir_registro(self):
        """Abre ventana para registrar nuevo paciente"""
        ventana = tk.Toplevel(self.root)
        ventana.title("Registrar Nuevo Paciente")
        ventana.geometry("550x620")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()
        ventana.resizable(False, False)
        
        tk.Label(
            ventana,
            text="📋 REGISTRO DE PACIENTE",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0',
            fg='#003366'
        ).pack(pady=10)
        
        tk.Label(
            ventana,
            text="Los campos con * son obligatorios",
            font=('Arial', 9),
            bg='#f0f0f0',
            fg='#666666'
        ).pack(pady=2)
        
        frame_campos = tk.Frame(ventana, bg='#f0f0f0')
        frame_campos.pack(padx=30, pady=10)
        
        campos = [
            ('DNI *', 'dni', True),
            ('Nombre *', 'nombre', True),
            ('Apellido *', 'apellido', True),
            ('Fecha Nac. (YYYY-MM-DD) *', 'fecha_nac', True),
            ('Sexo (M/F) *', 'sexo', True),
            ('Teléfono', 'telefono', False),
            ('Email', 'email', False),
            ('Domicilio', 'domicilio', False),
            ('Obra Social', 'obra_social', False)
        ]
        
        self.entries = {}
        for label_text, key, obligatorio in campos:
            frame = tk.Frame(frame_campos, bg='#f0f0f0')
            frame.pack(fill='x', pady=3)
            
            texto = label_text + ' *' if obligatorio else label_text
            tk.Label(
                frame,
                text=texto,
                width=22,
                anchor='w',
                bg='#f0f0f0',
                font=('Arial', 10)
            ).pack(side='left')
            
            entry = tk.Entry(frame, width=28, font=('Arial', 10))
            entry.pack(side='right')
            self.entries[key] = entry
        
        def guardar():
            obligatorios = ['dni', 'nombre', 'apellido', 'fecha_nac', 'sexo']
            for campo in obligatorios:
                if not self.entries[campo].get().strip():
                    messagebox.showerror("Error", f"El campo '{campo}' es obligatorio.")
                    return
            
            sexo = self.entries['sexo'].get().strip().upper()
            if sexo not in ['M', 'F']:
                messagebox.showerror("Error", "El sexo debe ser 'M' o 'F'.")
                return
            
            datos = {
                'dni': self.entries['dni'].get().strip(),
                'nombre': self.entries['nombre'].get().strip(),
                'apellido': self.entries['apellido'].get().strip(),
                'fecha_nac': self.entries['fecha_nac'].get().strip(),
                'sexo': sexo,
                'telefono': self.entries['telefono'].get().strip(),
                'email': self.entries['email'].get().strip(),
                'domicilio': self.entries['domicilio'].get().strip(),
                'obra_social': self.entries['obra_social'].get().strip()
            }
            
            resultado, info = registrar_paciente(datos)
            if resultado:
                messagebox.showinfo("Éxito", f"✅ Paciente registrado con éxito.\nHistoria Clínica N°: {info}")
                ventana.destroy()
                self.ver_pacientes(activos=True)
            else:
                messagebox.showerror("Error", f"❌ {info}")
        
        frame_botones = tk.Frame(ventana, bg='#f0f0f0')
        frame_botones.pack(pady=20)
        
        tk.Button(
            frame_botones,
            text="💾 Guardar",
            bg='#4CAF50',
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=25,
            pady=8,
            command=guardar
        ).pack(side='left', padx=10)
        
        tk.Button(
            frame_botones,
            text="❌ Cancelar",
            bg='#f44336',
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=25,
            pady=8,
            command=ventana.destroy
        ).pack(side='left', padx=10)
    
    # ---------- BUSCAR PACIENTE ----------
    def abrir_busqueda(self):
        """Abre ventana para buscar paciente por DNI"""
        ventana = tk.Toplevel(self.root)
        ventana.title("Buscar Paciente")
        ventana.geometry("500x450")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()
        ventana.resizable(False, False)
        
        tk.Label(
            ventana,
            text="🔍 BUSCAR PACIENTE POR DNI",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0',
            fg='#003366'
        ).pack(pady=15)
        
        frame_busqueda = tk.Frame(ventana, bg='#f0f0f0')
        frame_busqueda.pack(pady=10)
        
        tk.Label(
            frame_busqueda,
            text="DNI:",
            font=('Arial', 12, 'bold'),
            bg='#f0f0f0'
        ).pack(side='left', padx=10)
        
        entry_dni = tk.Entry(frame_busqueda, font=('Arial', 12), width=20)
        entry_dni.pack(side='left', padx=10)
        entry_dni.focus()
        
        frame_resultado = tk.Frame(ventana, bg='#f0f0f0')
        frame_resultado.pack(pady=10, fill='both', expand=True, padx=20)
        
        label_datos = tk.Label(
            frame_resultado,
            text="Ingrese un DNI y presione Buscar",
            font=('Arial', 10),
            bg='#f0f0f0',
            fg='#666666',
            justify='left'
        )
        label_datos.pack(pady=5)
        
        def buscar():
            dni = entry_dni.get().strip()
            if not dni:
                messagebox.showerror("Error", "Ingrese un DNI para buscar.")
                return
            
            resultado = buscar_paciente(dni)
            if resultado:
                estado = "✅ Activo" if resultado['activo'] == 1 else "🚫 Inactivo"
                texto = (
                    f"🏥 HISTORIA CLÍNICA: {resultado['id']}\n"
                    f"📋 DNI: {resultado['dni']}\n"
                    f"👤 Nombre: {resultado['nombre']} {resultado['apellido']}\n"
                    f"📅 Fecha Nac.: {resultado['fecha_nac']}\n"
                    f"⚧️ Sexo: {resultado['sexo']}\n"
                    f"📞 Teléfono: {resultado['telefono'] or 'No registrado'}\n"
                    f"✉️ Email: {resultado['email'] or 'No registrado'}\n"
                    f"🏠 Domicilio: {resultado['domicilio'] or 'No registrado'}\n"
                    f"🏢 Obra Social: {resultado['obra_social'] or 'No registrada'}\n"
                    f"📅 Registro: {resultado['fecha_registro']}\n"
                    f"📊 Estado: {estado}"
                )
                label_datos.config(text=texto, fg='#333333')
            else:
                label_datos.config(text="❌ Paciente no encontrado.", fg='#f44336')
        
        entry_dni.bind('<Return>', lambda e: buscar())
        
        frame_botones = tk.Frame(ventana, bg='#f0f0f0')
        frame_botones.pack(pady=10)
        
        tk.Button(
            frame_botones,
            text="🔍 Buscar",
            bg='#2196F3',
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=20,
            pady=8,
            command=buscar
        ).pack(side='left', padx=10)
        
        tk.Button(
            frame_botones,
            text="❌ Cerrar",
            bg='#f44336',
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=20,
            pady=8,
            command=ventana.destroy
        ).pack(side='left', padx=10)
    
    # ---------- MODIFICAR PACIENTE ----------
    def abrir_modificacion(self):
        """Abre ventana para modificar un paciente (buscándolo por DNI)"""
        ventana = tk.Toplevel(self.root)
        ventana.title("Modificar Paciente")
        ventana.geometry("550x450")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()
        ventana.resizable(False, False)
        
        tk.Label(
            ventana,
            text="✏️ MODIFICAR PACIENTE",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0',
            fg='#FF9800'
        ).pack(pady=10)
        
        frame_buscar = tk.Frame(ventana, bg='#f0f0f0')
        frame_buscar.pack(pady=10)
        
        tk.Label(
            frame_buscar,
            text="DNI del paciente:",
            font=('Arial', 11),
            bg='#f0f0f0'
        ).pack(side='left', padx=10)
        
        entry_dni = tk.Entry(frame_buscar, font=('Arial', 11), width=20)
        entry_dni.pack(side='left', padx=10)
        entry_dni.focus()
        
        frame_campos = tk.Frame(ventana, bg='#f0f0f0')
        frame_campos.pack(pady=10, padx=30, fill='both', expand=True)
        
        label_nombre = tk.Label(
            frame_campos,
            text="Ingrese un DNI y presione Buscar",
            font=('Arial', 11, 'bold'),
            bg='#f0f0f0',
            fg='#003366'
        )
        label_nombre.pack(pady=5)
        
        campos_mod = [
            ('Teléfono', 'telefono'),
            ('Email', 'email'),
            ('Domicilio', 'domicilio'),
            ('Obra Social', 'obra_social')
        ]
        
        entries_mod = {}
        frame_entries = tk.Frame(frame_campos, bg='#f0f0f0')
        
        for label_text, key in campos_mod:
            frame = tk.Frame(frame_entries, bg='#f0f0f0')
            frame.pack(fill='x', pady=3)
            
            tk.Label(
                frame,
                text=label_text + ":",
                width=15,
                anchor='w',
                bg='#f0f0f0',
                font=('Arial', 10)
            ).pack(side='left')
            
            entry = tk.Entry(frame, width=30, font=('Arial', 10))
            entry.pack(side='right')
            entries_mod[key] = entry
        
        paciente_id_actual = None
        
        def buscar_modificar():
            nonlocal paciente_id_actual
            dni = entry_dni.get().strip()
            if not dni:
                messagebox.showerror("Error", "Ingrese un DNI.")
                return
            
            resultado = buscar_paciente(dni)
            if resultado:
                paciente_id_actual = resultado['id']
                label_nombre.config(
                    text=f"Paciente: {resultado['nombre']} {resultado['apellido']} (HC: {resultado['id']})",
                    fg='#003366'
                )
                entries_mod['telefono'].delete(0, tk.END)
                entries_mod['telefono'].insert(0, resultado['telefono'])
                entries_mod['email'].delete(0, tk.END)
                entries_mod['email'].insert(0, resultado['email'])
                entries_mod['domicilio'].delete(0, tk.END)
                entries_mod['domicilio'].insert(0, resultado['domicilio'])
                entries_mod['obra_social'].delete(0, tk.END)
                entries_mod['obra_social'].insert(0, resultado['obra_social'])
                frame_entries.pack(pady=10)
            else:
                messagebox.showerror("Error", "Paciente no encontrado.")
        
        entry_dni.bind('<Return>', lambda e: buscar_modificar())
        
        tk.Button(
            ventana,
            text="🔍 Buscar",
            bg='#2196F3',
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=5,
            command=buscar_modificar
        ).pack(pady=5)
        
        def guardar_modificacion():
            nonlocal paciente_id_actual
            if not paciente_id_actual:
                messagebox.showerror("Error", "Primero busque un paciente.")
                return
            
            datos = {
                'telefono': entries_mod['telefono'].get().strip(),
                'email': entries_mod['email'].get().strip(),
                'domicilio': entries_mod['domicilio'].get().strip(),
                'obra_social': entries_mod['obra_social'].get().strip()
            }
            
            resultado, mensaje = modificar_paciente(paciente_id_actual, datos)
            if resultado:
                messagebox.showinfo("Éxito", f"✅ {mensaje}")
                ventana.destroy()
                self.ver_pacientes(activos=True)
            else:
                messagebox.showerror("Error", f"❌ {mensaje}")
        
        frame_botones = tk.Frame(ventana, bg='#f0f0f0')
        frame_botones.pack(pady=15)
        
        tk.Button(
            frame_botones,
            text="💾 Guardar Cambios",
            bg='#FF9800',
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=20,
            pady=8,
            command=guardar_modificacion
        ).pack(side='left', padx=10)
        
        tk.Button(
            frame_botones,
            text="❌ Cancelar",
            bg='#f44336',
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=20,
            pady=8,
            command=ventana.destroy
        ).pack(side='left', padx=10)
    
    def abrir_modificacion_con_id(self, paciente_id):
        """Abre modificación directa con el ID del paciente"""
        paciente = buscar_paciente_por_id(paciente_id)
        if not paciente:
            messagebox.showerror("Error", "Paciente no encontrado.")
            return
        
        ventana = tk.Toplevel(self.root)
        ventana.title(f"Modificar - {paciente['nombre']} {paciente['apellido']}")
        ventana.geometry("500x400")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()
        
        tk.Label(
            ventana,
            text=f"✏️ MODIFICAR PACIENTE",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0',
            fg='#FF9800'
        ).pack(pady=10)
        
        tk.Label(
            ventana,
            text=f"{paciente['nombre']} {paciente['apellido']} (HC: {paciente['id']})",
            font=('Arial', 11, 'bold'),
            bg='#f0f0f0',
            fg='#003366'
        ).pack(pady=5)
        
        frame_campos = tk.Frame(ventana, bg='#f0f0f0')
        frame_campos.pack(padx=30, pady=10)
        
        campos_mod = [
            ('Teléfono', 'telefono', paciente['telefono']),
            ('Email', 'email', paciente['email']),
            ('Domicilio', 'domicilio', paciente['domicilio']),
            ('Obra Social', 'obra_social', paciente['obra_social'])
        ]
        
        entries_mod = {}
        for label_text, key, valor in campos_mod:
            frame = tk.Frame(frame_campos, bg='#f0f0f0')
            frame.pack(fill='x', pady=3)
            
            tk.Label(
                frame,
                text=label_text + ":",
                width=15,
                anchor='w',
                bg='#f0f0f0',
                font=('Arial', 10)
            ).pack(side='left')
            
            entry = tk.Entry(frame, width=30, font=('Arial', 10))
            entry.insert(0, valor)
            entry.pack(side='right')
            entries_mod[key] = entry
        
        def guardar():
            datos = {
                'telefono': entries_mod['telefono'].get().strip(),
                'email': entries_mod['email'].get().strip(),
                'domicilio': entries_mod['domicilio'].get().strip(),
                'obra_social': entries_mod['obra_social'].get().strip()
            }
            
            resultado, mensaje = modificar_paciente(paciente_id, datos)
            if resultado:
                messagebox.showinfo("Éxito", f"✅ {mensaje}")
                ventana.destroy()
                self.ver_pacientes(activos=True)
            else:
                messagebox.showerror("Error", f"❌ {mensaje}")
        
        frame_botones = tk.Frame(ventana, bg='#f0f0f0')
        frame_botones.pack(pady=15)
        
        tk.Button(
            frame_botones,
            text="💾 Guardar Cambios",
            bg='#FF9800',
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=20,
            pady=8,
            command=guardar
        ).pack(side='left', padx=10)
        
        tk.Button(
            frame_botones,
            text="❌ Cancelar",
            bg='#f44336',
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=20,
            pady=8,
            command=ventana.destroy
        ).pack(side='left', padx=10)
    
    # ---------- BAJA LÓGICA DE PACIENTE ----------
    def dar_baja_paciente(self):
        """Abre ventana para dar de baja un paciente"""
        ventana = tk.Toplevel(self.root)
        ventana.title("Dar de Baja Paciente")
        ventana.geometry("500x300")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()
        ventana.resizable(False, False)
        
        tk.Label(
            ventana,
            text="🗑️ DAR DE BAJA PACIENTE",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0',
            fg='#f44336'
        ).pack(pady=10)
        
        tk.Label(
            ventana,
            text="ℹ️ La baja es LÓGICA: los datos se conservan\n"
                 "para auditoría. Los signos vitales y prescripciones\n"
                 "NO se eliminan.",
            font=('Arial', 10),
            bg='#f0f0f0',
            fg='#666666',
            justify='center'
        ).pack(pady=10)
        
        frame = tk.Frame(ventana, bg='#f0f0f0')
        frame.pack(pady=15)
        
        tk.Label(
            frame,
            text="DNI del paciente:",
            font=('Arial', 11),
            bg='#f0f0f0'
        ).pack(side='left', padx=10)
        
        entry_dni = tk.Entry(frame, font=('Arial', 11), width=20)
        entry_dni.pack(side='left', padx=10)
        entry_dni.focus()
        
        def confirmar_baja():
            dni = entry_dni.get().strip()
            if not dni:
                messagebox.showerror("Error", "Ingrese un DNI.")
                return
            
            paciente = buscar_paciente(dni)
            if not paciente:
                messagebox.showerror("Error", "Paciente no encontrado.")
                return
            
            if paciente['activo'] == 0:
                messagebox.showwarning("Aviso", "El paciente ya está dado de baja.")
                return
            
            # Contar registros asociados
            total_signos = contar_signos_vitales_paciente(paciente['id'])
            total_prescripciones = contar_prescripciones_paciente(paciente['id'])
            
            if messagebox.askyesno(
                "⚠️ Confirmar Baja",
                f"¿Está seguro de dar de baja a {paciente['nombre']} {paciente['apellido']} (HC: {paciente['id']})?\n\n"
                f"📊 Registros asociados:\n"
                f"   ❤️ Signos vitales: {total_signos}\n"
                f"   💊 Prescripciones: {total_prescripciones}\n\n"
                f"✅ Los datos del paciente SE CONSERVAN (baja lógica)\n"
                f"❌ El paciente no aparecerá en listados activos"
            ):
                resultado, mensaje = dar_baja_paciente(paciente['id'])
                if resultado:
                    messagebox.showinfo("Éxito", f"✅ {mensaje}")
                    ventana.destroy()
                    self.ver_pacientes(activos=True)
                else:
                    messagebox.showerror("Error", f"❌ {mensaje}")
        
        entry_dni.bind('<Return>', lambda e: confirmar_baja())
        
        tk.Button(
            ventana,
            text="🗑️ Confirmar Baja",
            bg='#f44336',
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=25,
            pady=8,
            command=confirmar_baja
        ).pack(pady=10)
    
    def baja_con_id(self, paciente_id):
        """Baja directa con ID"""
        paciente = buscar_paciente_por_id(paciente_id)
        if not paciente:
            return
        
        total_signos = contar_signos_vitales_paciente(paciente_id)
        total_prescripciones = contar_prescripciones_paciente(paciente_id)
        
        if messagebox.askyesno(
            "⚠️ Confirmar Baja",
            f"¿Está seguro de dar de baja a {paciente['nombre']} {paciente['apellido']}?\n\n"
            f"📊 Registros asociados:\n"
            f"   ❤️ Signos vitales: {total_signos}\n"
            f"   💊 Prescripciones: {total_prescripciones}\n\n"
            f"✅ Los datos del paciente SE CONSERVAN (baja lógica)"
        ):
            resultado, mensaje = dar_baja_paciente(paciente_id)
            if resultado:
                messagebox.showinfo("Éxito", f"✅ {mensaje}")
                self.ver_pacientes(activos=True)
            else:
                messagebox.showerror("Error", f"❌ {mensaje}")
    
    def reactivar_con_id(self, paciente_id):
        """Reactiva un paciente dado de baja"""
        if messagebox.askyesno(
            "♻️ Reactivar Paciente",
            "¿Está seguro de reactivar este paciente?"
        ):
            resultado, mensaje = reactivar_paciente(paciente_id)
            if resultado:
                messagebox.showinfo("Éxito", f"✅ {mensaje}")
                self.ver_pacientes(activos=True)
            else:
                messagebox.showerror("Error", f"❌ {mensaje}")


# ================================================================
# PUNTO DE ENTRADA
# ================================================================

if __name__ == "__main__":
    root = tk.Tk()
    app = AppPacientes(root)
    root.mainloop()
