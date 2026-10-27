# Pacientes_app.py
# Módulo de Gestión de Pacientes - OpenHIS-UNLaM
# Sprint 2: Interfaz Gráfica con Tkinter
# Equipo ¿?

import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime

# --- CONEXIÓN A LA BASE DE DATOS ---
def conectar_bd():
    return sqlite3.connect('BD/Salud.db')

# --- HU-01: REGISTRAR PACIENTE (CREATE) ---
def registrar_paciente(datos):
    """
    datos: diccionario con los campos del paciente
    """
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        
        cursor.execute("""
            INSERT INTO Pacientes 
            (dni, nombre, apellido, fecha_nacimiento, sexo, telefono, email, domicilio, obra_social)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datos['dni'],
            datos['nombre'],
            datos['apellido'],
            datos['fecha_nac'],
            datos['sexo'],
            datos['telefono'],
            datos['email'],
            datos['domicilio'],
            datos['obra_social']
        ))
        
        conexion.commit()
        nuevo_id = cursor.lastrowid
        conexion.close()
        
        return True, nuevo_id
        
    except sqlite3.IntegrityError:
        return False, "DNI duplicado. Ya existe un paciente con ese DNI."
    except Exception as e:
        return False, f"Error: {e}"

# --- HU-02: BUSCAR PACIENTE POR DNI (READ) ---
def buscar_paciente(dni):
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
                'telefono': paciente[6],
                'email': paciente[7],
                'domicilio': paciente[8],
                'obra_social': paciente[9],
                'fecha_registro': paciente[10]
            }
        else:
            return None
            
    except Exception as e:
        return None

# --- CLASE DE LA APLICACIÓN PRINCIPAL ---
class AppPacientes:
    def __init__(self, root):
        self.root = root
        self.root.title("OpenHIS-UNLaM - Gestión de Pacientes")
        self.root.geometry("800x600")
        self.root.configure(bg='#f0f0f0')
        
        # Frame principal
        self.frame_principal = tk.Frame(self.root, bg='#f0f0f0')
        self.frame_principal.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Título
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
            text="Sistema de Gestión de Pacientes - Sprint 1",
            font=('Arial', 10),
            bg='#f0f0f0',
            fg='#666666'
        )
        subtitulo.pack(pady=5)
        
        # Separador
        tk.Frame(self.frame_principal, height=2, bg='#cccccc').pack(fill='x', pady=10)
        
        # --- ÁREA DE BOTONES PRINCIPALES ---
        frame_botones = tk.Frame(self.frame_principal, bg='#f0f0f0')
        frame_botones.pack(pady=10)
        
        self.btn_registrar = tk.Button(
            frame_botones,
            text="📋 Registrar Nuevo Paciente",
            font=('Arial', 12),
            bg='#4CAF50',
            fg='white',
            padx=20,
            pady=10,
            command=self.abrir_registro
        )
        self.btn_registrar.pack(side='left', padx=10)
        
        self.btn_buscar = tk.Button(
            frame_botones,
            text="🔍 Buscar Paciente",
            font=('Arial', 12),
            bg='#2196F3',
            fg='white',
            padx=20,
            pady=10,
            command=self.abrir_busqueda
        )
        self.btn_buscar.pack(side='left', padx=10)
        
        self.btn_ver_todos = tk.Button(
            frame_botones,
            text="📊 Ver Todos",
            font=('Arial', 12),
            bg='#FF9800',
            fg='white',
            padx=20,
            pady=10,
            command=self.ver_todos
        )
        self.btn_ver_todos.pack(side='left', padx=10)
        
        # --- ÁREA DE RESULTADOS ---
        tk.Frame(self.frame_principal, height=2, bg='#cccccc').pack(fill='x', pady=10)
        
        self.label_resultados = tk.Label(
            self.frame_principal,
            text="Seleccione una acción para comenzar",
            font=('Arial', 11),
            bg='#f0f0f0',
            fg='#333333'
        )
        self.label_resultados.pack(pady=10)
        
        # Treeview para mostrar resultados
        self.tree = ttk.Treeview(self.frame_principal, columns=('ID', 'DNI', 'Nombre', 'Apellido', 'Teléfono'), show='headings', height=10)
        self.tree.heading('ID', text='HC')
        self.tree.heading('DNI', text='DNI')
        self.tree.heading('Nombre', text='Nombre')
        self.tree.heading('Apellido', text='Apellido')
        self.tree.heading('Teléfono', text='Teléfono')
        self.tree.column('ID', width=50)
        self.tree.column('DNI', width=100)
        self.tree.column('Nombre', width=150)
        self.tree.column('Apellido', width=150)
        self.tree.column('Teléfono', width=100)
        self.tree.pack(fill='both', expand=True, pady=10)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(self.frame_principal, orient='vertical', command=self.tree.yview)
        scrollbar.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # --- ESTADO ---
        self.label_estado = tk.Label(
            self.frame_principal,
            text="✅ OpenHIS-UNLaM",
            font=('Arial', 9),
            bg='#f0f0f0',
            fg='#666666'
        )
        self.label_estado.pack(side='bottom', pady=10)
        
        # Cargar todos los pacientes al iniciar
        self.ver_todos()
    
    # --- ABRIR VENTANA DE REGISTRO ---
    def abrir_registro(self):
        ventana_registro = tk.Toplevel(self.root)
        ventana_registro.title("Registrar Nuevo Paciente")
        ventana_registro.geometry("500x600")
        ventana_registro.configure(bg='#f0f0f0')
        ventana_registro.grab_set()  # Modal
        
        # Título
        tk.Label(
            ventana_registro,
            text="📋 REGISTRO DE PACIENTE",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0',
            fg='#003366'
        ).pack(pady=10)
        
        # Frame para campos
        frame_campos = tk.Frame(ventana_registro, bg='#f0f0f0')
        frame_campos.pack(padx=30, pady=10)
        
        campos = [
            ('DNI *', 'dni'),
            ('Nombre *', 'nombre'),
            ('Apellido *', 'apellido'),
            ('Fecha Nac. (YYYY-MM-DD) *', 'fecha_nac'),
            ('Sexo (M/F) *', 'sexo'),
            ('Teléfono', 'telefono'),
            ('Email', 'email'),
            ('Domicilio', 'domicilio'),
            ('Obra Social', 'obra_social')
        ]
        
        self.entries = {}
        for i, (label_text, key) in enumerate(campos):
            frame = tk.Frame(frame_campos, bg='#f0f0f0')
            frame.pack(fill='x', pady=3)
            
            tk.Label(
                frame,
                text=label_text,
                width=20,
                anchor='w',
                bg='#f0f0f0',
                font=('Arial', 10)
            ).pack(side='left')
            
            entry = tk.Entry(frame, width=30, font=('Arial', 10))
            entry.pack(side='right')
            self.entries[key] = entry
        
        # Frame de botones
        frame_botones = tk.Frame(ventana_registro, bg='#f0f0f0')
        frame_botones.pack(pady=20)
        
        def guardar():
            # Validar campos obligatorios
            obligatorios = ['dni', 'nombre', 'apellido', 'fecha_nac', 'sexo']
            for campo in obligatorios:
                if not self.entries[campo].get().strip():
                    messagebox.showerror("Error", f"El campo {campo} es obligatorio.")
                    return
            
            datos = {
                'dni': self.entries['dni'].get().strip(),
                'nombre': self.entries['nombre'].get().strip(),
                'apellido': self.entries['apellido'].get().strip(),
                'fecha_nac': self.entries['fecha_nac'].get().strip(),
                'sexo': self.entries['sexo'].get().strip(),
                'telefono': self.entries['telefono'].get().strip(),
                'email': self.entries['email'].get().strip(),
                'domicilio': self.entries['domicilio'].get().strip(),
                'obra_social': self.entries['obra_social'].get().strip()
            }
            
            resultado, info = registrar_paciente(datos)
            if resultado:
                messagebox.showinfo("Éxito", f"✅ Paciente registrado con éxito.\nHistoria Clínica N°: {info}")
                ventana_registro.destroy()
                self.ver_todos()  # Actualizar lista
            else:
                messagebox.showerror("Error", f"❌ {info}")
        
        tk.Button(
            frame_botones,
            text="💾 Guardar Paciente",
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
            command=ventana_registro.destroy
        ).pack(side='left', padx=10)
    
    # --- ABRIR VENTANA DE BÚSQUEDA ---
    def abrir_busqueda(self):
        ventana_busqueda = tk.Toplevel(self.root)
        ventana_busqueda.title("Buscar Paciente")
        ventana_busqueda.geometry("400x200")
        ventana_busqueda.configure(bg='#f0f0f0')
        ventana_busqueda.grab_set()
        
        tk.Label(
            ventana_busqueda,
            text="🔍 BUSCAR PACIENTE POR DNI",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0',
            fg='#003366'
        ).pack(pady=15)
        
        frame_busqueda = tk.Frame(ventana_busqueda, bg='#f0f0f0')
        frame_busqueda.pack(pady=20)
        
        tk.Label(
            frame_busqueda,
            text="DNI:",
            font=('Arial', 12),
            bg='#f0f0f0'
        ).pack(side='left', padx=10)
        
        entry_dni = tk.Entry(frame_busqueda, font=('Arial', 12), width=20)
        entry_dni.pack(side='left', padx=10)
        entry_dni.focus()
        
        def buscar():
            dni = entry_dni.get().strip()
            if not dni:
                messagebox.showerror("Error", "Ingrese un DNI para buscar.")
                return
            
            resultado = buscar_paciente(dni)
            if resultado:
                msg = (
                    f"Historia Clínica: {resultado['id']}\n"
                    f"DNI: {resultado['dni']}\n"
                    f"Nombre:{resultado['nombre']} {resultado['apellido']}\n"
                    f"Fecha Nac.: {resultado['fecha_nac']}\n"
                    f"Sexo: {resultado['sexo']}\n"
                    f"Teléfono: {resultado['telefono']}\n"
                    f"Email: {resultado['email']}\n"
                    f"Domicilio: {resultado['domicilio']}\n"
                    f"Obra Social: {resultado['obra_social']}"
                )
                messagebox.showinfo("✅ Paciente Encontrado", msg)
                ventana_busqueda.destroy()
            else:
                messagebox.showerror("Error", "❌ Paciente no encontrado.")
        
        def buscar_y_cerrar(event=None):
            buscar()
        
        entry_dni.bind('<Return>', buscar_y_cerrar)
        
        tk.Button(
            ventana_busqueda,
            text="🔍 Buscar",
            bg='#2196F3',
            fg='white',
            font=('Arial', 11),
            padx=20,
            pady=8,
            command=buscar
        ).pack(pady=10)
    
    # --- VER TODOS LOS PACIENTES ---
    def ver_todos(self):
        # Limpiar tree
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        try:
            conexion = conectar_bd()
            cursor = conexion.cursor()
            cursor.execute("SELECT id, dni, nombre, apellido, telefono FROM Pacientes ORDER BY apellido, nombre")
            pacientes = cursor.fetchall()
            conexion.close()
            
            for p in pacientes:
                self.tree.insert('', 'end', values=(p[0], p[1], p[2], p[3], p[4]))
            
            self.label_resultados.config(text=f"📊 Total de pacientes: {len(pacientes)}")
            
        except Exception as e:
            self.label_resultados.config(text=f"❌ Error: {e}")

# --- PUNTO DE ENTRADA ---
if __name__ == "__main__":
    root = tk.Tk()
    app = AppPacientes(root)
    root.mainloop()
