# ================================================================
# Pacientes2_app.pyw
# SPRINT 2 - PARTE 1: CRUD COMPLETO DE PACIENTES EN TKINTER
# Equipo ¿?
# ================================================================
#
# FUNCIONALIDADES:
#   ✅ Registrar paciente (CREATE) - HU-01
#   ✅ Buscar paciente por DNI (READ) - HU-02
#   ✅ Modificar datos del paciente (UPDATE) - HU-03
#   ✅ Eliminar paciente (DELETE) - HU-03
#   ✅ Ver listado completo de pacientes
#   ✅ Interfaz gráfica con Tkinter
#
# REQUISITOS PREVIOS:
#   - Base de datos: Salud.db con tabla Pacientes
#   - Python 3.x con Tkinter (incluido por defecto)
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


# ---------- OPERACIONES CRUD DE PACIENTES ----------
def registrar_paciente(datos):
    """
    HU-01: Registrar nuevo paciente (CREATE)
    
    Parámetros:
        datos: diccionario con los campos del paciente
            - dni (str): obligatorio, único
            - nombre (str): obligatorio
            - apellido (str): obligatorio
            - fecha_nac (str): obligatorio, formato YYYY-MM-DD
            - sexo (str): obligatorio, 'M' o 'F'
            - telefono (str): opcional
            - email (str): opcional
            - domicilio (str): opcional
            - obra_social (str): opcional
    
    Retorna:
        (True, id_nuevo) si tuvo éxito
        (False, mensaje_error) si falló
    """
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        
        cursor.execute("""
            INSERT INTO Pacientes 
            (dni, nombre, apellido, fecha_nacimiento, sexo, 
             telefono, email, domicilio, obra_social)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datos['dni'],
            datos['nombre'],
            datos['apellido'],
            datos['fecha_nac'],
            datos['sexo'],
            datos.get('telefono', ''),
            datos.get('email', ''),
            datos.get('domicilio', ''),
            datos.get('obra_social', '')
        ))
        
        conexion.commit()
        nuevo_id = cursor.lastrowid
        conexion.close()
        
        return True, nuevo_id
        
    except sqlite3.IntegrityError:
        return False, "❌ DNI duplicado. Ya existe un paciente con ese DNI."
    except Exception as e:
        return False, f"❌ Error: {e}"


def buscar_paciente(dni):
    """
    HU-02: Buscar paciente por DNI (READ)
    
    Parámetros:
        dni (str): DNI del paciente a buscar
    
    Retorna:
        diccionario con todos los datos del paciente, o None si no existe
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
                'fecha_registro': paciente[10]
            }
        return None
        
    except Exception as e:
        print(f"Error en buscar_paciente: {e}")
        return None


def modificar_paciente(paciente_id, datos):
    """
    HU-03: Modificar datos de un paciente (UPDATE)
    
    Parámetros:
        paciente_id (int): ID del paciente a modificar
        datos (dict): diccionario con los campos a modificar
            - telefono (str): opcional
            - email (str): opcional
            - domicilio (str): opcional
            - obra_social (str): opcional
    
    Retorna:
        (True, mensaje) si tuvo éxito
        (False, mensaje_error) si falló
    """
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        
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
            return True, "✅ Paciente modificado correctamente."
        return False, "❌ No se encontró el paciente."
        
    except Exception as e:
        return False, f"❌ Error: {e}"


def eliminar_paciente(paciente_id):
    """
    HU-03: Eliminar paciente (DELETE)
    
    Parámetros:
        paciente_id (int): ID del paciente a eliminar
    
    Retorna:
        (True, mensaje) si tuvo éxito
        (False, mensaje_error) si falló
    
    Nota: Esta es una eliminación física. Para una baja lógica,
    se podría agregar un campo 'activo' en la tabla.
    """
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        
        # Verificar que el paciente existe
        cursor.execute("SELECT id FROM Pacientes WHERE id = ?", (paciente_id,))
        if not cursor.fetchone():
            conexion.close()
            return False, "❌ No se encontró el paciente."
        
        # Eliminar el paciente
        cursor.execute("DELETE FROM Pacientes WHERE id = ?", (paciente_id,))
        
        conexion.commit()
        conexion.close()
        
        return True, "✅ Paciente eliminado correctamente."
        
    except Exception as e:
        return False, f"❌ Error: {e}"


