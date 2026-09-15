# ================================================================
# prescripciones_app.py
# SPRINT 3 - MÓDULO DE PRESCRIPCIÓN DE MEDICAMENTOS
# ================================================================
#
# FUNCIONALIDADES:
#   ✅ Registrar prescripción (CREATE)
#   ✅ Buscar prescripciones por paciente (READ)
#   ✅ Ver detalle de prescripción (READ)
#   ✅ Anular prescripción (DELETE lógico)
#   ✅ Ver listado completo de prescripciones
#   ✅ Selectores de Paciente, Profesional, Fármaco y SNOMED
#   ✅ Interfaz gráfica con Tkinter
#   ✅ Validaciones completas
#   ✅ Debug integrado
#
# ESTRUCTURA DE TABLA:
#   Prescripciones (
#       id INTEGER PRIMARY KEY AUTOINCREMENT,
#       paciente_id INTEGER NOT NULL,
#       profesional_id INTEGER NOT NULL,
#       farmaco_id INTEGER NOT NULL,
#       snomed_id INTEGER,
#       dosis TEXT NOT NULL,
#       via_administracion TEXT NOT NULL,
#       frecuencia TEXT NOT NULL,
#       duracion TEXT,
#       cantidad INTEGER,
#       indicaciones TEXT,
#       fecha_prescripcion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#       fecha_inicio TEXT,
#       fecha_fin TEXT,
#       activo INTEGER DEFAULT 1,
#       FOREIGN KEY (paciente_id) REFERENCES Pacientes(id),
#       FOREIGN KEY (profesional_id) REFERENCES Profesionales(id),
#       FOREIGN KEY (farmaco_id) REFERENCES Farmacos(id),
#       FOREIGN KEY (snomed_id) REFERENCES SnomedCT(id)
#   )
# ================================================================

import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime

# ================================================================
# CAPA DE ACCESO A DATOS (BACKEND)
# ================================================================

def conectar_bd():
    """Establece conexión con la base de datos Salud.db"""
    return sqlite3.connect('BD/Salud.db')


# -------------------- FUNCIONES DE CONSULTA --------------------

def obtener_pacientes_selector():
    """Obtiene lista de pacientes para selector (combobox)"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT id, dni, nombre, apellido 
            FROM Pacientes 
            ORDER BY apellido, nombre
        """)
        resultados = cursor.fetchall()
        conexion.close()
        return resultados
    except Exception as e:
        print(f"[ERROR] Error al obtener pacientes: {e}")
        return []


def obtener_profesionales_selector():
    """Obtiene lista de profesionales para selector (combobox)"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT p.id, p.dni, p.nombre, p.apellido, e.nombre as especialidad
            FROM Profesionales p
            LEFT JOIN Especialidades e ON p.especialidad_id = e.id
            ORDER BY p.apellido, p.nombre
        """)
        resultados = cursor.fetchall()
        conexion.close()
        return resultados
    except Exception as e:
        print(f"[ERROR] Error al obtener profesionales: {e}")
        return []


def obtener_farmacos_selector():
    """Obtiene lista de fármacos activos para selector (combobox)"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT id, codigo, nombre, principio_activo, presentacion, concentracion
            FROM Farmacos 
            WHERE activo = 1
            ORDER BY nombre
        """)
        resultados = cursor.fetchall()
        conexion.close()
        return resultados
    except Exception as e:
        print(f"[ERROR] Error al obtener fármacos: {e}")
        return []


def obtener_snomed_selector():
    """Obtiene lista de términos SNOMED para selector (combobox)"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT id, codigo, termino, categoria
            FROM SnomedCT 
            WHERE activo = 1 
            ORDER BY termino
        """)
        resultados = cursor.fetchall()
        conexion.close()
        return resultados
    except Exception as e:
        print(f"[ERROR] Error al obtener SNOMED: {e}")
        return []


