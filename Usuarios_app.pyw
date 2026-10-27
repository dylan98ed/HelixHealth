# ================================================================
# Usuarios_app.pyw
# MÓDULO DE GESTIÓN DE USUARIOS - OPENHIS-UNLaM
# ================================================================
#
# FUNCIONALIDADES:
#   ✅ Registrar usuario (CREATE)
#   ✅ Buscar usuario por nombre de usuario (READ)
#   ✅ Listar todos los usuarios (READ)
#   ✅ Modificar usuario (UPDATE)
#   ✅ Cambiar contraseña
#   ✅ Dar de baja usuario (DELETE lógico)
#   ✅ Reactivar usuario
#   ✅ Ver usuarios activos / inactivos
#   ✅ Interfaz gráfica con Tkinter
#
# SEGURIDAD:
#   - Contraseñas hasheadas con SHA-256
#   - Roles definidos: admin, medico, enfermero, administrativo
#   - Borrado lógico (activo = 0)
#   - Auditoría de último acceso
# ================================================================

import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk
import hashlib
from datetime import datetime

# ================================================================
# CONEXIÓN A BASE DE DATOS
# ================================================================

def conectar_bd():
    """Establece conexión con la base de datos Salud.db"""
    return sqlite3.connect('BD/Salud.db')


def hashear_password(password):
    """Hashea una contraseña con SHA-256"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


# ================================================================
# CRUD DE USUARIOS
# ================================================================

def registrar_usuario(datos):
    """
    Registra un nuevo usuario (CREATE)
    
    Parámetros:
        datos (dict):
            - usuario (str): obligatorio, único
            - password (str): obligatorio
            - nombre_completo (str): obligatorio
            - email (str): opcional
            - rol (str): obligatorio (admin, medico, enfermero, administrativo)
    
    Retorna:
        (True, id_nuevo) o (False, mensaje_error)
    """
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        
        password_hash = hashear_password(datos['password'])
        
        cursor.execute("""
            INSERT INTO Usuarios 
            (usuario, password_hash, nombre_completo, email, rol, activo)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            datos['usuario'],
            password_hash,
            datos['nombre_completo'],
            datos.get('email', ''),
            datos['rol'],
            1
        ))
        
        conexion.commit()
        nuevo_id = cursor.lastrowid
        conexion.close()
        print(f"[DEBUG] Usuario registrado con ID: {nuevo_id}")
        return True, nuevo_id
        
    except sqlite3.IntegrityError:
        return False, "❌ El nombre de usuario ya existe. Elija otro."
    except Exception as e:
        print(f"[ERROR] Error en registrar_usuario: {e}")
        return False, f"❌ Error: {e}"


def buscar_usuario(usuario):
    """Busca un usuario por nombre de usuario"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT id, usuario, nombre_completo, email, rol, activo, 
                   ultimo_acceso, fecha_creacion
            FROM Usuarios 
            WHERE usuario = ?
        """, (usuario,))
        resultado = cursor.fetchone()
        conexion.close()
        
        if resultado:
            return {
                'id': resultado[0],
                'usuario': resultado[1],
                'nombre_completo': resultado[2],
                'email': resultado[3] or '',
                'rol': resultado[4],
                'activo': resultado[5],
                'ultimo_acceso': resultado[6] or 'Nunca',
                'fecha_creacion': resultado[7]
            }
        return None
    except Exception as e:
        print(f"[ERROR] Error en buscar_usuario: {e}")
        return None


def listar_usuarios(activos=True):
    """Lista usuarios según estado"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        
        estado = 1 if activos else 0
        
        cursor.execute(f"""
            SELECT id, usuario, nombre_completo, email, rol, activo, 
                   ultimo_acceso, fecha_creacion
            FROM Usuarios 
            WHERE activo = {estado}
            ORDER BY nombre_completo
        """)
        resultados = cursor.fetchall()
        conexion.close()
        return resultados
    except Exception as e:
        print(f"[ERROR] Error en listar_usuarios: {e}")
        return []


def modificar_usuario(usuario_id, datos):
    """Modifica datos de un usuario (excepto contraseña)"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        
        cursor.execute("""
            UPDATE Usuarios 
            SET nombre_completo = ?, email = ?, rol = ?
            WHERE id = ?
        """, (
            datos['nombre_completo'],
            datos.get('email', ''),
            datos['rol'],
            usuario_id
        ))
        
        conexion.commit()
        afectados = cursor.rowcount
        conexion.close()
        
        if afectados > 0:
            return True, "✅ Usuario modificado correctamente."
        return False, "❌ No se encontró el usuario."
    except Exception as e:
        return False, f"❌ Error: {e}"


