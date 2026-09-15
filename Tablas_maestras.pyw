# ================================================================
# Tablas_maestras.pyw
# MÓDULO DE GESTIÓN DE TABLAS MAESTRAS
# SPRINT 3 - ADMINISTRACIÓN DE DATOS REFERENCIALES
# ================================================================
#
# FUNCIONALIDADES PARA CADA TABLA:
#   ✅ Listar registros
#   ✅ Registrar nuevo (CREATE)
#   ✅ Buscar por código o término (READ)
#   ✅ Modificar (UPDATE)
#   ✅ Activar/Desactivar (DELETE lógico)
#   ✅ Interfaz gráfica con Tkinter
#
# TABLAS GESTIONADAS:
#   1. Especialidades - Usada por Profesionales
#   2. SnomedCT - Terminología clínica (para HCE)
#   3. Farmacos - Medicamentos (para futura farmacia)
# ================================================================

import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk

# ================================================================
# CAPA DE ACCESO A DATOS
# ================================================================

def conectar_bd():
    """Establece conexión con la base de datos Salud.db"""
    return sqlite3.connect('BD/Salud.db')


# -------------------- FUNCIONES GENÉRICAS --------------------

def tabla_existe(nombre_tabla):
    """Verifica si una tabla existe en la base de datos"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name=?
        """, (nombre_tabla,))
        existe = cursor.fetchone() is not None
        conexion.close()
        return existe
    except Exception as e:
        return False


def crear_tablas_maestras():
    """Crea las tablas maestras si no existen"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        
        # Tabla Especialidades
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Especialidades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT UNIQUE NOT NULL,
                nombre TEXT NOT NULL,
                descripcion TEXT,
                activo INTEGER DEFAULT 1,
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Tabla SnomedCT
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS SnomedCT (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT UNIQUE NOT NULL,
                termino TEXT NOT NULL,
                descripcion TEXT,
                categoria TEXT,
                activo INTEGER DEFAULT 1,
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Tabla Farmacos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Farmacos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT UNIQUE NOT NULL,
                nombre TEXT NOT NULL,
                principio_activo TEXT,
                presentacion TEXT,
                concentracion TEXT,
                via_administracion TEXT,
                activo INTEGER DEFAULT 1,
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conexion.commit()
        conexion.close()
        return True
    except Exception as e:
        print(f"Error al crear tablas maestras: {e}")
        return False


# -------------------- ESPECIALIDADES --------------------

def listar_especialidades(activos=True):
    """Lista todas las especialidades"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        if activos:
            cursor.execute("""
                SELECT id, codigo, nombre, descripcion, activo 
                FROM Especialidades 
                WHERE activo = 1
                ORDER BY nombre
            """)
        else:
            cursor.execute("""
                SELECT id, codigo, nombre, descripcion, activo 
                FROM Especialidades 
                ORDER BY nombre
            """)
        resultados = cursor.fetchall()
        conexion.close()
        return resultados
    except Exception as e:
        return []


def registrar_especialidad(datos):
    """Registra una nueva especialidad"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("""
            INSERT INTO Especialidades (codigo, nombre, descripcion, activo)
            VALUES (?, ?, ?, ?)
        """, (datos['codigo'], datos['nombre'], datos['descripcion'], 1))
        conexion.commit()
        nuevo_id = cursor.lastrowid
        conexion.close()
        return True, nuevo_id
    except sqlite3.IntegrityError:
        return False, "❌ Código duplicado. Ya existe una especialidad con ese código."
    except Exception as e:
        return False, f"❌ Error: {e}"


def modificar_especialidad(especialidad_id, datos):
    """Modifica una especialidad"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("""
            UPDATE Especialidades 
            SET codigo = ?, nombre = ?, descripcion = ?
            WHERE id = ?
        """, (datos['codigo'], datos['nombre'], datos['descripcion'], especialidad_id))
        conexion.commit()
        conexion.close()
        return True, "✅ Especialidad modificada correctamente."
    except sqlite3.IntegrityError:
        return False, "❌ Código duplicado."
    except Exception as e:
        return False, f"❌ Error: {e}"


def eliminar_especialidad(especialidad_id):
    """Elimina lógicamente una especialidad (activo = 0)"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("UPDATE Especialidades SET activo = 0 WHERE id = ?", (especialidad_id,))
        conexion.commit()
        conexion.close()
        return True, "✅ Especialidad desactivada correctamente."
    except Exception as e:
        return False, f"❌ Error: {e}"