def obtener_paciente_por_dni(dni):
    """Busca un paciente por DNI"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("SELECT id, dni, nombre, apellido FROM Pacientes WHERE dni = ?", (dni,))
        resultado = cursor.fetchone()
        conexion.close()
        return resultado
    except Exception as e:
        print(f"[ERROR] Error al buscar paciente: {e}")
        return None


# -------------------- CRUD DE PRESCRIPCIONES --------------------

def registrar_prescripcion(datos):
    """
    Registra una nueva prescripción (CREATE)
    
    Parámetros:
        datos: diccionario con los campos:
            - paciente_id (int): obligatorio
            - profesional_id (int): obligatorio
            - farmaco_id (int): obligatorio
            - snomed_id (int): opcional
            - dosis (str): obligatorio
            - via_administracion (str): obligatorio
            - frecuencia (str): obligatorio
            - duracion (str): opcional
            - cantidad (int): opcional
            - indicaciones (str): opcional
            - fecha_inicio (str): opcional, formato YYYY-MM-DD
            - fecha_fin (str): opcional, formato YYYY-MM-DD
    
    Retorna:
        (True, id_nuevo) si tuvo éxito
        (False, mensaje_error) si falló
    """
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        
        cursor.execute("""
            INSERT INTO Prescripciones 
            (paciente_id, profesional_id, farmaco_id, snomed_id,
             dosis, via_administracion, frecuencia, duracion,
             cantidad, indicaciones, fecha_inicio, fecha_fin, activo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datos['paciente_id'],
            datos['profesional_id'],
            datos['farmaco_id'],
            datos.get('snomed_id'),
            datos['dosis'],
            datos['via_administracion'],
            datos['frecuencia'],
            datos.get('duracion', ''),
            datos.get('cantidad'),
            datos.get('indicaciones', ''),
            datos.get('fecha_inicio'),
            datos.get('fecha_fin'),
            1  # activo
        ))
        
        conexion.commit()
        nuevo_id = cursor.lastrowid
        conexion.close()
        print(f"[DEBUG] Prescripción registrada con ID: {nuevo_id}")
        return True, nuevo_id
        
    except Exception as e:
        print(f"[ERROR] Error en registrar_prescripcion: {e}")
        return False, f"❌ Error al registrar prescripción: {e}"


def listar_prescripciones(activas=True):
    """
    Lista todas las prescripciones con datos relacionados
    
    Retorna: Lista de tuplas con datos completos
    """
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        
        where = "WHERE p.activo = 1" if activas else "WHERE p.activo = 0"
        
        cursor.execute(f"""
            SELECT 
                p.id,
                p.fecha_prescripcion,
                pac.nombre || ' ' || pac.apellido as paciente,
                pac.dni as paciente_dni,
                prof.nombre || ' ' || prof.apellido as profesional,
                f.nombre as farmaco,
                f.codigo as farmaco_codigo,
                p.dosis,
                p.via_administracion,
                p.frecuencia,
                p.duracion,
                p.cantidad,
                p.indicaciones,
                s.termino as diagnostico,
                p.activo,
                p.fecha_inicio,
                p.fecha_fin
            FROM Prescripciones p
            LEFT JOIN Pacientes pac ON p.paciente_id = pac.id
            LEFT JOIN Profesionales prof ON p.profesional_id = prof.id
            LEFT JOIN Farmacos f ON p.farmaco_id = f.id
            LEFT JOIN SnomedCT s ON p.snomed_id = s.id
            {where}
            ORDER BY p.fecha_prescripcion DESC
        """)
        
        resultados = cursor.fetchall()
        conexion.close()
        print(f"[DEBUG] Prescripciones cargadas: {len(resultados)}")
        return resultados
        
    except Exception as e:
        print(f"[ERROR] Error en listar_prescripciones: {e}")
        return []