def listar_pacientes():
    """
    Obtiene todos los pacientes ordenados por apellido y nombre
    
    Retorna:
        Lista de tuplas (id, dni, nombre, apellido, telefono)
    """
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT id, dni, nombre, apellido, telefono 
            FROM Pacientes 
            ORDER BY apellido, nombre
        """)
        pacientes = cursor.fetchall()
        conexion.close()
        return pacientes
    except Exception as e:
        print(f"Error en listar_pacientes: {e}")
        return []


# ================================================================
# CAPA DE PRESENTACIÓN (FRONTEND) - APLICACIÓN TKINTER
# ================================================================

class AppPacientes:
    """
    Aplicación principal de gestión de pacientes con interfaz gráfica.
    Implementa las 4 operaciones CRUD completas.
    """
    
    def __init__(self, root):
        """
        Inicializa la ventana principal y todos sus componentes.
        
        Parámetros:
            root: ventana Tkinter principal
        """
        self.root = root
        self.root.title("OpenHIS-UNLaM - Gestión de Pacientes (CRUD)")
        self.root.geometry("900x600")
        self.root.configure(bg='#f0f0f0')
        
        # ---------- FRAME PRINCIPAL ----------
        self.frame_principal = tk.Frame(self.root, bg='#f0f0f0')
        self.frame_principal.pack(fill='both', expand=True, padx=20, pady=20)
        
        # ---------- TÍTULO ----------
        titulo = tk.Label(
            self.frame_principal,
            text="🏥 HOSPITAL UNIVERSITARIO SAN JUSTO",
            font=('Arial', 16, 'bold'),
            bg='#f0f0f0',
            fg='#003366'
        )
        titulo.pack(pady=10)
        
        subtitulo = tk.Label(
            self.frame_principal,
            text="Sistema de Gestión de Pacientes - CRUD Completo (Sprint 2 - Parte 1)",
            font=('Arial', 10),
            bg='#f0f0f0',
            fg='#666666'
        )
        subtitulo.pack(pady=5)
        
        # Separador
        tk.Frame(self.frame_principal, height=2, bg='#cccccc').pack(fill='x', pady=10)
        
        # ---------- BOTONES PRINCIPALES ----------
        frame_botones = tk.Frame(self.frame_principal, bg='#f0f0f0')
        frame_botones.pack(pady=10)
        
        # Botón Registrar
        self.btn_registrar = tk.Button(
            frame_botones,
            text="📋 Registrar Paciente",
            font=('Arial', 10),
            bg='#4CAF50',
            fg='white',
            padx=10,
            pady=8,
            command=self.abrir_registro
        )
        self.btn_registrar.pack(side='left', padx=5)
        
        # Botón Buscar
        self.btn_buscar = tk.Button(
            frame_botones,
            text="🔍 Buscar Paciente",
            font=('Arial', 10),
            bg='#2196F3',
            fg='white',
            padx=10,
            pady=8,
            command=self.abrir_busqueda
        )
        self.btn_buscar.pack(side='left', padx=5)
        
        # Botón Modificar
        self.btn_modificar = tk.Button(
            frame_botones,
            text="✏️ Modificar Paciente",
            font=('Arial', 10),
            bg='#FF9800',
            fg='white',
            padx=10,
            pady=8,
            command=self.abrir_modificacion
        )
        self.btn_modificar.pack(side='left', padx=5)
        
        # Botón Eliminar
        self.btn_eliminar = tk.Button(
            frame_botones,
            text="🗑️ Eliminar Paciente",
            font=('Arial', 10),
            bg='#f44336',
            fg='white',
            padx=10,
            pady=8,
            command=self.eliminar_paciente
        )
        self.btn_eliminar.pack(side='left', padx=5)
        
        # Botón Ver Todos
        self.btn_ver_todos = tk.Button(
            frame_botones,
            text="📊 Ver Todos",
            font=('Arial', 10),
            bg='#9E9E9E',
            fg='white',
            padx=10,
            pady=8,
            command=self.ver_todos
        )
        self.btn_ver_todos.pack(side='left', padx=5)
        
        # Separador
        tk.Frame(self.frame_principal, height=2, bg='#cccccc').pack(fill='x', pady=10)
        
        # ---------- LABEL DE RESULTADOS ----------
        self.label_resultados = tk.Label(
            self.frame_principal,
            text="Seleccione una acción para comenzar",
            font=('Arial', 11),
            bg='#f0f0f0',
            fg='#333333'
        )
        self.label_resultados.pack(pady=5)
        
        # ---------- TABLA DE PACIENTES (Treeview) ----------
        # Frame contenedor para tabla y scrollbar
        frame_tabla = tk.Frame(self.frame_principal, bg='#f0f0f0')
        frame_tabla.pack(fill='both', expand=True, pady=10)
        
        self.tree = ttk.Treeview(
            frame_tabla,
            columns=('ID', 'DNI', 'Nombre', 'Apellido', 'Teléfono'),
            show='headings',
            height=12
        )
        
        # Configurar columnas
        self.tree.heading('ID', text='HC')
        self.tree.heading('DNI', text='DNI')
        self.tree.heading('Nombre', text='Nombre')
        self.tree.heading('Apellido', text='Apellido')
        self.tree.heading('Teléfono', text='Teléfono')
        
        self.tree.column('ID', width=50, anchor='center')
        self.tree.column('DNI', width=100, anchor='center')
        self.tree.column('Nombre', width=200)
        self.tree.column('Apellido', width=200)
        self.tree.column('Teléfono', width=120, anchor='center')
        
        self.tree.pack(side='left', fill='both', expand=True)
        
        # Scrollbar vertical
        scrollbar = ttk.Scrollbar(frame_tabla, orient='vertical', command=self.tree.yview)
        scrollbar.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # ---------- ESTADO ----------
        self.label_estado = tk.Label(
            self.frame_principal,
            text="✅ OpenHIS-UNLaM",
            font=('Arial', 9),
            bg='#f0f0f0',
            fg='#666666'
        )
        self.label_estado.pack(side='bottom', pady=5)
        
        # Cargar todos los pacientes al iniciar
        self.ver_todos()
    
    # ----------------------------------------------------------------
    # MÉTODOS DE LA APLICACIÓN
    # ----------------------------------------------------------------
    
    def ver_todos(self):
        """
        Actualiza la tabla con la lista completa de pacientes.
        Se ejecuta al iniciar y después de cada operación.
        """
        # Limpiar tabla
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Obtener y mostrar pacientes
        pacientes = listar_pacientes()
        for p in pacientes:
            self.tree.insert('', 'end', values=(p[0], p[1], p[2], p[3], p[4]))
        
        self.label_resultados.config(text=f"📊 Total de pacientes: {len(pacientes)}")
    
    # ---------- REGISTRAR PACIENTE (CREATE) ----------
    
    def abrir_registro(self):
        """
        Abre una ventana modal con formulario para registrar un nuevo paciente.
        Implementa HU-01: Alta de pacientes.
        """
        ventana = tk.Toplevel(self.root)
        ventana.title("Registrar Nuevo Paciente")
        ventana.geometry("500x600")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()  # Ventana modal
        
        # Título
        tk.Label(
            ventana,
            text="📋 REGISTRO DE PACIENTE",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0',
            fg='#003366'
        ).pack(pady=10)
        
        # Frame para campos
        frame_campos = tk.Frame(ventana, bg='#f0f0f0')
        frame_campos.pack(padx=30, pady=10)
        
        # Lista de campos: (etiqueta, clave, es_obligatorio)
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
            
            # Etiqueta con asterisco si es obligatorio
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
        
        # Función para guardar
        def guardar():
            # Validar campos obligatorios
            obligatorios = ['dni', 'nombre', 'apellido', 'fecha_nac', 'sexo']
            for campo in obligatorios:
                if not self.entries[campo].get().strip():
                    messagebox.showerror("Error", f"El campo {campo} es obligatorio.")
                    return
            
            # Recolectar datos
            datos = {
                'dni': self.entries['dni'].get().strip(),
                'nombre': self.entries['nombre'].get().strip(),
                'apellido': self.entries['apellido'].get().strip(),
                'fecha_nac': self.entries['fecha_nac'].get().strip(),
                'sexo': self.entries['sexo'].get().strip().upper(),
                'telefono': self.entries['telefono'].get().strip(),
                'email': self.entries['email'].get().strip(),
                'domicilio': self.entries['domicilio'].get().strip(),
                'obra_social': self.entries['obra_social'].get().strip()
            }
            
            # Validar sexo
            if datos['sexo'] not in ['M', 'F']:
                messagebox.showerror("Error", "El sexo debe ser 'M' o 'F'.")
                return
            
            # Registrar
            resultado, info = registrar_paciente(datos)
            if resultado:
                messagebox.showinfo("Éxito", f"✅ Paciente registrado con éxito.\nHistoria Clínica N°: {info}")
                ventana.destroy()
                self.ver_todos()
            else:
                messagebox.showerror("Error", f"❌ {info}")
        
        # Botones de acción
        frame_botones = tk.Frame(ventana, bg='#f0f0f0')
        frame_botones.pack(pady=20)
        
        tk.Button(
            frame_botones,
            text="💾 Guardar",
            bg='#4CAF50',
            fg='white',
            font=('Arial', 11),
            padx=20,
            pady=8,
            command=guardar
        ).pack(side='left', padx=10)
        
        tk.Button(
            frame_botones,
            text="❌ Cancelar",
            bg='#f44336',
            fg='white',
            font=('Arial', 11),
            padx=20,
            pady=8,
            command=ventana.destroy
        ).pack(side='left', padx=10)
    
    # ---------- BUSCAR PACIENTE (READ) ----------
    
    def abrir_busqueda(self):
        """
        Abre una ventana para buscar un paciente por DNI.
        Implementa HU-02: Búsqueda de pacientes.
        """
        ventana = tk.Toplevel(self.root)
        ventana.title("Buscar Paciente")
        ventana.geometry("450x300")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()
        
        tk.Label(
            ventana,
            text="🔍 BUSCAR PACIENTE POR DNI",
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
            font=('Arial', 12),
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
            
            resultado = buscar_paciente(dni)
            if resultado:
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
                    f"📅 Fecha Registro: {resultado['fecha_registro']}"
                )
                label_datos.config(text=texto, fg='#333333')
            else:
                label_datos.config(text="❌ Paciente no encontrado.", fg='#f44336')
        
        # Permitir búsqueda con Enter
        entry_dni.bind('<Return>', lambda e: buscar())
        
        tk.Button(
            ventana,
            text="🔍 Buscar",
            bg='#2196F3',
            fg='white',
            font=('Arial', 11),
            padx=20,
            pady=8,
            command=buscar
        ).pack(pady=10)
    
    # ---------- MODIFICAR PACIENTE (UPDATE) ----------
    
    def abrir_modificacion(self):
        """
        Abre una ventana para modificar datos de un paciente existente.
        Implementa HU-03: Modificación de pacientes.
        """
        ventana = tk.Toplevel(self.root)
        ventana.title("Modificar Paciente")
        ventana.geometry("500x400")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()
        
        tk.Label(
            ventana,
            text="✏️ MODIFICAR PACIENTE",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0',
            fg='#FF9800'
        ).pack(pady=10)
        
        # Buscar por DNI
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
        
        # Frame para campos modificables
        frame_campos = tk.Frame(ventana, bg='#f0f0f0')
        frame_campos.pack(pady=10, padx=30, fill='both', expand=True)
        
        # Label que muestra el nombre del paciente encontrado
        label_nombre = tk.Label(
            frame_campos,
            text="Ingrese un DNI y presione Buscar",
            font=('Arial', 11, 'bold'),
            bg='#f0f0f0',
            fg='#003366'
        )
        label_nombre.pack(pady=5)
        
        # Campos a modificar
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
                # Cargar datos actuales en los campos
                entries_mod['telefono'].delete(0, tk.END)
                entries_mod['telefono'].insert(0, resultado['telefono'] or '')
                entries_mod['email'].delete(0, tk.END)
                entries_mod['email'].insert(0, resultado['email'] or '')
                entries_mod['domicilio'].delete(0, tk.END)
                entries_mod['domicilio'].insert(0, resultado['domicilio'] or '')
                entries_mod['obra_social'].delete(0, tk.END)
                entries_mod['obra_social'].insert(0, resultado['obra_social'] or '')
                frame_entries.pack(pady=10)
            else:
                messagebox.showerror("Error", "Paciente no encontrado.")
        
        entry_dni.bind('<Return>', lambda e: buscar_modificar())
        
        tk.Button(
            ventana,
            text="🔍 Buscar",
            bg='#2196F3',
            fg='white',
            font=('Arial', 10),
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
                self.ver_todos()
            else:
                messagebox.showerror("Error", f"❌ {mensaje}")
        
        tk.Button(
            ventana,
            text="💾 Guardar Cambios",
            bg='#FF9800',
            fg='white',
            font=('Arial', 11),
            padx=20,
            pady=8,
            command=guardar_modificacion
        ).pack(pady=10)
    
    # ---------- ELIMINAR PACIENTE (DELETE) ----------
    
    def eliminar_paciente(self):
        """
        Abre una ventana para eliminar un paciente buscándolo por DNI.
        Implementa HU-03: Baja de pacientes.
        """
        ventana = tk.Toplevel(self.root)
        ventana.title("Eliminar Paciente")
        ventana.geometry("450x220")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()
        
        tk.Label(
            ventana,
            text="🗑️ ELIMINAR PACIENTE",
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
            text="DNI del paciente:",
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
            
            paciente = buscar_paciente(dni)
            if not paciente:
                messagebox.showerror("Error", "Paciente no encontrado.")
                return
            
            # Confirmar con el usuario
            if messagebox.askyesno(
                "⚠️ Confirmar Eliminación",
                f"¿Está seguro de eliminar a {paciente['nombre']} {paciente['apellido']} (HC: {paciente['id']})?\n\nEsta acción no se puede deshacer."
            ):
                resultado, mensaje = eliminar_paciente(paciente['id'])
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
            font=('Arial', 11),
            padx=20,
            pady=8,
            command=confirmar_eliminar
        ).pack(pady=10)


# ================================================================
# PUNTO DE ENTRADA
# ================================================================

if __name__ == "__main__":
    root = tk.Tk()
    app = AppPacientes(root)
    root.mainloop()