def cambiar_password(usuario_id, nueva_password):
    """Cambia la contraseña de un usuario"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        
        password_hash = hashear_password(nueva_password)
        
        cursor.execute("""
            UPDATE Usuarios SET password_hash = ? WHERE id = ?
        """, (password_hash, usuario_id))
        
        conexion.commit()
        afectados = cursor.rowcount
        conexion.close()
        
        if afectados > 0:
            return True, "✅ Contraseña cambiada correctamente."
        return False, "❌ No se encontró el usuario."
    except Exception as e:
        return False, f"❌ Error: {e}"


def dar_baja_usuario(usuario_id):
    """Baja lógica de usuario (activo = 0)"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        
        # Verificar que no sea el último admin activo
        cursor.execute("""
            SELECT rol FROM Usuarios WHERE id = ?
        """, (usuario_id,))
        resultado = cursor.fetchone()
        
        if not resultado:
            conexion.close()
            return False, "❌ No se encontró el usuario."
        
        if resultado[0] == 'admin':
            cursor.execute("""
                SELECT COUNT(*) FROM Usuarios 
                WHERE rol = 'admin' AND activo = 1 AND id != ?
            """, (usuario_id,))
            otros_admins = cursor.fetchone()[0]
            
            if otros_admins == 0:
                conexion.close()
                return False, "❌ No se puede dar de baja al último administrador activo."
        
        cursor.execute("UPDATE Usuarios SET activo = 0 WHERE id = ?", (usuario_id,))
        conexion.commit()
        conexion.close()
        
        return True, "✅ Usuario dado de baja correctamente."
    except Exception as e:
        return False, f"❌ Error: {e}"


