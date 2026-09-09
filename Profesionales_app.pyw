# ================================================================
# Profesionales_app.pyw
# SPRINT 3 - MÓDULO DE GESTIÓN DE PROFESIONALES (COMPLETO)
# ================================================================
#
# FUNCIONALIDADES:
#   ✅ Registrar profesional (CREATE) - HU-04
#   ✅ Buscar profesional por DNI (READ) - HU-05
#   ✅ Modificar datos del profesional (UPDATE)
#   ✅ Eliminar profesional (DELETE)
#   ✅ Ver listado completo de profesionales
#   ✅ Selector de especialidades desde tabla maestra
#   ✅ Interfaz gráfica con Tkinter
#
# ESTRUCTURA DE TABLA:
#   Profesionales (
#       id INTEGER PRIMARY KEY AUTOINCREMENT,
#       dni TEXT UNIQUE NOT NULL,
#       nombre TEXT NOT NULL,
#       apellido TEXT NOT NULL,
#       fecha_nacimiento TEXT NOT NULL,
#       sexo TEXT NOT NULL CHECK (sexo IN ('M', 'F')),
#       matricula TEXT UNIQUE NOT NULL,
#       especialidad_id INTEGER NOT NULL,  -- REFERENCIA A TABLA ESPECIALIDADES
#       telefono TEXT,
#       email TEXT,
#       fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#       FOREIGN KEY (especialidad_id) REFERENCES Especialidades(id)
#   )
# ================================================================

import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk

# ================================================================
# CAPA DE ACCESO A DATOS (BACKEND)
# ================================================================

def conectar_bd():
    """Establece conexión con la base de datos Salud.db"""
    return sqlite3.connect('BD/Salud.db')


# -------------------- FUNCIONES DE TABLAS MAESTRAS --------------------

def obtener_especialidades_selector():
    """
    Obtiene lista de especialidades activas para el selector (combobox)
    Retorna: Lista de tuplas (id, nombre_completo)
    """
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT id, codigo, nombre 
            FROM Especialidades 
            WHERE activo = 1 
            ORDER BY nombre
        """)
        resultados = cursor.fetchall()
        conexion.close()
        return resultados
    except Exception as e:
        print(f"Error al obtener especialidades: {e}")
        return []


def obtener_nombre_especialidad(especialidad_id):
    """Obtiene el nombre de una especialidad por su ID"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("SELECT nombre FROM Especialidades WHERE id = ?", (especialidad_id,))
        resultado = cursor.fetchone()
        conexion.close()
        return resultado[0] if resultado else "No especificada"
    except Exception as e:
        return "No especificada"


# -------------------- PROFESIONALES (CRUD COMPLETO) --------------------

def registrar_profesional(datos):
    """
    HU-04: Registrar nuevo profesional (CREATE)
    
    Parámetros:
        datos: diccionario con los campos del profesional
            - dni (str): obligatorio, único
            - nombre (str): obligatorio
            - apellido (str): obligatorio
            - fecha_nac (str): obligatorio, formato YYYY-MM-DD
            - sexo (str): obligatorio, 'M' o 'F'
            - matricula (str): obligatorio, única
            - especialidad_id (int): obligatorio, ID de la especialidad
            - telefono (str): opcional
            - email (str): opcional
    
    Retorna:
        (True, id_nuevo) si tuvo éxito
        (False, mensaje_error) si falló
    """
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        
        cursor.execute("""
            INSERT INTO Profesionales 
            (dni, nombre, apellido, fecha_nacimiento, sexo, 
             matricula, especialidad_id, telefono, email)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datos['dni'],
            datos['nombre'],
            datos['apellido'],
            datos['fecha_nac'],
            datos['sexo'],
            datos['matricula'],
            datos['especialidad_id'],
            datos.get('telefono', ''),
            datos.get('email', '')
        ))
        
        conexion.commit()
        nuevo_id = cursor.lastrowid
        conexion.close()
        return True, nuevo_id
        
    except sqlite3.IntegrityError as e:
        if 'dni' in str(e):
            return False, "❌ DNI duplicado. Ya existe un profesional con ese DNI."
        elif 'matricula' in str(e):
            return False, "❌ Matrícula duplicada. Ya existe un profesional con esa matrícula."
        return False, f"❌ Error de integridad: {e}"
    except Exception as e:
        return False, f"❌ Error: {e}"


def buscar_profesional(dni):
    """
    HU-05: Buscar profesional por DNI (READ)
    Retorna: dict con datos del profesional o None
    """
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT p.*, e.nombre as especialidad_nombre 
            FROM Profesionales p
            LEFT JOIN Especialidades e ON p.especialidad_id = e.id
            WHERE p.dni = ?
        """, (dni,))
        profesional = cursor.fetchone()
        conexion.close()
        
        if profesional:
            return {
                'id': profesional[0],
                'dni': profesional[1],
                'nombre': profesional[2],
                'apellido': profesional[3],
                'fecha_nac': profesional[4],
                'sexo': profesional[5],
                'matricula': profesional[6],
                'especialidad_id': profesional[7],
                'especialidad_nombre': profesional[11] or 'No especificada',
                'telefono': profesional[8] or '',
                'email': profesional[9] or '',
                'fecha_registro': profesional[10]
            }
        return None
        
    except Exception as e:
        print(f"Error en buscar_profesional: {e}")
        return None