def buscar_prescripciones_por_paciente(paciente_id):
    """
    Busca prescripciones de un paciente específico
    """
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT 
                p.id,
                p.fecha_prescripcion,
                f.nombre as farmaco,
                f.codigo as farmaco_codigo,
                p.dosis,
                p.via_administracion,
                p.frecuencia,
                p.duracion,
                p.cantidad,
                p.indicaciones,
                s.termino as diagnostico,
                p.activo,
                prof.nombre || ' ' || prof.apellido as profesional
            FROM Prescripciones p
            LEFT JOIN Farmacos f ON p.farmaco_id = f.id
            LEFT JOIN SnomedCT s ON p.snomed_id = s.id
            LEFT JOIN Profesionales prof ON p.profesional_id = prof.id
            WHERE p.paciente_id = ?
            ORDER BY p.fecha_prescripcion DESC
        """, (paciente_id,))
        
        resultados = cursor.fetchall()
        conexion.close()
        return resultados
        
    except Exception as e:
        print(f"[ERROR] Error en buscar_prescripciones_por_paciente: {e}")
        return []


def buscar_prescripcion_por_id(prescripcion_id):
    """
    Busca una prescripción por su ID
    """
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT 
                p.*,
                pac.nombre || ' ' || pac.apellido as paciente_nombre,
                pac.dni as paciente_dni,
                prof.nombre || ' ' || prof.apellido as profesional_nombre,
                prof.dni as profesional_dni,
                f.nombre as farmaco_nombre,
                f.codigo as farmaco_codigo,
                s.termino as diagnostico,
                s.codigo as diagnostico_codigo
            FROM Prescripciones p
            LEFT JOIN Pacientes pac ON p.paciente_id = pac.id
            LEFT JOIN Profesionales prof ON p.profesional_id = prof.id
            LEFT JOIN Farmacos f ON p.farmaco_id = f.id
            LEFT JOIN SnomedCT s ON p.snomed_id = s.id
            WHERE p.id = ?
        """, (prescripcion_id,))
        
        resultado = cursor.fetchone()
        conexion.close()
        
        if resultado:
            return {
                'id': resultado[0],
                'paciente_id': resultado[1],
                'profesional_id': resultado[2],
                'farmaco_id': resultado[3],
                'snomed_id': resultado[4],
                'dosis': resultado[5],
                'via_administracion': resultado[6],
                'frecuencia': resultado[7],
                'duracion': resultado[8] or '',
                'cantidad': resultado[9] or '',
                'indicaciones': resultado[10] or '',
                'fecha_prescripcion': resultado[11],
                'fecha_inicio': resultado[12] or '',
                'fecha_fin': resultado[13] or '',
                'activo': resultado[14],
                'paciente_nombre': resultado[15] or 'No especificado',
                'paciente_dni': resultado[16] or 'No especificado',
                'profesional_nombre': resultado[17] or 'No especificado',
                'profesional_dni': resultado[18] or 'No especificado',
                'farmaco_nombre': resultado[19] or 'No especificado',
                'farmaco_codigo': resultado[20] or 'No especificado',
                'diagnostico': resultado[21] or 'No especificado',
                'diagnostico_codigo': resultado[22] or 'No especificado'
            }
        return None
        
    except Exception as e:
        print(f"[ERROR] Error en buscar_prescripcion_por_id: {e}")
        return None


def anular_prescripcion(prescripcion_id):
    """
    Anula una prescripción (DELETE lógico - activo = 0)
    """
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        
        cursor.execute("UPDATE Prescripciones SET activo = 0 WHERE id = ?", (prescripcion_id,))
        conexion.commit()
        afectados = cursor.rowcount
        conexion.close()
        
        if afectados > 0:
            print(f"[DEBUG] Prescripción {prescripcion_id} anulada")
            return True, "✅ Prescripción anulada correctamente."
        return False, "❌ No se encontró la prescripción."
        
    except Exception as e:
        print(f"[ERROR] Error en anular_prescripcion: {e}")
        return False, f"❌ Error: {e}"


# ================================================================
# CAPA DE PRESENTACIÓN (FRONTEND)
# ================================================================