def obtener_especialidades_selector():
    """Obtiene lista de especialidades para selector (combobox)"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("SELECT id, nombre FROM Especialidades WHERE activo = 1 ORDER BY nombre")
        resultados = cursor.fetchall()
        conexion.close()
        return resultados
    except Exception as e:
        return []


# -------------------- SNOMED CT --------------------

def listar_snomed(categoria=None):
    """Lista términos SNOMED CT"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        if categoria:
            cursor.execute("""
                SELECT id, codigo, termino, descripcion, categoria, activo 
                FROM SnomedCT 
                WHERE categoria = ? AND activo = 1
                ORDER BY termino
            """, (categoria,))
        else:
            cursor.execute("""
                SELECT id, codigo, termino, descripcion, categoria, activo 
                FROM SnomedCT 
                WHERE activo = 1
                ORDER BY termino
            """)
        resultados = cursor.fetchall()
        conexion.close()
        return resultados
    except Exception as e:
        return []


def registrar_snomed(datos):
    """Registra un término SNOMED CT"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("""
            INSERT INTO SnomedCT (codigo, termino, descripcion, categoria, activo)
            VALUES (?, ?, ?, ?, ?)
        """, (datos['codigo'], datos['termino'], datos['descripcion'], 
              datos['categoria'], 1))
        conexion.commit()
        nuevo_id = cursor.lastrowid
        conexion.close()
        return True, nuevo_id
    except sqlite3.IntegrityError:
        return False, "❌ Código duplicado."
    except Exception as e:
        return False, f"❌ Error: {e}"


def buscar_snomed_por_termino(termino):
    """Busca términos SNOMED CT por texto"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT id, codigo, termino, descripcion, categoria 
            FROM SnomedCT 
            WHERE termino LIKE ? AND activo = 1
            ORDER BY termino
            LIMIT 20
        """, (f'%{termino}%',))
        resultados = cursor.fetchall()
        conexion.close()
        return resultados
    except Exception as e:
        return []


# -------------------- FÁRMACOS --------------------

def listar_farmacos():
    """Lista todos los fármacos activos"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT id, codigo, nombre, principio_activo, presentacion, 
                   concentracion, via_administracion, activo 
            FROM Farmacos 
            WHERE activo = 1
            ORDER BY nombre
        """)
        resultados = cursor.fetchall()
        conexion.close()
        return resultados
    except Exception as e:
        return []


def registrar_farmaco(datos):
    """Registra un nuevo fármaco"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("""
            INSERT INTO Farmacos 
            (codigo, nombre, principio_activo, presentacion, concentracion, via_administracion, activo)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            datos['codigo'], datos['nombre'], datos['principio_activo'],
            datos['presentacion'], datos['concentracion'], datos['via_administracion'], 1
        ))
        conexion.commit()
        nuevo_id = cursor.lastrowid
        conexion.close()
        return True, nuevo_id
    except sqlite3.IntegrityError:
        return False, "❌ Código duplicado."
    except Exception as e:
        return False, f"❌ Error: {e}"


# ================================================================
# CAPA DE PRESENTACIÓN - APPLET GENERAL PARA TABLAS MAESTRAS
# ================================================================