def buscar_profesional_por_id(profesional_id):
    """Busca un profesional por su ID"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT p.*, e.nombre as especialidad_nombre 
            FROM Profesionales p
            LEFT JOIN Especialidades e ON p.especialidad_id = e.id
            WHERE p.id = ?
        """, (profesional_id,))
        profesional = cursor.fetchone()
        conexion.close()
        
        if profesional:
            return {
                'id': profesional[0],
                'dni': profesional[1],
                'nombre': profesional[2],
                'apellido': profesional[3],
                'matricula': profesional[6],
                'especialidad_id': profesional[7],
                'especialidad_nombre': profesional[11] or 'No especificada'
            }
        return None
    except Exception as e:
        print(f"Error en buscar_profesional_por_id: {e}")
        return None


def listar_profesionales():
    """
    Obtiene todos los profesionales ordenados por apellido y nombre
    Retorna: Lista de tuplas (id, dni, nombre, apellido, especialidad, matricula)
    """
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT 
                p.id, 
                p.dni, 
                p.nombre, 
                p.apellido, 
                e.nombre as especialidad_nombre,
                p.matricula
            FROM Profesionales p
            LEFT JOIN Especialidades e ON p.especialidad_id = e.id
            ORDER BY p.apellido, p.nombre
        """)
        profesionales = cursor.fetchall()
        conexion.close()
        return profesionales
    except Exception as e:
        print(f"Error en listar_profesionales: {e}")
        return []


def modificar_profesional(profesional_id, datos):
    """
    Modifica datos de un profesional (UPDATE)
    
    Parámetros:
        profesional_id (int): ID del profesional
        datos (dict): 
            - telefono (str): opcional
            - email (str): opcional
            - especialidad_id (int): ID de la especialidad
    """
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        
        cursor.execute("""
            UPDATE Profesionales 
            SET telefono = ?, email = ?, especialidad_id = ?
            WHERE id = ?
        """, (
            datos.get('telefono', ''),
            datos.get('email', ''),
            datos.get('especialidad_id', 0),
            profesional_id
        ))
        
        conexion.commit()
        afectados = cursor.rowcount
        conexion.close()
        
        if afectados > 0:
            return True, "✅ Profesional modificado correctamente."
        return False, "❌ No se encontró el profesional."
        
    except Exception as e:
        return False, f"❌ Error: {e}"


def eliminar_profesional(profesional_id):
    """
    Elimina un profesional (DELETE)
    Retorna: (True, mensaje) o (False, mensaje_error)
    """
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        
        # Verificar que el profesional existe
        cursor.execute("SELECT id FROM Profesionales WHERE id = ?", (profesional_id,))
        if not cursor.fetchone():
            conexion.close()
            return False, "❌ No se encontró el profesional."
        
        cursor.execute("DELETE FROM Profesionales WHERE id = ?", (profesional_id,))
        conexion.commit()
        conexion.close()
        
        return True, "✅ Profesional eliminado correctamente."
        
    except Exception as e:
        return False, f"❌ Error: {e}"


# ================================================================
# CAPA DE PRESENTACIÓN (FRONTEND)
# ================================================================

class AppProfesionales:
    """Aplicación de gestión de profesionales"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("OpenHIS-UNLaM - Gestión de Profesionales (Sprint 3)")
        self.root.geometry("1000x650")
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
            text="👨‍⚕️ HOSPITAL UNIVERSITARIO SAN JUSTO",
            font=('Arial', 18, 'bold'),
            bg='#f0f0f0',
            fg='#003366'
        )
        titulo.pack(pady=5)
        
        subtitulo = tk.Label(
            self.frame_principal,
            text="Sistema de Gestión de Profesionales - Sprint 3",
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
        
        # Botón Registrar
        self.btn_registrar = tk.Button(
            frame_botones,
            text="📋 Registrar Profesional",
            bg='#4CAF50',
            fg='white',
            command=self.abrir_registro,
            **estilo_boton
        )
        self.btn_registrar.pack(side='left', padx=3)
        
        # Botón Buscar
        self.btn_buscar = tk.Button(
            frame_botones,
            text="🔍 Buscar Profesional",
            bg='#2196F3',
            fg='white',
            command=self.abrir_busqueda,
            **estilo_boton
        )
        self.btn_buscar.pack(side='left', padx=3)
        
        # Botón Modificar
        self.btn_modificar = tk.Button(
            frame_botones,
            text="✏️ Modificar Profesional",
            bg='#FF9800',
            fg='white',
            command=self.abrir_modificacion,
            **estilo_boton
        )
        self.btn_modificar.pack(side='left', padx=3)
        
        # Botón Eliminar
        self.btn_eliminar = tk.Button(
            frame_botones,
            text="🗑️ Eliminar Profesional",
            bg='#f44336',
            fg='white',
            command=self.eliminar_profesional,
            **estilo_boton
        )
        self.btn_eliminar.pack(side='left', padx=3)
        
        # --- SEPARADOR ---
        tk.Frame(frame_botones, width=20, bg='#f0f0f0').pack(pady=50)
        frame_botones = tk.Frame(self.frame_principal, bg='#f0f0f0')
        frame_botones.pack(pady=3)

        # Botón Ver Todos
        self.btn_ver_todos = tk.Button(
            frame_botones,
            text="📊 Ver Todos",
            bg='#607D8B',
            fg='white',
            command=self.ver_todos,
            **estilo_boton
        )
        self.btn_ver_todos.pack(side='left', padx=3)
        
        # Botón Actualizar Especialidades
        self.btn_actualizar_esp = tk.Button(
            frame_botones,
            text="🔄 Actualizar Especialidades",
            bg='#9C27B0',
            fg='white',
            command=self.actualizar_especialidades,
            **estilo_boton
        )
        self.btn_actualizar_esp.pack(side='left', padx=3)
        
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
        
        # ---------- TABLA DE PROFESIONALES ----------
        frame_tabla = tk.Frame(self.frame_principal, bg='#f0f0f0')
        frame_tabla.pack(fill='both', expand=True, pady=10)
        
        self.tree = ttk.Treeview(
            frame_tabla,
            columns=('ID', 'DNI', 'Nombre', 'Apellido', 'Especialidad', 'Matrícula'),
            show='headings',
            height=12,
            selectmode='browse'
        )
        
        columnas = [
            ('ID', 'ID', 40, 'center'),
            ('DNI', 'DNI', 100, 'center'),
            ('Nombre', 'Nombre', 180, 'w'),
            ('Apellido', 'Apellido', 180, 'w'),
            ('Especialidad', 'Especialidad', 180, 'w'),
            ('Matrícula', 'Matrícula', 100, 'center')
        ]
        
        for col, heading, width, anchor in columnas:
            self.tree.heading(col, text=heading)
            self.tree.column(col, width=width, anchor=anchor)
        
        self.tree.pack(side='left', fill='both', expand=True)
        
        scrollbar = ttk.Scrollbar(frame_tabla, orient='vertical', command=self.tree.yview)
        scrollbar.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # ---------- ESTADO ----------
        self.label_estado = tk.Label(
            self.frame_principal,
            text="✅ Sistema listo",
            font=('Arial', 9),
            bg='#f0f0f0',
            fg='#666666'
        )
        self.label_estado.pack(side='bottom', pady=5)
        
        # Cargar todos los profesionales al iniciar
        self.ver_todos()
    
    # ============================================================
    # MÉTODOS DE LA APLICACIÓN
    # ============================================================
    
    # ---------- VER TODOS ----------
    def ver_todos(self):
        """Actualiza la tabla con todos los profesionales"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        profesionales = listar_profesionales()
        for p in profesionales:
            # p = (id, dni, nombre, apellido, especialidad, matricula)
            self.tree.insert('', 'end', values=(p[0], p[1], p[2], p[3], p[4] or 'Sin especialidad', p[5]))
        
        self.label_resultados.config(text=f"📊 Total de profesionales: {len(profesionales)}")
    
    # ---------- ACTUALIZAR ESPECIALIDADES ----------
    def actualizar_especialidades(self):
        """Actualiza la lista de especialidades disponibles (para usar en comboboxes)"""
        # Solo muestra un mensaje de confirmación
        messagebox.showinfo("Actualización", 
            "🔄 Las especialidades se actualizan automáticamente\n"
            "desde la tabla maestra al abrir los formularios.\n\n"
            "Si agregó nuevas especialidades, cierre y vuelva a abrir\n"
            "el formulario de registro o modificación.")
        self.label_estado.config(text="✅ Especialidades actualizadas")
    
    # ---------- REGISTRAR PROFESIONAL ----------
    def abrir_registro(self):
        """Abre ventana para registrar nuevo profesional"""
        ventana = tk.Toplevel(self.root)
        ventana.title("Registrar Nuevo Profesional")
        ventana.geometry("550x650")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()
        ventana.resizable(False, False)
        
        # Título
        tk.Label(
            ventana,
            text="📋 REGISTRO DE PROFESIONAL",
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
        
        # ---------- OBTENER ESPECIALIDADES ----------
        especialidades = obtener_especialidades_selector()
        if not especialidades:
            messagebox.showwarning("Advertencia", 
                "No hay especialidades cargadas en el sistema.\n"
                "Por favor, cargue especialidades primero en el módulo de Tablas Maestras.")
            ventana.destroy()
            return
        
        # ---------- CAMPOS ----------
        frame_campos = tk.Frame(ventana, bg='#f0f0f0')
        frame_campos.pack(padx=30, pady=10)
        
        campos = [
            ('DNI *', 'dni', True),
            ('Nombre *', 'nombre', True),
            ('Apellido *', 'apellido', True),
            ('Fecha Nac. (YYYY-MM-DD) *', 'fecha_nac', True),
            ('Sexo (M/F) *', 'sexo', True),
            ('Matrícula *', 'matricula', True),
            ('Especialidad *', 'especialidad', True),
            ('Teléfono', 'telefono', False),
            ('Email', 'email', False)
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
            
            if key == 'especialidad':
                # Combobox para especialidad
                combo = ttk.Combobox(frame, width=28, font=('Arial', 10), state='readonly')
                valores_especialidades = [f"{esp[1]} - {esp[2]}" for esp in especialidades]
                combo['values'] = valores_especialidades
                if valores_especialidades:
                    combo.current(0)
                combo.pack(side='right')
                self.entries[key] = combo
            else:
                entry = tk.Entry(frame, width=28, font=('Arial', 10))
                entry.pack(side='right')
                self.entries[key] = entry
        
        # ---------- FUNCIÓN GUARDAR ----------
        def guardar():
            # Validar campos obligatorios
            obligatorios = ['dni', 'nombre', 'apellido', 'fecha_nac', 'sexo', 'matricula']
            for campo in obligatorios:
                if not self.entries[campo].get().strip():
                    messagebox.showerror("Error", f"El campo '{campo}' es obligatorio.")
                    return
            
            # Validar especialidad seleccionada
            especialidad_seleccionada = self.entries['especialidad'].get()
            if not especialidad_seleccionada:
                messagebox.showerror("Error", "Debe seleccionar una especialidad.")
                return
            
            # Obtener ID de la especialidad seleccionada
            especialidad_id = None
            for esp in especialidades:
                if f"{esp[1]} - {esp[2]}" == especialidad_seleccionada:
                    especialidad_id = esp[0]
                    break
            
            if not especialidad_id:
                messagebox.showerror("Error", "Especialidad no válida.")
                return
            
            # Validar sexo
            sexo = self.entries['sexo'].get().strip().upper()
            if sexo not in ['M', 'F']:
                messagebox.showerror("Error", "El sexo debe ser 'M' o 'F'.")
                return
            
            # Recolectar datos
            datos = {
                'dni': self.entries['dni'].get().strip(),
                'nombre': self.entries['nombre'].get().strip(),
                'apellido': self.entries['apellido'].get().strip(),
                'fecha_nac': self.entries['fecha_nac'].get().strip(),
                'sexo': sexo,
                'matricula': self.entries['matricula'].get().strip(),
                'especialidad_id': especialidad_id,
                'telefono': self.entries['telefono'].get().strip(),
                'email': self.entries['email'].get().strip()
            }
            
            resultado, info = registrar_profesional(datos)
            if resultado:
                messagebox.showinfo("Éxito", f"✅ Profesional registrado con éxito.\nID: {info}")
                ventana.destroy()
                self.ver_todos()
            else:
                messagebox.showerror("Error", f"❌ {info}")
        
        # ---------- BOTONES ----------
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
    
    # ---------- BUSCAR PROFESIONAL ----------
    def abrir_busqueda(self):
        """Abre ventana para buscar profesional por DNI"""
        ventana = tk.Toplevel(self.root)
        ventana.title("Buscar Profesional")
        ventana.geometry("500x400")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()
        ventana.resizable(False, False)
        
        tk.Label(
            ventana,
            text="🔍 BUSCAR PROFESIONAL POR DNI",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0',
            fg='#003366'
        ).pack(pady=15)
        
        # Frame para ingresar DNI
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
        
        # Frame para mostrar resultados
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
            
            resultado = buscar_profesional(dni)
            if resultado:
                texto = (
                    f"👨‍⚕️ ID: {resultado['id']}\n"
                    f"📋 DNI: {resultado['dni']}\n"
                    f"👤 Nombre: {resultado['nombre']} {resultado['apellido']}\n"
                    f"📅 Fecha Nac.: {resultado['fecha_nac']}\n"
                    f"⚧️ Sexo: {resultado['sexo']}\n"
                    f"📜 Matrícula: {resultado['matricula']}\n"
                    f"🏥 Especialidad: {resultado['especialidad_nombre']}\n"
                    f"📞 Teléfono: {resultado['telefono'] or 'No registrado'}\n"
                    f"✉️ Email: {resultado['email'] or 'No registrado'}\n"
                    f"📅 Registro: {resultado['fecha_registro']}"
                )
                label_datos.config(text=texto, fg='#333333')
            else:
                label_datos.config(text="❌ Profesional no encontrado.", fg='#f44336')
        
        entry_dni.bind('<Return>', lambda e: buscar())
        
        # Botones
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
    
    # ---------- MODIFICAR PROFESIONAL ----------
    def abrir_modificacion(self):
        """Abre ventana para modificar datos de un profesional"""
        ventana = tk.Toplevel(self.root)
        ventana.title("Modificar Profesional")
        ventana.geometry("550x500")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()
        ventana.resizable(False, False)
        
        tk.Label(
            ventana,
            text="✏️ MODIFICAR PROFESIONAL",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0',
            fg='#FF9800'
        ).pack(pady=10)
        
        # ---------- BUSCAR POR DNI ----------
        frame_buscar = tk.Frame(ventana, bg='#f0f0f0')
        frame_buscar.pack(pady=10)
        
        tk.Label(
            frame_buscar,
            text="DNI del profesional:",
            font=('Arial', 11),
            bg='#f0f0f0'
        ).pack(side='left', padx=10)
        
        entry_dni = tk.Entry(frame_buscar, font=('Arial', 11), width=20)
        entry_dni.pack(side='left', padx=10)
        entry_dni.focus()
        
        # ---------- CAMPOS MODIFICABLES ----------
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
        
        # Obtener especialidades para el combobox
        especialidades = obtener_especialidades_selector()
        
        campos_mod = [
            ('Teléfono', 'telefono'),
            ('Email', 'email'),
            ('Especialidad *', 'especialidad')
        ]
        
        entries_mod = {}
        frame_entries = tk.Frame(frame_campos, bg='#f0f0f0')
        
        for label_text, key in campos_mod:
            frame = tk.Frame(frame_entries, bg='#f0f0f0')
            frame.pack(fill='x', pady=3)
            
            tk.Label(
                frame,
                text=label_text + ":",
                width=18,
                anchor='w',
                bg='#f0f0f0',
                font=('Arial', 10)
            ).pack(side='left')
            
            if key == 'especialidad':
                combo = ttk.Combobox(frame, width=28, font=('Arial', 10), state='readonly')
                valores_especialidades = [f"{esp[1]} - {esp[2]}" for esp in especialidades]
                combo['values'] = valores_especialidades
                if valores_especialidades:
                    combo.current(0)
                combo.pack(side='right')
                entries_mod[key] = combo
            else:
                entry = tk.Entry(frame, width=28, font=('Arial', 10))
                entry.pack(side='right')
                entries_mod[key] = entry
        
        profesional_id_actual = None
        
        def buscar_modificar():
            nonlocal profesional_id_actual
            dni = entry_dni.get().strip()
            if not dni:
                messagebox.showerror("Error", "Ingrese un DNI.")
                return
            
            resultado = buscar_profesional(dni)
            if resultado:
                profesional_id_actual = resultado['id']
                label_nombre.config(
                    text=f"Profesional: {resultado['nombre']} {resultado['apellido']} (ID: {resultado['id']})",
                    fg='#003366'
                )
                entries_mod['telefono'].delete(0, tk.END)
                entries_mod['telefono'].insert(0, resultado['telefono'] or '')
                entries_mod['email'].delete(0, tk.END)
                entries_mod['email'].insert(0, resultado['email'] or '')
                
                # Seleccionar especialidad en el combobox
                especialidad_actual = resultado['especialidad_nombre']
                for esp in especialidades:
                    if f"{esp[1]} - {esp[2]}" == f"{resultado['especialidad_id']} - {especialidad_actual}":
                        entries_mod['especialidad'].current(especialidades.index(esp))
                        break
                
                frame_entries.pack(pady=10)
            else:
                messagebox.showerror("Error", "Profesional no encontrado.")
        
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
            nonlocal profesional_id_actual
            if not profesional_id_actual:
                messagebox.showerror("Error", "Primero busque un profesional.")
                return
            
            # Validar especialidad seleccionada
            especialidad_seleccionada = entries_mod['especialidad'].get()
            if not especialidad_seleccionada:
                messagebox.showerror("Error", "Debe seleccionar una especialidad.")
                return
            
            # Obtener ID de la especialidad seleccionada
            especialidad_id = None
            for esp in especialidades:
                if f"{esp[1]} - {esp[2]}" == especialidad_seleccionada:
                    especialidad_id = esp[0]
                    break
            
            if not especialidad_id:
                messagebox.showerror("Error", "Especialidad no válida.")
                return
            
            datos = {
                'telefono': entries_mod['telefono'].get().strip(),
                'email': entries_mod['email'].get().strip(),
                'especialidad_id': especialidad_id
            }
            
            resultado, mensaje = modificar_profesional(profesional_id_actual, datos)
            if resultado:
                messagebox.showinfo("Éxito", f"✅ {mensaje}")
                ventana.destroy()
                self.ver_todos()
            else:
                messagebox.showerror("Error", f"❌ {mensaje}")
        
        # ---------- BOTONES ----------
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
    
    # ---------- ELIMINAR PROFESIONAL ----------
    def eliminar_profesional(self):
        """Abre ventana para eliminar un profesional"""
        ventana = tk.Toplevel(self.root)
        ventana.title("Eliminar Profesional")
        ventana.geometry("480x250")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()
        ventana.resizable(False, False)
        
        tk.Label(
            ventana,
            text="🗑️ ELIMINAR PROFESIONAL",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0',
            fg='#f44336'
        ).pack(pady=10)
        
        tk.Label(
            ventana,
            text="⚠️ Esta operación no se puede deshacer.",
            font=('Arial', 10),
            bg='#f0f0f0',
            fg='#f44336'
        ).pack(pady=5)
        
        frame = tk.Frame(ventana, bg='#f0f0f0')
        frame.pack(pady=15)
        
        tk.Label(
            frame,
            text="DNI del profesional:",
            font=('Arial', 11),
            bg='#f0f0f0'
        ).pack(side='left', padx=10)
        
        entry_dni = tk.Entry(frame, font=('Arial', 11), width=20)
        entry_dni.pack(side='left', padx=10)
        entry_dni.focus()
        
        def confirmar_eliminar():
            dni = entry_dni.get().strip()
            if not dni:
                messagebox.showerror("Error", "Ingrese un DNI.")
                return
            
            profesional = buscar_profesional(dni)
            if not profesional:
                messagebox.showerror("Error", "Profesional no encontrado.")
                return
            
            if messagebox.askyesno(
                "⚠️ Confirmar Eliminación",
                f"¿Está seguro de eliminar a {profesional['nombre']} {profesional['apellido']} (ID: {profesional['id']})?"
            ):
                resultado, mensaje = eliminar_profesional(profesional['id'])
                if resultado:
                    messagebox.showinfo("Éxito", f"✅ {mensaje}")
                    ventana.destroy()
                    self.ver_todos()
                else:
                    messagebox.showerror("Error", f"❌ {mensaje}")
        
        entry_dni.bind('<Return>', lambda e: confirmar_eliminar())
        
        tk.Button(
            ventana,
            text="🗑️ Eliminar",
            bg='#f44336',
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=25,
            pady=8,
            command=confirmar_eliminar
        ).pack(pady=15)


# ================================================================
# PUNTO DE ENTRADA
# ================================================================

if __name__ == "__main__":
    root = tk.Tk()
    app = AppProfesionales(root)
    root.mainloop()