class AppPrescripciones:
    """Aplicación de gestión de prescripciones"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("OpenHIS-UNLaM - Prescripción de Medicamentos")
        self.root.geometry("1100x700")
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
            text="💊 PRESCRIPCIÓN DE MEDICAMENTOS",
            font=('Arial', 18, 'bold'),
            bg='#f0f0f0',
            fg='#003366'
        )
        titulo.pack(pady=5)
        
        subtitulo = tk.Label(
            self.frame_principal,
            text="Hospital Universitario San Justo - Sistema de Prescripciones",
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
        
        # Botón Nueva Prescripción
        self.btn_nueva = tk.Button(
            frame_botones,
            text="💊 Nueva Prescripción",
            bg='#4CAF50',
            fg='white',
            command=self.abrir_nueva_prescripcion,
            **estilo_boton
        )
        self.btn_nueva.pack(side='left', padx=3)
        
        # Botón Buscar por Paciente
        self.btn_buscar_paciente = tk.Button(
            frame_botones,
            text="🔍 Buscar por Paciente",
            bg='#2196F3',
            fg='white',
            command=self.buscar_por_paciente,
            **estilo_boton
        )
        self.btn_buscar_paciente.pack(side='left', padx=3)
        
        # Botón Ver Todas
        self.btn_ver_todas = tk.Button(
            frame_botones,
            text="📊 Ver Todas",
            bg='#607D8B',
            fg='white',
            command=self.ver_todas,
            **estilo_boton
        )
        self.btn_ver_todas.pack(side='left', padx=3)
        
        # Botón Ver Anuladas
        self.btn_ver_anuladas = tk.Button(
            frame_botones,
            text="🚫 Ver Anuladas",
            bg='#f44336',
            fg='white',
            command=self.ver_anuladas,
            **estilo_boton
        )
        self.btn_ver_anuladas.pack(side='left', padx=3)
        
        # Botón Debug
        self.btn_debug = tk.Button(
            frame_botones,
            text="🐛 Debug",
            bg='#9C27B0',
            fg='white',
            command=self.debug_prescripciones,
            **estilo_boton
        )
        self.btn_debug.pack(side='left', padx=3)
        
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
        
        # ---------- TABLA DE PRESCRIPCIONES ----------
        frame_tabla = tk.Frame(self.frame_principal, bg='#f0f0f0')
        frame_tabla.pack(fill='both', expand=True, pady=10)
        
        self.tree = ttk.Treeview(
            frame_tabla,
            columns=(
                'ID', 'Fecha', 'Paciente', 'DNI', 'Profesional',
                'Fármaco', 'Dosis', 'Vía', 'Frecuencia', 'Diagnóstico', 'Estado'
            ),
            show='headings',
            height=12,
            selectmode='browse'
        )
        
        columnas = [
            ('ID', 'ID', 40, 'center'),
            ('Fecha', 'Fecha', 130, 'center'),
            ('Paciente', 'Paciente', 160, 'w'),
            ('DNI', 'DNI', 90, 'center'),
            ('Profesional', 'Profesional', 140, 'w'),
            ('Fármaco', 'Fármaco', 150, 'w'),
            ('Dosis', 'Dosis', 70, 'center'),
            ('Vía', 'Vía', 80, 'center'),
            ('Frecuencia', 'Frecuencia', 90, 'center'),
            ('Diagnóstico', 'Diagnóstico', 140, 'w'),
            ('Estado', 'Estado', 70, 'center')
        ]
        
        for col, heading, width, anchor in columnas:
            self.tree.heading(col, text=heading)
            self.tree.column(col, width=width, anchor=anchor)
        
        self.tree.pack(side='left', fill='both', expand=True)
        
        scrollbar = ttk.Scrollbar(frame_tabla, orient='vertical', command=self.tree.yview)
        scrollbar.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # Evento doble clic para ver detalle
        self.tree.bind('<Double-1>', self.on_doble_click)
        
        # ---------- ESTADO ----------
        self.label_estado = tk.Label(
            self.frame_principal,
            text="✅ Sistema listo",
            font=('Arial', 9),
            bg='#f0f0f0',
            fg='#666666'
        )
        self.label_estado.pack(side='bottom', pady=5)
        
        # Cargar todas las prescripciones al iniciar
        self.ver_todas()
    
    # ============================================================
    # MÉTODOS DE LA APLICACIÓN
    # ============================================================
    
    # ---------- VER TODAS ----------
    def ver_todas(self):
        """Actualiza la tabla con todas las prescripciones activas"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        prescripciones = listar_prescripciones(activas=True)
        print(f"[DEBUG] ver_todas: {len(prescripciones)} prescripciones activas")
        
        if not prescripciones:
            self.label_resultados.config(text="⚠️ No hay prescripciones activas")
            return
        
        for p in prescripciones:
            estado = "Activa" if p[14] == 1 else "Anulada"
            self.tree.insert('', 'end', values=(
                p[0],           # ID
                p[1][:16] if p[1] else '',  # Fecha
                p[2] or 'N/A',  # Paciente
                p[3] or 'N/A',  # DNI Paciente
                p[4] or 'N/A',  # Profesional
                p[5] or 'N/A',  # Fármaco
                p[7] or '-',    # Dosis
                p[8] or '-',    # Vía
                p[9] or '-',    # Frecuencia
                p[13] or '-',   # Diagnóstico
                estado          # Estado
            ))
        
        self.label_resultados.config(text=f"📊 Total de prescripciones activas: {len(prescripciones)}")
    
    def ver_anuladas(self):
        """Actualiza la tabla con todas las prescripciones anuladas"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        prescripciones = listar_prescripciones(activas=False)
        print(f"[DEBUG] ver_anuladas: {len(prescripciones)} prescripciones anuladas")
        
        if not prescripciones:
            self.label_resultados.config(text="⚠️ No hay prescripciones anuladas")
            return
        
        for p in prescripciones:
            estado = "Anulada"
            self.tree.insert('', 'end', values=(
                p[0], p[1][:16] if p[1] else '',
                p[2] or 'N/A', p[3] or 'N/A',
                p[4] or 'N/A', p[5] or 'N/A',
                p[7] or '-', p[8] or '-', p[9] or '-',
                p[13] or '-', estado
            ))
        
        self.label_resultados.config(text=f"📊 Total de prescripciones anuladas: {len(prescripciones)}")
    
    # ---------- DEBUG ----------
    def debug_prescripciones(self):
        """Muestra información de debug en consola"""
        print("\n" + "="*70)
        print("🐛 DEBUG - PRESCRIPCIONES")
        print("="*70)
        
        try:
            conexion = conectar_bd()
            cursor = conexion.cursor()
            
            # Verificar estructura
            print("\n📋 ESTRUCTURA DE LA TABLA:")
            cursor.execute("PRAGMA table_info(Prescripciones)")
            for col in cursor.fetchall():
                print(f"   {col[1]} ({col[2]})")
            
            # Verificar datos
            cursor.execute("SELECT COUNT(*) FROM Prescripciones")
            total = cursor.fetchone()[0]
            print(f"\n📊 TOTAL DE REGISTROS: {total}")
            
            if total > 0:
                cursor.execute("SELECT id, paciente_id, profesional_id, farmaco_id, activo FROM Prescripciones LIMIT 5")
                for row in cursor.fetchall():
                    print(f"   ID: {row[0]}, Paciente: {row[1]}, Profesional: {row[2]}, Fármaco: {row[3]}, Activo: {row[4]}")
            
            # Verificar dependencias
            cursor.execute("SELECT COUNT(*) FROM Pacientes")
            print(f"\n👤 Pacientes disponibles: {cursor.fetchone()[0]}")
            
            cursor.execute("SELECT COUNT(*) FROM Profesionales")
            print(f"👨‍⚕️ Profesionales disponibles: {cursor.fetchone()[0]}")
            
            cursor.execute("SELECT COUNT(*) FROM Farmacos WHERE activo = 1")
            print(f"💊 Fármacos activos: {cursor.fetchone()[0]}")
            
            cursor.execute("SELECT COUNT(*) FROM SnomedCT WHERE activo = 1")
            print(f"📋 SNOMED activos: {cursor.fetchone()[0]}")
            
            conexion.close()
            
        except Exception as e:
            print(f"❌ ERROR en debug: {e}")
        
        print("\n" + "="*70)
        messagebox.showinfo("Debug", "Información de debug mostrada en la consola.")
    
    # ---------- BUSCAR POR PACIENTE ----------
    def buscar_por_paciente(self):
        """Abre ventana para buscar prescripciones por paciente"""
        ventana = tk.Toplevel(self.root)
        ventana.title("Buscar Prescripciones por Paciente")
        ventana.geometry("450x200")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()
        ventana.resizable(False, False)
        
        tk.Label(
            ventana,
            text="🔍 BUSCAR POR PACIENTE",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0',
            fg='#003366'
        ).pack(pady=15)
        
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
        
        def buscar():
            dni = entry_dni.get().strip()
            if not dni:
                messagebox.showerror("Error", "Ingrese un DNI.")
                return
            
            paciente = obtener_paciente_por_dni(dni)
            if not paciente:
                messagebox.showerror("Error", "Paciente no encontrado.")
                return
            
            ventana.destroy()
            self.mostrar_prescripciones_paciente(paciente)
        
        entry_dni.bind('<Return>', lambda e: buscar())
        
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
    
    def mostrar_prescripciones_paciente(self, paciente):
        """Muestra las prescripciones de un paciente específico"""
        ventana = tk.Toplevel(self.root)
        ventana.title(f"Prescripciones - {paciente[2]} {paciente[3]}")
        ventana.geometry("1000x500")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()
        
        tk.Label(
            ventana,
            text=f"💊 PRESCRIPCIONES DE {paciente[2]} {paciente[3]} (DNI: {paciente[1]})",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0',
            fg='#003366'
        ).pack(pady=10)
        
        frame_tabla = tk.Frame(ventana, bg='#f0f0f0')
        frame_tabla.pack(fill='both', expand=True, padx=20, pady=10)
        
        tree = ttk.Treeview(
            frame_tabla,
            columns=('ID', 'Fecha', 'Fármaco', 'Dosis', 'Vía', 'Frecuencia', 'Profesional', 'Diagnóstico', 'Estado'),
            show='headings',
            height=10
        )
        
        columnas = [
            ('ID', 'ID', 40, 'center'),
            ('Fecha', 'Fecha', 130, 'center'),
            ('Fármaco', 'Fármaco', 160, 'w'),
            ('Dosis', 'Dosis', 70, 'center'),
            ('Vía', 'Vía', 80, 'center'),
            ('Frecuencia', 'Frecuencia', 90, 'center'),
            ('Profesional', 'Profesional', 150, 'w'),
            ('Diagnóstico', 'Diagnóstico', 150, 'w'),
            ('Estado', 'Estado', 70, 'center')
        ]
        
        for col, heading, width, anchor in columnas:
            tree.heading(col, text=heading)
            tree.column(col, width=width, anchor=anchor)
        
        tree.pack(side='left', fill='both', expand=True)
        
        scrollbar = ttk.Scrollbar(frame_tabla, orient='vertical', command=tree.yview)
        scrollbar.pack(side='right', fill='y')
        tree.configure(yscrollcommand=scrollbar.set)
        
        # Cargar datos
        prescripciones = buscar_prescripciones_por_paciente(paciente[0])
        for p in prescripciones:
            estado = "Activa" if p[11] == 1 else "Anulada"
            tree.insert('', 'end', values=(
                p[0], p[1][:16] if p[1] else '',
                p[2] or 'N/A', p[4] or '-', p[5] or '-', p[6] or '-',
                p[12] or 'N/A', p[10] or '-', estado
            ))
        
        total_activas = len([p for p in prescripciones if p[11] == 1])
        tk.Label(
            ventana,
            text=f"Total: {len(prescripciones)} prescripciones ({total_activas} activas)",
            font=('Arial', 10),
            bg='#f0f0f0',
            fg='#666666'
        ).pack(pady=5)
        
        tk.Button(
            ventana,
            text="❌ Cerrar",
            bg='#f44336',
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=20,
            pady=8,
            command=ventana.destroy
        ).pack(pady=10)
    
    # ---------- NUEVA PRESCRIPCIÓN ----------
    def abrir_nueva_prescripcion(self):
        """Abre ventana para registrar una nueva prescripción"""
        ventana = tk.Toplevel(self.root)
        ventana.title("Nueva Prescripción")
        ventana.geometry("750x700")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()
        ventana.resizable(False, False)
        
        # ---------- TÍTULO ----------
        tk.Label(
            ventana,
            text="💊 NUEVA PRESCRIPCIÓN",
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
        
        # ---------- OBTENER DATOS PARA SELECTORES ----------
        pacientes = obtener_pacientes_selector()
        if not pacientes:
            messagebox.showwarning("Advertencia", 
                "No hay pacientes cargados en el sistema.\n"
                "Por favor, cargue pacientes primero.")
            ventana.destroy()
            return
        
        profesionales = obtener_profesionales_selector()
        if not profesionales:
            messagebox.showwarning("Advertencia", 
                "No hay profesionales cargados en el sistema.\n"
                "Por favor, cargue profesionales primero.")
            ventana.destroy()
            return
        
        farmacos = obtener_farmacos_selector()
        if not farmacos:
            messagebox.showwarning("Advertencia", 
                "No hay fármacos cargados en el sistema.\n"
                "Por favor, cargue fármacos primero en el módulo de Tablas Maestras.")
            ventana.destroy()
            return
        
        snomed = obtener_snomed_selector()
        
        # ---------- CAMPOS DEL FORMULARIO ----------
        frame_campos = tk.Frame(ventana, bg='#f0f0f0')
        frame_campos.pack(padx=30, pady=10, fill='both', expand=True)
        
        # Función helper para crear combobox
        def crear_combobox(parent, valores, texto_inicial="Seleccione..."):
            combo = ttk.Combobox(parent, width=40, font=('Arial', 10), state='readonly')
            if valores:
                combo['values'] = valores
                combo.current(0)
            else:
                combo['values'] = [texto_inicial]
                combo.current(0)
            return combo
        
        # --- Paciente ---
        frame = tk.Frame(frame_campos, bg='#f0f0f0')
        frame.pack(fill='x', pady=4)
        tk.Label(frame, text="Paciente *:", width=20, anchor='w', bg='#f0f0f0', font=('Arial', 10, 'bold')).pack(side='left')
        valores_pacientes = [f"{p[0]} - {p[2]} {p[3]} (DNI: {p[1]})" for p in pacientes]
        combo_paciente = crear_combobox(frame, valores_pacientes)
        combo_paciente.pack(side='right')
        
        # --- Profesional ---
        frame = tk.Frame(frame_campos, bg='#f0f0f0')
        frame.pack(fill='x', pady=4)
        tk.Label(frame, text="Profesional *:", width=20, anchor='w', bg='#f0f0f0', font=('Arial', 10, 'bold')).pack(side='left')
        valores_prof = [f"{p[0]} - {p[2]} {p[3]} ({p[4] or 'Sin especialidad'})" for p in profesionales]
        combo_prof = crear_combobox(frame, valores_prof)
        combo_prof.pack(side='right')
        
        # --- Fármaco ---
        frame = tk.Frame(frame_campos, bg='#f0f0f0')
        frame.pack(fill='x', pady=4)
        tk.Label(frame, text="Fármaco *:", width=20, anchor='w', bg='#f0f0f0', font=('Arial', 10, 'bold')).pack(side='left')
        valores_farmacos = [f"{f[0]} - {f[1]} {f[2]} ({f[3] or 'N/A'})" for f in farmacos]
        combo_farmaco = crear_combobox(frame, valores_farmacos)
        combo_farmaco.pack(side='right')
        
        # --- Diagnóstico (SNOMED) - Opcional ---
        frame = tk.Frame(frame_campos, bg='#f0f0f0')
        frame.pack(fill='x', pady=4)
        tk.Label(frame, text="Diagnóstico (SNOMED):", width=20, anchor='w', bg='#f0f0f0', font=('Arial', 10)).pack(side='left')
        if snomed:
            valores_snomed = [f"{s[0]} - {s[1]} {s[2]} ({s[3]})" for s in snomed]
            combo_snomed = crear_combobox(frame, valores_snomed)
        else:
            combo_snomed = ttk.Combobox(frame, width=40, font=('Arial', 10), state='readonly')
            combo_snomed['values'] = ['No hay diagnósticos cargados']
            combo_snomed.current(0)
        combo_snomed.pack(side='right')
        
        # --- Campos de texto en grid 2 columnas ---
        frame_detalles = tk.Frame(frame_campos, bg='#f0f0f0')
        frame_detalles.pack(fill='x', pady=10)
        
        campos_texto = [
            ('Dosis *', 'dosis', 0, 0),
            ('Vía Administración *', 'via', 0, 1),
            ('Frecuencia *', 'frecuencia', 1, 0),
            ('Duración (ej: 7 días)', 'duracion', 1, 1),
            ('Cantidad', 'cantidad', 2, 0),
            ('Fecha Inicio (YYYY-MM-DD)', 'fecha_inicio', 2, 1),
            ('Fecha Fin (YYYY-MM-DD)', 'fecha_fin', 3, 0),
        ]
        
        entries = {}
        for label_text, key, row, col in campos_texto:
            frame = tk.Frame(frame_detalles, bg='#f0f0f0')
            frame.grid(row=row, column=col, sticky='ew', padx=10, pady=3)
            
            texto = label_text + ' *' if '*' in label_text else label_text
            tk.Label(
                frame,
                text=texto,
                width=18,
                anchor='w',
                bg='#f0f0f0',
                font=('Arial', 10)
            ).pack(side='left')
            
            entry = tk.Entry(frame, width=25, font=('Arial', 10))
            entry.pack(side='right', padx=5)
            entries[key] = entry
        
        # --- Indicaciones (campo grande) ---
        frame = tk.Frame(frame_campos, bg='#f0f0f0')
        frame.pack(fill='x', pady=5)
        tk.Label(frame, text="Indicaciones:", width=20, anchor='w', bg='#f0f0f0', font=('Arial', 10)).pack(side='left')
        text_indicaciones = tk.Text(frame, width=40, height=3, font=('Arial', 10))
        text_indicaciones.pack(side='right', padx=5)
        
        # ---------- FUNCIÓN GUARDAR ----------
        def guardar():
            # Validar campos obligatorios
            obligatorios = ['dosis', 'via', 'frecuencia']
            for campo in obligatorios:
                if not entries[campo].get().strip():
                    messagebox.showerror("Error", f"El campo '{campo}' es obligatorio.")
                    return
            
            # Obtener IDs seleccionados
            try:
                paciente_id = int(combo_paciente.get().split(' - ')[0])
                profesional_id = int(combo_prof.get().split(' - ')[0])
                farmaco_id = int(combo_farmaco.get().split(' - ')[0])
                
                snomed_id = None
                if snomed and combo_snomed.get() and combo_snomed.get() != 'No hay diagnósticos cargados':
                    snomed_id = int(combo_snomed.get().split(' - ')[0])
            except (ValueError, IndexError) as e:
                print(f"[ERROR] Error al parsear IDs: {e}")
                messagebox.showerror("Error", "Seleccione opciones válidas.")
                return
            
            # Recolectar datos
            datos = {
                'paciente_id': paciente_id,
                'profesional_id': profesional_id,
                'farmaco_id': farmaco_id,
                'snomed_id': snomed_id,
                'dosis': entries['dosis'].get().strip(),
                'via_administracion': entries['via'].get().strip(),
                'frecuencia': entries['frecuencia'].get().strip(),
                'duracion': entries['duracion'].get().strip(),
                'cantidad': int(entries['cantidad'].get()) if entries['cantidad'].get().strip() else None,
                'indicaciones': text_indicaciones.get('1.0', tk.END).strip(),
                'fecha_inicio': entries['fecha_inicio'].get().strip() or None,
                'fecha_fin': entries['fecha_fin'].get().strip() or None
            }
            
            resultado, info = registrar_prescripcion(datos)
            if resultado:
                messagebox.showinfo("Éxito", f"✅ Prescripción registrada con éxito.\nID: {info}")
                ventana.destroy()
                self.ver_todas()
            else:
                messagebox.showerror("Error", f"❌ {info}")
        
        # ---------- BOTONES ----------
        frame_botones = tk.Frame(ventana, bg='#f0f0f0')
        frame_botones.pack(pady=20)
        
        tk.Button(
            frame_botones,
            text="💾 Guardar Prescripción",
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
    
    # ---------- DOBLE CLICK - VER DETALLE ----------
    def on_doble_click(self, event):
        """Maneja el doble clic en la tabla"""
        seleccion = self.tree.selection()
        if not seleccion:
            return
        
        item = self.tree.item(seleccion[0])
        valores = item['values']
        if not valores:
            return
        
        prescripcion_id = valores[0]
        self.ver_detalle_prescripcion(prescripcion_id)
    
    def ver_detalle_prescripcion(self, prescripcion_id):
        """Muestra el detalle de una prescripción"""
        prescripcion = buscar_prescripcion_por_id(prescripcion_id)
        if not prescripcion:
            messagebox.showerror("Error", "No se encontró la prescripción.")
            return
        
        ventana = tk.Toplevel(self.root)
        ventana.title(f"Detalle de Prescripción #{prescripcion_id}")
        ventana.geometry("550x600")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()
        
        tk.Label(
            ventana,
            text=f"💊 PRESCRIPCIÓN #{prescripcion_id}",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0',
            fg='#003366'
        ).pack(pady=10)
        
        estado = "✅ Activa" if prescripcion['activo'] == 1 else "🚫 Anulada"
        
        frame_detalle = tk.Frame(ventana, bg='#f0f0f0')
        frame_detalle.pack(padx=30, pady=10, fill='both', expand=True)
        
        detalles = [
            ('👤 Paciente', prescripcion['paciente_nombre']),
            ('📋 DNI Paciente', prescripcion['paciente_dni']),
            ('👨‍⚕️ Profesional', prescripcion['profesional_nombre']),
            ('📋 DNI Profesional', prescripcion['profesional_dni']),
            ('💊 Fármaco', prescripcion['farmaco_nombre']),
            ('📋 Código Fármaco', prescripcion['farmaco_codigo']),
            ('📋 Diagnóstico', prescripcion['diagnostico']),
            ('📋 Código SNOMED', prescripcion['diagnostico_codigo']),
            ('💊 Dosis', prescripcion['dosis']),
            ('💉 Vía Administración', prescripcion['via_administracion']),
            ('⏱️ Frecuencia', prescripcion['frecuencia']),
            ('📅 Duración', prescripcion['duracion'] or 'No especificada'),
            ('📦 Cantidad', prescripcion['cantidad'] or 'No especificada'),
            ('📅 Fecha Inicio', prescripcion['fecha_inicio'] or 'No especificada'),
            ('📅 Fecha Fin', prescripcion['fecha_fin'] or 'No especificada'),
            ('📝 Indicaciones', prescripcion['indicaciones'] or 'Sin indicaciones'),
            ('📅 Fecha Prescripción', prescripcion['fecha_prescripcion']),
            ('📊 Estado', estado)
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
                text=value,
                anchor='w',
                bg='#f0f0f0',
                font=('Arial', 10),
                wraplength=350,
                justify='left'
            ).pack(side='left', padx=5)
        
        # Botones de acción
        frame_botones = tk.Frame(ventana, bg='#f0f0f0')
        frame_botones.pack(pady=15)
        
        if prescripcion['activo'] == 1:
            tk.Button(
                frame_botones,
                text="🚫 Anular",
                bg='#f44336',
                fg='white',
                font=('Arial', 10, 'bold'),
                padx=15,
                pady=5,
                command=lambda: self.anular_prescripcion(prescripcion_id, ventana)
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
    
    def anular_prescripcion(self, prescripcion_id, ventana_actual):
        """Anula una prescripción"""
        if messagebox.askyesno(
            "⚠️ Confirmar Anulación",
            "¿Está seguro de anular esta prescripción?\n\nEsta acción no se puede deshacer."
        ):
            resultado, mensaje = anular_prescripcion(prescripcion_id)
            if resultado:
                messagebox.showinfo("Éxito", mensaje)
                ventana_actual.destroy()
                self.ver_todas()
            else:
                messagebox.showerror("Error", mensaje)


# ================================================================
# PUNTO DE ENTRADA
# ================================================================

if __name__ == "__main__":
    root = tk.Tk()
    app = AppPrescripciones(root)
    root.mainloop()