def reactivar_usuario(usuario_id):
    """Reactiva un usuario dado de baja"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        
        cursor.execute("UPDATE Usuarios SET activo = 1 WHERE id = ?", (usuario_id,))
        conexion.commit()
        afectados = cursor.rowcount
        conexion.close()
        
        if afectados > 0:
            return True, "✅ Usuario reactivado correctamente."
        return False, "❌ No se encontró el usuario."
    except Exception as e:
        return False, f"❌ Error: {e}"


# ================================================================
# CAPA DE PRESENTACIÓN (FRONTEND)
# ================================================================

class AppUsuarios:
    """Aplicación de gestión de usuarios"""
    
    # Colores por rol
    COLORES_ROL = {
        'admin': '#f44336',
        'medico': '#2196F3',
        'enfermero': '#4CAF50',
        'administrativo': '#FF9800'
    }
    
    def __init__(self, root):
        self.root = root
        self.root.title("OpenHIS-UNLaM - Gestión de Usuarios")
        self.root.geometry("1050x650")
        self.root.configure(bg='#f0f0f0')
        
        # Centrar
        self.root.update_idletasks()
        ancho = self.root.winfo_width()
        alto = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (ancho // 2)
        y = (self.root.winfo_screenheight() // 2) - (alto // 2)
        self.root.geometry(f'{ancho}x{alto}+{x}+{y}')
        
        # Frame principal
        self.frame_principal = tk.Frame(self.root, bg='#f0f0f0')
        self.frame_principal.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Título
        tk.Label(
            self.frame_principal,
            text="🔐 GESTIÓN DE USUARIOS",
            font=('Arial', 18, 'bold'),
            bg='#f0f0f0',
            fg='#003366'
        ).pack(pady=5)
        
        tk.Label(
            self.frame_principal,
            text="Administración de cuentas y permisos del sistema",
            font=('Arial', 11),
            bg='#f0f0f0',
            fg='#666666'
        ).pack(pady=2)
        
        tk.Frame(self.frame_principal, height=2, bg='#cccccc').pack(fill='x', pady=10)
        
        # ---------- BOTONES ----------
        frame_botones = tk.Frame(self.frame_principal, bg='#f0f0f0')
        frame_botones.pack(pady=10)
        
        estilo = {'font': ('Arial', 10, 'bold'), 'padx': 15, 'pady': 8,
                  'relief': 'raised', 'bd': 2}
        
        tk.Button(frame_botones, text="➕ Nuevo Usuario", bg='#4CAF50',
                 fg='white', command=self.abrir_registro, **estilo).pack(side='left', padx=3)
        
        tk.Button(frame_botones, text="🔍 Buscar", bg='#2196F3',
                 fg='white', command=self.abrir_busqueda, **estilo).pack(side='left', padx=3)
        
        tk.Button(frame_botones, text="✏️ Modificar", bg='#FF9800',
                 fg='white', command=self.abrir_modificacion, **estilo).pack(side='left', padx=3)
        
        tk.Button(frame_botones, text="🔑 Cambiar Password", bg='#9C27B0',
                 fg='white', command=self.abrir_cambio_password, **estilo).pack(side='left', padx=3)
        
        tk.Button(frame_botones, text="🗑️ Dar de Baja", bg='#f44336',
                 fg='white', command=self.dar_baja, **estilo).pack(side='left', padx=3)
        
        # Separador
        tk.Frame(frame_botones, width=20, bg='#f0f0f0').pack(side='left')
        
        tk.Button(frame_botones, text="📊 Ver Activos", bg='#607D8B',
                 fg='white', command=lambda: self.ver_usuarios(True),
                 **estilo).pack(side='left', padx=3)
        
        tk.Button(frame_botones, text="📋 Ver Inactivos", bg='#9E9E9E',
                 fg='white', command=lambda: self.ver_usuarios(False),
                 **estilo).pack(side='left', padx=3)
        
        tk.Frame(self.frame_principal, height=2, bg='#cccccc').pack(fill='x', pady=10)
        
        # Label de resultados
        self.label_resultados = tk.Label(
            self.frame_principal,
            text="Seleccione una acción para comenzar",
            font=('Arial', 11, 'italic'),
            bg='#f0f0f0',
            fg='#666666'
        )
        self.label_resultados.pack(pady=5)
        
        # Tabla
        frame_tabla = tk.Frame(self.frame_principal, bg='#f0f0f0')
        frame_tabla.pack(fill='both', expand=True, pady=10)
        
        self.tree = ttk.Treeview(
            frame_tabla,
            columns=('ID', 'Usuario', 'Nombre Completo', 'Email', 'Rol', 'Estado', 'Último Acceso'),
            show='headings',
            height=12,
            selectmode='browse'
        )
        
        columnas = [
            ('ID', 'ID', 40, 'center'),
            ('Usuario', 'Usuario', 120, 'center'),
            ('Nombre Completo', 'Nombre Completo', 220, 'w'),
            ('Email', 'Email', 200, 'w'),
            ('Rol', 'Rol', 120, 'center'),
            ('Estado', 'Estado', 80, 'center'),
            ('Último Acceso', 'Último Acceso', 140, 'center')
        ]
        
        for col, heading, width, anchor in columnas:
            self.tree.heading(col, text=heading)
            self.tree.column(col, width=width, anchor=anchor)
        
        self.tree.pack(side='left', fill='both', expand=True)
        
        scrollbar = ttk.Scrollbar(frame_tabla, orient='vertical', command=self.tree.yview)
        scrollbar.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.bind('<Double-1>', self.on_doble_click)
        
        # Estado
        self.label_estado = tk.Label(
            self.frame_principal,
            text="✅ OpenHIS-UNLaM",
            font=('Arial', 9),
            bg='#f0f0f0',
            fg='#666666'
        )
        self.label_estado.pack(side='bottom', pady=5)
        
        # Cargar usuarios activos
        self.ver_usuarios(activos=True)
    
    # ============================================================
    # MÉTODOS
    # ============================================================
    
    def ver_usuarios(self, activos=True):
        """Carga usuarios según su estado"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        usuarios = listar_usuarios(activos=activos)
        
        for u in usuarios:
            estado = "✅ Activo" if u[5] == 1 else "🚫 Inactivo"
            ultimo = u[6][:16] if u[6] else 'Nunca'
            self.tree.insert('', 'end', values=(
                u[0], u[1], u[2], u[3] or '-', u[4].upper(), estado, ultimo
            ))
        
        tipo = "activos" if activos else "inactivos"
        self.label_resultados.config(text=f"👥 Total de usuarios {tipo}: {len(usuarios)}")
    
    def on_doble_click(self, event):
        """Doble clic - ver detalle"""
        seleccion = self.tree.selection()
        if not seleccion:
            return
        item = self.tree.item(seleccion[0])
        usuario = item['values'][1]
        self.ver_detalle(usuario)
    
    def ver_detalle(self, usuario):
        """Muestra el detalle de un usuario"""
        u = buscar_usuario(usuario)
        if not u:
            messagebox.showerror("Error", "No se encontró el usuario.")
            return
        
        ventana = tk.Toplevel(self.root)
        ventana.title(f"Detalle - {u['usuario']}")
        ventana.geometry("500x450")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()
        
        tk.Label(ventana, text=f"🔐 DETALLE DE USUARIO",
                font=('Arial', 14, 'bold'), bg='#f0f0f0', fg='#003366').pack(pady=10)
        
        estado = "✅ Activo" if u['activo'] == 1 else "🚫 Inactivo"
        color_rol = self.COLORES_ROL.get(u['rol'], '#666')
        
        tk.Label(ventana, text=estado, font=('Arial', 11, 'bold'),
                bg='#f0f0f0', fg='#4CAF50' if u['activo'] == 1 else '#f44336').pack(pady=5)
        
        tk.Label(ventana, text=f"Rol: {u['rol'].upper()}", font=('Arial', 10, 'bold'),
                bg='#f0f0f0', fg=color_rol).pack(pady=3)
        
        frame_detalle = tk.Frame(ventana, bg='#f0f0f0')
        frame_detalle.pack(padx=30, pady=10, fill='both', expand=True)
        
        detalles = [
            ('🆔 ID', u['id']),
            ('👤 Usuario', u['usuario']),
            ('📛 Nombre', u['nombre_completo']),
            ('✉️ Email', u['email'] or 'No registrado'),
            ('👔 Rol', u['rol'].capitalize()),
            ('📅 Último acceso', u['ultimo_acceso'][:16] if u['ultimo_acceso'] != 'Nunca' else 'Nunca'),
            ('📅 Fecha creación', u['fecha_creacion']),
            ('📊 Estado', estado)
        ]
        
        for label, value in detalles:
            frame = tk.Frame(frame_detalle, bg='#f0f0f0')
            frame.pack(fill='x', pady=3)
            tk.Label(frame, text=f"{label}:", width=18, anchor='w',
                    bg='#f0f0f0', font=('Arial', 10, 'bold')).pack(side='left')
            tk.Label(frame, text=str(value), anchor='w',
                    bg='#f0f0f0', font=('Arial', 10),
                    wraplength=300, justify='left').pack(side='left', padx=5)
        
        # Botones según estado
        frame_botones = tk.Frame(ventana, bg='#f0f0f0')
        frame_botones.pack(pady=15)
        
        if u['activo'] == 1:
            tk.Button(frame_botones, text="🔑 Cambiar Password", bg='#9C27B0', fg='white',
                     font=('Arial', 10, 'bold'), padx=15, pady=5,
                     command=lambda: [ventana.destroy(), self.abrir_cambio_password_con_usuario(usuario)]).pack(side='left', padx=5)
            
            tk.Button(frame_botones, text="🗑️ Dar de Baja", bg='#f44336', fg='white',
                     font=('Arial', 10, 'bold'), padx=15, pady=5,
                     command=lambda: [ventana.destroy(), self.baja_con_usuario(usuario)]).pack(side='left', padx=5)
        else:
            tk.Button(frame_botones, text="♻️ Reactivar", bg='#4CAF50', fg='white',
                     font=('Arial', 10, 'bold'), padx=15, pady=5,
                     command=lambda: [ventana.destroy(), self.reactivar_con_usuario(usuario)]).pack(side='left', padx=5)
        
        tk.Button(frame_botones, text="❌ Cerrar", bg='#9E9E9E', fg='white',
                 font=('Arial', 10, 'bold'), padx=15, pady=5,
                 command=ventana.destroy).pack(side='left', padx=5)
    
    # ---------- REGISTRAR ----------
    def abrir_registro(self):
        """Abre ventana para registrar nuevo usuario"""
        ventana = tk.Toplevel(self.root)
        ventana.title("Registrar Nuevo Usuario")
        ventana.geometry("500x550")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()
        ventana.resizable(False, False)
        
        tk.Label(ventana, text="➕ NUEVO USUARIO",
                font=('Arial', 14, 'bold'), bg='#f0f0f0', fg='#4CAF50').pack(pady=10)
        
        tk.Label(ventana, text="Los campos con * son obligatorios",
                font=('Arial', 9), bg='#f0f0f0', fg='#666666').pack(pady=2)
        
        frame_campos = tk.Frame(ventana, bg='#f0f0f0')
        frame_campos.pack(padx=30, pady=15)
        
        # Usuario
        frame = tk.Frame(frame_campos, bg='#f0f0f0')
        frame.pack(fill='x', pady=4)
        tk.Label(frame, text="Usuario *:", width=18, anchor='w',
                bg='#f0f0f0', font=('Arial', 10)).pack(side='left')
        entry_usuario = tk.Entry(frame, width=28, font=('Arial', 10))
        entry_usuario.pack(side='right')
        
        # Password
        frame = tk.Frame(frame_campos, bg='#f0f0f0')
        frame.pack(fill='x', pady=4)
        tk.Label(frame, text="Contraseña *:", width=18, anchor='w',
                bg='#f0f0f0', font=('Arial', 10)).pack(side='left')
        entry_password = tk.Entry(frame, width=28, font=('Arial', 10), show='●')
        entry_password.pack(side='right')
        
        # Confirmar Password
        frame = tk.Frame(frame_campos, bg='#f0f0f0')
        frame.pack(fill='x', pady=4)
        tk.Label(frame, text="Confirmar *:", width=18, anchor='w',
                bg='#f0f0f0', font=('Arial', 10)).pack(side='left')
        entry_confirm = tk.Entry(frame, width=28, font=('Arial', 10), show='●')
        entry_confirm.pack(side='right')
        
        # Nombre completo
        frame = tk.Frame(frame_campos, bg='#f0f0f0')
        frame.pack(fill='x', pady=4)
        tk.Label(frame, text="Nombre Completo *:", width=18, anchor='w',
                bg='#f0f0f0', font=('Arial', 10)).pack(side='left')
        entry_nombre = tk.Entry(frame, width=28, font=('Arial', 10))
        entry_nombre.pack(side='right')
        
        # Email
        frame = tk.Frame(frame_campos, bg='#f0f0f0')
        frame.pack(fill='x', pady=4)
        tk.Label(frame, text="Email:", width=18, anchor='w',
                bg='#f0f0f0', font=('Arial', 10)).pack(side='left')
        entry_email = tk.Entry(frame, width=28, font=('Arial', 10))
        entry_email.pack(side='right')
        
        # Rol
        frame = tk.Frame(frame_campos, bg='#f0f0f0')
        frame.pack(fill='x', pady=4)
        tk.Label(frame, text="Rol *:", width=18, anchor='w',
                bg='#f0f0f0', font=('Arial', 10)).pack(side='left')
        combo_rol = ttk.Combobox(frame, width=25, font=('Arial', 10), state='readonly')
        combo_rol['values'] = ['admin', 'medico', 'enfermero', 'administrativo']
        combo_rol.current(3)  # administrativo por defecto
        combo_rol.pack(side='right')
        
        def guardar():
            # Validar
            if not entry_usuario.get().strip():
                messagebox.showerror("Error", "El usuario es obligatorio.")
                return
            if not entry_password.get():
                messagebox.showerror("Error", "La contraseña es obligatoria.")
                return
            if entry_password.get() != entry_confirm.get():
                messagebox.showerror("Error", "Las contraseñas no coinciden.")
                return
            if not entry_nombre.get().strip():
                messagebox.showerror("Error", "El nombre completo es obligatorio.")
                return
            if len(entry_password.get()) < 6:
                messagebox.showerror("Error", "La contraseña debe tener al menos 6 caracteres.")
                return
            
            datos = {
                'usuario': entry_usuario.get().strip().lower(),
                'password': entry_password.get(),
                'nombre_completo': entry_nombre.get().strip(),
                'email': entry_email.get().strip(),
                'rol': combo_rol.get()
            }
            
            resultado, info = registrar_usuario(datos)
            if resultado:
                messagebox.showinfo("Éxito", f"✅ Usuario registrado.\nID: {info}")
                ventana.destroy()
                self.ver_usuarios(activos=True)
            else:
                messagebox.showerror("Error", f"❌ {info}")
        
        frame_botones = tk.Frame(ventana, bg='#f0f0f0')
        frame_botones.pack(pady=20)
        
        tk.Button(frame_botones, text="💾 Guardar", bg='#4CAF50', fg='white',
                 font=('Arial', 11, 'bold'), padx=25, pady=8,
                 command=guardar).pack(side='left', padx=10)
        tk.Button(frame_botones, text="❌ Cancelar", bg='#f44336', fg='white',
                 font=('Arial', 11, 'bold'), padx=25, pady=8,
                 command=ventana.destroy).pack(side='left', padx=10)
    
    # ---------- BUSCAR ----------
    def abrir_busqueda(self):
        """Busca usuario por nombre"""
        ventana = tk.Toplevel(self.root)
        ventana.title("Buscar Usuario")
        ventana.geometry("450x180")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()
        ventana.resizable(False, False)
        
        tk.Label(ventana, text="🔍 BUSCAR USUARIO",
                font=('Arial', 14, 'bold'), bg='#f0f0f0', fg='#003366').pack(pady=15)
        
        frame = tk.Frame(ventana, bg='#f0f0f0')
        frame.pack(pady=15)
        
        tk.Label(frame, text="Usuario:", font=('Arial', 11), bg='#f0f0f0').pack(side='left', padx=10)
        entry = tk.Entry(frame, font=('Arial', 11), width=20)
        entry.pack(side='left', padx=10)
        entry.focus()
        
        def buscar():
            usuario = entry.get().strip()
            if not usuario:
                messagebox.showerror("Error", "Ingrese un usuario.")
                return
            ventana.destroy()
            self.ver_detalle(usuario)
        
        entry.bind('<Return>', lambda e: buscar())
        
        tk.Button(ventana, text="🔍 Buscar", bg='#2196F3', fg='white',
                 font=('Arial', 11, 'bold'), padx=20, pady=8,
                 command=buscar).pack(pady=10)
    
    # ---------- MODIFICAR ----------
    def abrir_modificacion(self):
        """Modifica usuario"""
        ventana = tk.Toplevel(self.root)
        ventana.title("Modificar Usuario")
        ventana.geometry("500x400")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()
        ventana.resizable(False, False)
        
        tk.Label(ventana, text="✏️ MODIFICAR USUARIO",
                font=('Arial', 14, 'bold'), bg='#f0f0f0', fg='#FF9800').pack(pady=10)
        
        frame_buscar = tk.Frame(ventana, bg='#f0f0f0')
        frame_buscar.pack(pady=10)
        
        tk.Label(frame_buscar, text="Usuario:", font=('Arial', 11),
                bg='#f0f0f0').pack(side='left', padx=10)
        entry_usuario = tk.Entry(frame_buscar, font=('Arial', 11), width=20)
        entry_usuario.pack(side='left', padx=10)
        entry_usuario.focus()
        
        frame_campos = tk.Frame(ventana, bg='#f0f0f0')
        frame_campos.pack(pady=10, padx=30, fill='both', expand=True)
        
        label_info = tk.Label(frame_campos, text="Ingrese un usuario y presione Buscar",
                            font=('Arial', 11, 'bold'), bg='#f0f0f0', fg='#003366')
        label_info.pack(pady=5)
        
        entries = {}
        frame_entries = tk.Frame(frame_campos, bg='#f0f0f0')
        
        campos = [
            ('Nombre Completo', 'nombre_completo'),
            ('Email', 'email')
        ]
        
        for label_text, key in campos:
            frame = tk.Frame(frame_entries, bg='#f0f0f0')
            frame.pack(fill='x', pady=3)
            tk.Label(frame, text=label_text + ":", width=15, anchor='w',
                    bg='#f0f0f0', font=('Arial', 10)).pack(side='left')
            entry = tk.Entry(frame, width=30, font=('Arial', 10))
            entry.pack(side='right')
            entries[key] = entry
        
        # Rol
        frame = tk.Frame(frame_entries, bg='#f0f0f0')
        frame.pack(fill='x', pady=3)
        tk.Label(frame, text="Rol:", width=15, anchor='w',
                bg='#f0f0f0', font=('Arial', 10)).pack(side='left')
        combo_rol = ttk.Combobox(frame, width=27, font=('Arial', 10), state='readonly')
        combo_rol['values'] = ['admin', 'medico', 'enfermero', 'administrativo']
        combo_rol.pack(side='right')
        entries['rol'] = combo_rol
        
        usuario_id = None
        
        def buscar():
            nonlocal usuario_id
            u = entry_usuario.get().strip()
            if not u:
                messagebox.showerror("Error", "Ingrese un usuario.")
                return
            
            datos = buscar_usuario(u)
            if datos:
                usuario_id = datos['id']
                label_info.config(text=f"{datos['nombre_completo']} ({datos['rol'].upper()})")
                entries['nombre_completo'].delete(0, tk.END)
                entries['nombre_completo'].insert(0, datos['nombre_completo'])
                entries['email'].delete(0, tk.END)
                entries['email'].insert(0, datos['email'])
                combo_rol.set(datos['rol'])
                frame_entries.pack(pady=10)
            else:
                messagebox.showerror("Error", "Usuario no encontrado.")
        
        entry_usuario.bind('<Return>', lambda e: buscar())
        
        tk.Button(ventana, text="🔍 Buscar", bg='#2196F3', fg='white',
                 font=('Arial', 10, 'bold'), padx=15, pady=5,
                 command=buscar).pack(pady=5)
        
        def guardar():
            nonlocal usuario_id
            if not usuario_id:
                messagebox.showerror("Error", "Primero busque un usuario.")
                return
            
            datos = {
                'nombre_completo': entries['nombre_completo'].get().strip(),
                'email': entries['email'].get().strip(),
                'rol': combo_rol.get()
            }
            
            resultado, mensaje = modificar_usuario(usuario_id, datos)
            if resultado:
                messagebox.showinfo("Éxito", mensaje)
                ventana.destroy()
                self.ver_usuarios(activos=True)
            else:
                messagebox.showerror("Error", mensaje)
        
        frame_botones = tk.Frame(ventana, bg='#f0f0f0')
        frame_botones.pack(pady=15)
        
        tk.Button(frame_botones, text="💾 Guardar", bg='#FF9800', fg='white',
                 font=('Arial', 11, 'bold'), padx=20, pady=8,
                 command=guardar).pack(side='left', padx=10)
        tk.Button(frame_botones, text="❌ Cancelar", bg='#f44336', fg='white',
                 font=('Arial', 11, 'bold'), padx=20, pady=8,
                 command=ventana.destroy).pack(side='left', padx=10)
    
    # ---------- CAMBIAR PASSWORD ----------
    def abrir_cambio_password(self):
        """Abre ventana para cambiar password"""
        ventana = tk.Toplevel(self.root)
        ventana.title("Cambiar Contraseña")
        ventana.geometry("450x350")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()
        ventana.resizable(False, False)
        
        tk.Label(ventana, text="🔑 CAMBIAR CONTRASEÑA",
                font=('Arial', 14, 'bold'), bg='#f0f0f0', fg='#9C27B0').pack(pady=15)
        
        frame = tk.Frame(ventana, bg='#f0f0f0')
        frame.pack(pady=15)
        
        tk.Label(frame, text="Usuario:", font=('Arial', 11), bg='#f0f0f0').pack(side='left', padx=10)
        entry = tk.Entry(frame, font=('Arial', 11), width=20)
        entry.pack(side='left', padx=10)
        entry.focus()
        
        def continuar():
            u = entry.get().strip()
            if not u:
                messagebox.showerror("Error", "Ingrese un usuario.")
                return
            ventana.destroy()
            self.abrir_cambio_password_con_usuario(u)
        
        entry.bind('<Return>', lambda e: continuar())
        
        tk.Button(ventana, text="Continuar", bg='#9C27B0', fg='white',
                 font=('Arial', 11, 'bold'), padx=20, pady=8,
                 command=continuar).pack(pady=10)
    
    def abrir_cambio_password_con_usuario(self, usuario):
        """Abre ventana de cambio de password para un usuario específico"""
        u = buscar_usuario(usuario)
        if not u:
            messagebox.showerror("Error", "Usuario no encontrado.")
            return
        
        ventana = tk.Toplevel(self.root)
        ventana.title(f"Cambiar Contraseña - {usuario}")
        ventana.geometry("450x350")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()
        ventana.resizable(False, False)
        
        tk.Label(ventana, text=f"🔑 CAMBIAR CONTRASEÑA",
                font=('Arial', 14, 'bold'), bg='#f0f0f0', fg='#9C27B0').pack(pady=10)
        
        tk.Label(ventana, text=f"Usuario: {u['nombre_completo']}",
                font=('Arial', 11), bg='#f0f0f0', fg='#666666').pack(pady=5)
        
        frame = tk.Frame(ventana, bg='#f0f0f0')
        frame.pack(pady=15)
        
        # Nueva password
        f1 = tk.Frame(frame, bg='#f0f0f0')
        f1.pack(fill='x', pady=5)
        tk.Label(f1, text="Nueva contraseña:", width=18, anchor='w',
                bg='#f0f0f0', font=('Arial', 10)).pack(side='left')
        entry_pass = tk.Entry(f1, width=20, font=('Arial', 10), show='●')
        entry_pass.pack(side='right')
        
        # Confirmar
        f2 = tk.Frame(frame, bg='#f0f0f0')
        f2.pack(fill='x', pady=5)
        tk.Label(f2, text="Confirmar contraseña:", width=18, anchor='w',
                bg='#f0f0f0', font=('Arial', 10)).pack(side='left')
        entry_confirm = tk.Entry(f2, width=20, font=('Arial', 10), show='●')
        entry_confirm.pack(side='right')
        
        def guardar():
            p1 = entry_pass.get()
            p2 = entry_confirm.get()
            
            if not p1:
                messagebox.showerror("Error", "Ingrese la nueva contraseña.")
                return
            if p1 != p2:
                messagebox.showerror("Error", "Las contraseñas no coinciden.")
                return
            if len(p1) < 6:
                messagebox.showerror("Error", "La contraseña debe tener al menos 6 caracteres.")
                return
            
            resultado, mensaje = cambiar_password(u['id'], p1)
            if resultado:
                messagebox.showinfo("Éxito", mensaje)
                ventana.destroy()
            else:
                messagebox.showerror("Error", mensaje)
        
        frame_botones = tk.Frame(ventana, bg='#f0f0f0')
        frame_botones.pack(pady=15)
        
        tk.Button(frame_botones, text="💾 Cambiar", bg='#9C27B0', fg='white',
                 font=('Arial', 11, 'bold'), padx=20, pady=8,
                 command=guardar).pack(side='left', padx=10)
        tk.Button(frame_botones, text="❌ Cancelar", bg='#f44336', fg='white',
                 font=('Arial', 11, 'bold'), padx=20, pady=8,
                 command=ventana.destroy).pack(side='left', padx=10)
    
    # ---------- DAR DE BAJA ----------
    def dar_baja(self):
        """Baja lógica de usuario"""
        ventana = tk.Toplevel(self.root)
        ventana.title("Dar de Baja Usuario")
        ventana.geometry("450x250")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()
        ventana.resizable(False, False)
        
        tk.Label(ventana, text="🗑️ DAR DE BAJA USUARIO",
                font=('Arial', 14, 'bold'), bg='#f0f0f0', fg='#f44336').pack(pady=10)
        
        tk.Label(ventana, text="ℹ️ La baja es LÓGICA. El usuario puede reactivarse.",
                font=('Arial', 9), bg='#f0f0f0', fg='#666666').pack(pady=5)
        
        frame = tk.Frame(ventana, bg='#f0f0f0')
        frame.pack(pady=15)
        
        tk.Label(frame, text="Usuario:", font=('Arial', 11), bg='#f0f0f0').pack(side='left', padx=10)
        entry = tk.Entry(frame, font=('Arial', 11), width=20)
        entry.pack(side='left', padx=10)
        entry.focus()
        
        def confirmar():
            u = entry.get().strip()
            if not u:
                messagebox.showerror("Error", "Ingrese un usuario.")
                return
            
            usuario = buscar_usuario(u)
            if not usuario:
                messagebox.showerror("Error", "Usuario no encontrado.")
                return
            
            if usuario['activo'] == 0:
                messagebox.showwarning("Aviso", "El usuario ya estaba dado de baja.")
                return
            
            if messagebox.askyesno("⚠️ Confirmar",
                f"¿Dar de baja al usuario '{u}'?\n\n"
                f"Nombre: {usuario['nombre_completo']}\n"
                f"Rol: {usuario['rol'].upper()}"):
                resultado, mensaje = dar_baja_usuario(usuario['id'])
                if resultado:
                    messagebox.showinfo("Éxito", mensaje)
                    ventana.destroy()
                    self.ver_usuarios(activos=True)
                else:
                    messagebox.showerror("Error", mensaje)
        
        entry.bind('<Return>', lambda e: confirmar())
        
        tk.Button(ventana, text="🗑️ Confirmar Baja", bg='#f44336', fg='white',
                 font=('Arial', 11, 'bold'), padx=20, pady=8,
                 command=confirmar).pack(pady=10)
    
    def baja_con_usuario(self, usuario):
        """Baja directa"""
        u = buscar_usuario(usuario)
        if not u:
            return
        
        if messagebox.askyesno("⚠️ Confirmar",
            f"¿Dar de baja al usuario '{usuario}'?\n\n"
            f"Nombre: {u['nombre_completo']}\n"
            f"Rol: {u['rol'].upper()}"):
            resultado, mensaje = dar_baja_usuario(u['id'])
            if resultado:
                messagebox.showinfo("Éxito", mensaje)
                self.ver_usuarios(activos=True)
            else:
                messagebox.showerror("Error", mensaje)
    
    def reactivar_con_usuario(self, usuario):
        """Reactiva un usuario"""
        u = buscar_usuario(usuario)
        if not u:
            return
        
        if messagebox.askyesno("♻️ Reactivar", f"¿Reactivar al usuario '{usuario}'?"):
            resultado, mensaje = reactivar_usuario(u['id'])
            if resultado:
                messagebox.showinfo("Éxito", mensaje)
                self.ver_usuarios(activos=True)
            else:
                messagebox.showerror("Error", mensaje)


# ================================================================
# PUNTO DE ENTRADA
# ================================================================

if __name__ == "__main__":
    root = tk.Tk()
    app = AppUsuarios(root)
    root.mainloop()