class AppTablasMaestras:
    """Aplicación principal para gestionar tablas maestras"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("OpenHIS-UNLaM - Tablas Maestras")
        self.root.geometry("900x650")
        self.root.configure(bg='#f0f0f0')
        
        # Verificar/Crear tablas
        crear_tablas_maestras()
        
        # ---------- FRAME PRINCIPAL ----------
        self.frame_principal = tk.Frame(self.root, bg='#f0f0f0')
        self.frame_principal.pack(fill='both', expand=True, padx=20, pady=20)
        
        # ---------- TÍTULO ----------
        titulo = tk.Label(
            self.frame_principal,
            text="📚 TABLAS MAESTRAS",
            font=('Arial', 18, 'bold'),
            bg='#f0f0f0',
            fg='#003366'
        )
        titulo.pack(pady=10)
        
        subtitulo = tk.Label(
            self.frame_principal,
            text="Gestión de Especialidades, SNOMED CT y Fármacos",
            font=('Arial', 11),
            bg='#f0f0f0',
            fg='#666666'
        )
        subtitulo.pack(pady=5)
        
        tk.Frame(self.frame_principal, height=2, bg='#cccccc').pack(fill='x', pady=10)
        
        # ---------- BOTONES DE SELECCIÓN DE TABLA ----------
        frame_tablas = tk.Frame(self.frame_principal, bg='#f0f0f0')
        frame_tablas.pack(pady=10)
        
        estilo_boton = {
            'font': ('Arial', 11, 'bold'),
            'padx': 20,
            'pady': 8,
            'relief': 'raised',
            'bd': 2
        }
        
        self.btn_especialidades = tk.Button(
            frame_tablas,
            text="🏥 Especialidades",
            bg='#4CAF50',
            fg='white',
            command=self.mostrar_especialidades,
            **estilo_boton
        )
        self.btn_especialidades.pack(side='left', padx=5)
        
        self.btn_snomed = tk.Button(
            frame_tablas,
            text="📋 SNOMED CT",
            bg='#2196F3',
            fg='white',
            command=self.mostrar_snomed,
            **estilo_boton
        )
        self.btn_snomed.pack(side='left', padx=5)
        
        self.btn_farmacos = tk.Button(
            frame_tablas,
            text="💊 Fármacos",
            bg='#FF9800',
            fg='white',
            command=self.mostrar_farmacos,
            **estilo_boton
        )
        self.btn_farmacos.pack(side='left', padx=5)
        
        tk.Frame(self.frame_principal, height=2, bg='#cccccc').pack(fill='x', pady=10)
        
        # ---------- ÁREA DE CONTENIDO ----------
        self.frame_contenido = tk.Frame(self.frame_principal, bg='#f0f0f0')
        self.frame_contenido.pack(fill='both', expand=True, pady=10)
        
        # Mensaje inicial
        self.label_mensaje = tk.Label(
            self.frame_contenido,
            text="Seleccione una tabla para comenzar la gestión",
            font=('Arial', 14),
            bg='#f0f0f0',
            fg='#666666'
        )
        self.label_mensaje.pack(expand=True)
        
        # ---------- ESTADO ----------
        self.label_estado = tk.Label(
            self.frame_principal,
            text="✅ Sistema listo",
            font=('Arial', 9),
            bg='#f0f0f0',
            fg='#666666'
        )
        self.label_estado.pack(side='bottom', pady=5)
    
    # ============================================================
    # MÉTODOS PARA MOSTRAR TABLAS
    # ============================================================
    
    def limpiar_contenido(self):
        """Limpia el área de contenido"""
        for widget in self.frame_contenido.winfo_children():
            widget.destroy()
    
    def mostrar_especialidades(self):
        """Muestra la gestión de especialidades"""
        self.limpiar_contenido()
        
        # Título
        tk.Label(
            self.frame_contenido,
            text="🏥 GESTIÓN DE ESPECIALIDADES",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0',
            fg='#4CAF50'
        ).pack(pady=5)
        
        # Botón Agregar
        frame_botones = tk.Frame(self.frame_contenido, bg='#f0f0f0')
        frame_botones.pack(pady=5)
        
        tk.Button(
            frame_botones,
            text="➕ Agregar Especialidad",
            bg='#4CAF50',
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=5,
            command=self.agregar_especialidad
        ).pack(side='left', padx=5)
        
        tk.Button(
            frame_botones,
            text="🔄 Actualizar",
            bg='#2196F3',
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=5,
            command=self.mostrar_especialidades
        ).pack(side='left', padx=5)
        
        # Tabla
        frame_tabla = tk.Frame(self.frame_contenido, bg='#f0f0f0')
        frame_tabla.pack(fill='both', expand=True, pady=10)
        
        tree = ttk.Treeview(
            frame_tabla,
            columns=('ID', 'Código', 'Nombre', 'Descripción', 'Estado'),
            show='headings',
            height=15
        )
        tree.heading('ID', text='ID')
        tree.heading('Código', text='Código')
        tree.heading('Nombre', text='Nombre')
        tree.heading('Descripción', text='Descripción')
        tree.heading('Estado', text='Estado')
        tree.column('ID', width=40, anchor='center')
        tree.column('Código', width=80, anchor='center')
        tree.column('Nombre', width=200)
        tree.column('Descripción', width=300)
        tree.column('Estado', width=80, anchor='center')
        tree.pack(side='left', fill='both', expand=True)
        
        scrollbar = ttk.Scrollbar(frame_tabla, orient='vertical', command=tree.yview)
        scrollbar.pack(side='right', fill='y')
        tree.configure(yscrollcommand=scrollbar.set)
        
        # Cargar datos
        especialidades = listar_especialidades(activos=False)
        for esp in especialidades:
            estado = "Activo" if esp[4] == 1 else "Inactivo"
            tree.insert('', 'end', values=(esp[0], esp[1], esp[2], esp[3], estado))
        
        # Eventos
        tree.bind('<Double-1>', lambda e: self.editar_especialidad(tree))
        tree.bind('<Button-3>', lambda e: self.menu_contextual_especialidad(tree, e))
    
    # ---------- AGREGAR ESPECIALIDAD ----------
    def agregar_especialidad(self):
        """Abre ventana para agregar una especialidad"""
        ventana = tk.Toplevel(self.root)
        ventana.title("Agregar Especialidad")
        ventana.geometry("550x300")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()
        
        tk.Label(
            ventana,
            text="➕ AGREGAR ESPECIALIDAD",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0',
            fg='#4CAF50'
        ).pack(pady=10)
        
        frame = tk.Frame(ventana, bg='#f0f0f0')
        frame.pack(padx=30, pady=10)
        
        campos = [
            ('Código *', 'codigo'),
            ('Nombre *', 'nombre'),
            ('Descripción', 'descripcion')
        ]
        
        entries = {}
        for label_text, key in campos:
            f = tk.Frame(frame, bg='#f0f0f0')
            f.pack(fill='x', pady=3)
            tk.Label(f, text=label_text, width=15, anchor='w', bg='#f0f0f0', font=('Arial', 10)).pack(side='left')
            entry = tk.Entry(f, width=30, font=('Arial', 10))
            entry.pack(side='right')
            entries[key] = entry
        
        def guardar():
            if not entries['codigo'].get().strip() or not entries['nombre'].get().strip():
                messagebox.showerror("Error", "Código y Nombre son obligatorios.")
                return
            
            datos = {
                'codigo': entries['codigo'].get().strip(),
                'nombre': entries['nombre'].get().strip(),
                'descripcion': entries['descripcion'].get().strip()
            }
            
            resultado, info = registrar_especialidad(datos)
            if resultado:
                messagebox.showinfo("Éxito", f"✅ Especialidad agregada con éxito.\nID: {info}")
                ventana.destroy()
                self.mostrar_especialidades()
            else:
                messagebox.showerror("Error", f"❌ {info}")
        
        frame_botones = tk.Frame(ventana, bg='#f0f0f0')
        frame_botones.pack(pady=20)
        tk.Button(frame_botones, text="💾 Guardar", bg='#4CAF50', fg='white',
                 font=('Arial', 11, 'bold'), padx=20, pady=8, command=guardar).pack(side='left', padx=10)
        tk.Button(frame_botones, text="❌ Cancelar", bg='#f44336', fg='white',
                 font=('Arial', 11, 'bold'), padx=20, pady=8, command=ventana.destroy).pack(side='left', padx=10)
    
    # ---------- EDITAR ESPECIALIDAD ----------
    def editar_especialidad(self, tree):
        """Abre ventana para editar una especialidad"""
        seleccion = tree.selection()
        if not seleccion:
            return
        
        item = tree.item(seleccion[0])
        valores = item['values']
        if not valores:
            return
        
        especialidad_id = valores[0]
        
        ventana = tk.Toplevel(self.root)
        ventana.title("Editar Especialidad")
        ventana.geometry("550x300")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()
        
        tk.Label(
            ventana,
            text="✏️ EDITAR ESPECIALIDAD",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0',
            fg='#FF9800'
        ).pack(pady=10)
        
        frame = tk.Frame(ventana, bg='#f0f0f0')
        frame.pack(padx=30, pady=10)
        
        campos = [
            ('Código *', 'codigo', valores[1]),
            ('Nombre *', 'nombre', valores[2]),
            ('Descripción', 'descripcion', valores[3] or '')
        ]
        
        entries = {}
        for label_text, key, default in campos:
            f = tk.Frame(frame, bg='#f0f0f0')
            f.pack(fill='x', pady=3)
            tk.Label(f, text=label_text, width=15, anchor='w', bg='#f0f0f0', font=('Arial', 10)).pack(side='left')
            entry = tk.Entry(f, width=30, font=('Arial', 10))
            entry.insert(0, default)
            entry.pack(side='right')
            entries[key] = entry
        
        def guardar():
            if not entries['codigo'].get().strip() or not entries['nombre'].get().strip():
                messagebox.showerror("Error", "Código y Nombre son obligatorios.")
                return
            
            datos = {
                'codigo': entries['codigo'].get().strip(),
                'nombre': entries['nombre'].get().strip(),
                'descripcion': entries['descripcion'].get().strip()
            }
            
            resultado, mensaje = modificar_especialidad(especialidad_id, datos)
            if resultado:
                messagebox.showinfo("Éxito", mensaje)
                ventana.destroy()
                self.mostrar_especialidades()
            else:
                messagebox.showerror("Error", mensaje)
        
        frame_botones = tk.Frame(ventana, bg='#f0f0f0')
        frame_botones.pack(pady=20)
        tk.Button(frame_botones, text="💾 Guardar Cambios", bg='#FF9800', fg='white',
                 font=('Arial', 11, 'bold'), padx=20, pady=8, command=guardar).pack(side='left', padx=10)
        tk.Button(frame_botones, text="🗑️ Desactivar", bg='#f44336', fg='white',
                 font=('Arial', 11, 'bold'), padx=20, pady=8, 
                 command=lambda: self.desactivar_especialidad(especialidad_id, ventana)).pack(side='left', padx=10)
        tk.Button(frame_botones, text="❌ Cancelar", bg='#9E9E9E', fg='white',
                 font=('Arial', 11, 'bold'), padx=20, pady=8, command=ventana.destroy).pack(side='left', padx=10)
    
    def desactivar_especialidad(self, especialidad_id, ventana):
        """Desactiva una especialidad"""
        if messagebox.askyesno("Confirmar", "¿Está seguro de desactivar esta especialidad?"):
            resultado, mensaje = eliminar_especialidad(especialidad_id)
            if resultado:
                messagebox.showinfo("Éxito", mensaje)
                ventana.destroy()
                self.mostrar_especialidades()
            else:
                messagebox.showerror("Error", mensaje)
    
    # ---------- MENÚ CONTEXTUAL ----------
    def menu_contextual_especialidad(self, tree, event):
        """Muestra menú contextual para especialidades"""
        seleccion = tree.selection()
        if seleccion:
            menu = tk.Menu(self.root, tearoff=0)
            menu.add_command(label="✏️ Editar", command=lambda: self.editar_especialidad(tree))
            menu.add_command(label="🗑️ Desactivar", 
                           command=lambda: self.desactivar_especialidad(int(tree.item(seleccion[0])['values'][0]), None))
            menu.post(event.x_root, event.y_root)
    
    # ============================================================
    # SNOMED CT (Simplificado - Mismo patrón que Especialidades)
    # ============================================================
    
    def mostrar_snomed(self):
        """Muestra la gestión de SNOMED CT"""
        self.limpiar_contenido()
        
        tk.Label(
            self.frame_contenido,
            text="📋 GESTIÓN DE SNOMED CT",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0',
            fg='#2196F3'
        ).pack(pady=5)
        
        frame_botones = tk.Frame(self.frame_contenido, bg='#f0f0f0')
        frame_botones.pack(pady=5)
        
        tk.Button(
            frame_botones,
            text="➕ Agregar Término",
            bg='#2196F3',
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=5,
            command=self.agregar_snomed
        ).pack(side='left', padx=5)
        
        tk.Button(
            frame_botones,
            text="🔍 Buscar",
            bg='#4CAF50',
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=5,
            command=self.buscar_snomed
        ).pack(side='left', padx=5)
        
        tk.Button(
            frame_botones,
            text="🔄 Actualizar",
            bg='#FF9800',
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=5,
            command=self.mostrar_snomed
        ).pack(side='left', padx=5)
        
        frame_tabla = tk.Frame(self.frame_contenido, bg='#f0f0f0')
        frame_tabla.pack(fill='both', expand=True, pady=10)
        
        tree = ttk.Treeview(
            frame_tabla,
            columns=('ID', 'Código', 'Término', 'Categoría', 'Descripción'),
            show='headings',
            height=15
        )
        tree.heading('ID', text='ID')
        tree.heading('Código', text='Código')
        tree.heading('Término', text='Término')
        tree.heading('Categoría', text='Categoría')
        tree.heading('Descripción', text='Descripción')
        tree.column('ID', width=40, anchor='center')
        tree.column('Código', width=100, anchor='center')
        tree.column('Término', width=200)
        tree.column('Categoría', width=120)
        tree.column('Descripción', width=300)
        tree.pack(side='left', fill='both', expand=True)
        
        scrollbar = ttk.Scrollbar(frame_tabla, orient='vertical', command=tree.yview)
        scrollbar.pack(side='right', fill='y')
        tree.configure(yscrollcommand=scrollbar.set)
        
        snomed = listar_snomed()
        for s in snomed:
            tree.insert('', 'end', values=(s[0], s[1], s[2], s[4], s[3]))
    
    def agregar_snomed(self):
        """Abre ventana para agregar un término SNOMED CT"""
        ventana = tk.Toplevel(self.root)
        ventana.title("Agregar Término SNOMED CT")
        ventana.geometry("450x350")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()
        
        tk.Label(
            ventana,
            text="➕ AGREGAR TÉRMINO SNOMED CT",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0',
            fg='#2196F3'
        ).pack(pady=10)
        
        frame = tk.Frame(ventana, bg='#f0f0f0')
        frame.pack(padx=30, pady=10)
        
        campos = [
            ('Código *', 'codigo'),
            ('Término *', 'termino'),
            ('Categoría *', 'categoria'),
            ('Descripción', 'descripcion')
        ]
        
        entries = {}
        for label_text, key in campos:
            f = tk.Frame(frame, bg='#f0f0f0')
            f.pack(fill='x', pady=3)
            tk.Label(f, text=label_text, width=15, anchor='w', bg='#f0f0f0', font=('Arial', 10)).pack(side='left')
            entry = tk.Entry(f, width=30, font=('Arial', 10))
            entry.pack(side='right')
            entries[key] = entry
        
        def guardar():
            obligatorios = ['codigo', 'termino', 'categoria']
            for campo in obligatorios:
                if not entries[campo].get().strip():
                    messagebox.showerror("Error", f"El campo {campo} es obligatorio.")
                    return
            
            datos = {
                'codigo': entries['codigo'].get().strip(),
                'termino': entries['termino'].get().strip(),
                'categoria': entries['categoria'].get().strip(),
                'descripcion': entries['descripcion'].get().strip()
            }
            
            resultado, info = registrar_snomed(datos)
            if resultado:
                messagebox.showinfo("Éxito", f"✅ Término agregado con éxito.\nID: {info}")
                ventana.destroy()
                self.mostrar_snomed()
            else:
                messagebox.showerror("Error", f"❌ {info}")
        
        frame_botones = tk.Frame(ventana, bg='#f0f0f0')
        frame_botones.pack(pady=20)
        tk.Button(frame_botones, text="💾 Guardar", bg='#2196F3', fg='white',
                 font=('Arial', 11, 'bold'), padx=20, pady=8, command=guardar).pack(side='left', padx=10)
        tk.Button(frame_botones, text="❌ Cancelar", bg='#f44336', fg='white',
                 font=('Arial', 11, 'bold'), padx=20, pady=8, command=ventana.destroy).pack(side='left', padx=10)
    
    def buscar_snomed(self):
        """Abre ventana para buscar términos SNOMED CT"""
        ventana = tk.Toplevel(self.root)
        ventana.title("Buscar SNOMED CT")
        ventana.geometry("600x400")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()
        
        tk.Label(
            ventana,
            text="🔍 BUSCAR TÉRMINOS SNOMED CT",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0',
            fg='#2196F3'
        ).pack(pady=10)
        
        frame_buscar = tk.Frame(ventana, bg='#f0f0f0')
        frame_buscar.pack(pady=10)
        
        tk.Label(frame_buscar, text="Buscar:", font=('Arial', 11), bg='#f0f0f0').pack(side='left', padx=10)
        entry_buscar = tk.Entry(frame_buscar, font=('Arial', 11), width=30)
        entry_buscar.pack(side='left', padx=10)
        
        frame_resultados = tk.Frame(ventana, bg='#f0f0f0')
        frame_resultados.pack(fill='both', expand=True, padx=20, pady=10)
        
        tree = ttk.Treeview(
            frame_resultados,
            columns=('Código', 'Término', 'Categoría', 'Descripción'),
            show='headings',
            height=10
        )
        tree.heading('Código', text='Código')
        tree.heading('Término', text='Término')
        tree.heading('Categoría', text='Categoría')
        tree.heading('Descripción', text='Descripción')
        tree.column('Código', width=100)
        tree.column('Término', width=200)
        tree.column('Categoría', width=120)
        tree.column('Descripción', width=200)
        tree.pack(side='left', fill='both', expand=True)
        
        scrollbar = ttk.Scrollbar(frame_resultados, orient='vertical', command=tree.yview)
        scrollbar.pack(side='right', fill='y')
        tree.configure(yscrollcommand=scrollbar.set)
        
        def buscar():
            for item in tree.get_children():
                tree.delete(item)
            
            termino = entry_buscar.get().strip()
            if not termino:
                messagebox.showerror("Error", "Ingrese un término para buscar.")
                return
            
            resultados = buscar_snomed_por_termino(termino)
            for r in resultados:
                tree.insert('', 'end', values=(r[1], r[2], r[4], r[3]))
            
            if not resultados:
                messagebox.showinfo("Sin resultados", "No se encontraron términos que coincidan.")
        
        entry_buscar.bind('<Return>', lambda e: buscar())
        
        tk.Button(
            ventana,
            text="🔍 Buscar",
            bg='#2196F3',
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=20,
            pady=8,
            command=buscar
        ).pack(pady=10)
    
    # ============================================================
    # FÁRMACOS (Simplificado - Mismo patrón)
    # ============================================================
    
    def mostrar_farmacos(self):
        """Muestra la gestión de fármacos"""
        self.limpiar_contenido()
        
        tk.Label(
            self.frame_contenido,
            text="💊 GESTIÓN DE FÁRMACOS",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0',
            fg='#FF9800'
        ).pack(pady=5)
        
        frame_botones = tk.Frame(self.frame_contenido, bg='#f0f0f0')
        frame_botones.pack(pady=5)
        
        tk.Button(
            frame_botones,
            text="➕ Agregar Fármaco",
            bg='#FF9800',
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=5,
            command=self.agregar_farmaco
        ).pack(side='left', padx=5)
        
        tk.Button(
            frame_botones,
            text="🔄 Actualizar",
            bg='#2196F3',
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=5,
            command=self.mostrar_farmacos
        ).pack(side='left', padx=5)
        
        frame_tabla = tk.Frame(self.frame_contenido, bg='#f0f0f0')
        frame_tabla.pack(fill='both', expand=True, pady=10)
        
        tree = ttk.Treeview(
            frame_tabla,
            columns=('ID', 'Código', 'Nombre', 'Principio Activo', 'Presentación', 'Concentración', 'Vía'),
            show='headings',
            height=15
        )
        tree.heading('ID', text='ID')
        tree.heading('Código', text='Código')
        tree.heading('Nombre', text='Nombre')
        tree.heading('Principio Activo', text='Principio Activo')
        tree.heading('Presentación', text='Presentación')
        tree.heading('Concentración', text='Concentración')
        tree.heading('Vía', text='Vía Adm.')
        tree.column('ID', width=40, anchor='center')
        tree.column('Código', width=80, anchor='center')
        tree.column('Nombre', width=180)
        tree.column('Principio Activo', width=150)
        tree.column('Presentación', width=100)
        tree.column('Concentración', width=100)
        tree.column('Vía', width=100)
        tree.pack(side='left', fill='both', expand=True)
        
        scrollbar = ttk.Scrollbar(frame_tabla, orient='vertical', command=tree.yview)
        scrollbar.pack(side='right', fill='y')
        tree.configure(yscrollcommand=scrollbar.set)
        
        farmacos = listar_farmacos()
        for f in farmacos:
            tree.insert('', 'end', values=(f[0], f[1], f[2], f[3] or '', f[4] or '', f[5] or '', f[6] or ''))
    
    def agregar_farmaco(self):
        """Abre ventana para agregar un fármaco"""
        ventana = tk.Toplevel(self.root)
        ventana.title("Agregar Fármaco")
        ventana.geometry("500x450")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()
        
        tk.Label(
            ventana,
            text="➕ AGREGAR FÁRMACO",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0',
            fg='#FF9800'
        ).pack(pady=10)
        
        frame = tk.Frame(ventana, bg='#f0f0f0')
        frame.pack(padx=30, pady=10)
        
        campos = [
            ('Código *', 'codigo'),
            ('Nombre *', 'nombre'),
            ('Principio Activo', 'principio_activo'),
            ('Presentación', 'presentacion'),
            ('Concentración', 'concentracion'),
            ('Vía Administración', 'via_administracion')
        ]
        
        entries = {}
        for label_text, key in campos:
            f = tk.Frame(frame, bg='#f0f0f0')
            f.pack(fill='x', pady=3)
            tk.Label(f, text=label_text, width=18, anchor='w', bg='#f0f0f0', font=('Arial', 10)).pack(side='left')
            entry = tk.Entry(f, width=28, font=('Arial', 10))
            entry.pack(side='right')
            entries[key] = entry
        
        def guardar():
            if not entries['codigo'].get().strip() or not entries['nombre'].get().strip():
                messagebox.showerror("Error", "Código y Nombre son obligatorios.")
                return
            
            datos = {
                'codigo': entries['codigo'].get().strip(),
                'nombre': entries['nombre'].get().strip(),
                'principio_activo': entries['principio_activo'].get().strip(),
                'presentacion': entries['presentacion'].get().strip(),
                'concentracion': entries['concentracion'].get().strip(),
                'via_administracion': entries['via_administracion'].get().strip()
            }
            
            resultado, info = registrar_farmaco(datos)
            if resultado:
                messagebox.showinfo("Éxito", f"✅ Fármaco agregado con éxito.\nID: {info}")
                ventana.destroy()
                self.mostrar_farmacos()
            else:
                messagebox.showerror("Error", f"❌ {info}")
        
        frame_botones = tk.Frame(ventana, bg='#f0f0f0')
        frame_botones.pack(pady=20)
        tk.Button(frame_botones, text="💾 Guardar", bg='#FF9800', fg='white',
                 font=('Arial', 11, 'bold'), padx=20, pady=8, command=guardar).pack(side='left', padx=10)
        tk.Button(frame_botones, text="❌ Cancelar", bg='#f44336', fg='white',
                 font=('Arial', 11, 'bold'), padx=20, pady=8, command=ventana.destroy).pack(side='left', padx=10)


# ================================================================
# PUNTO DE ENTRADA
# ================================================================

if __name__ == "__main__":
    root = tk.Tk()
    app = AppTablasMaestras(root)
    root.mainloop()
