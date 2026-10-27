# ================================================================
# _Menu_principal_app.pyw
# OPENHIS-UNLaM - MENÚ PRINCIPAL CON LOGIN Y AUDITORÍA
# ================================================================
#
# FUNCIONALIDADES:
#   ✅ Login obligatorio al iniciar
#   ✅ Validación contra tabla Usuarios
#   ✅ Hash SHA-256 de contraseñas
#   ✅ Registro de último acceso
#   ✅ AUDITORÍA: Login y Logout
#   ✅ GUARDAR SESIÓN: usuario actual en archivo .sesion
#   ✅ Menú con módulos filtrados por rol
#   ✅ Botón "Cerrar Sesión" que vuelve al login
#   ✅ Módulo de gestión de usuarios (solo admin)
#
# USUARIOS DE PRUEBA:
#   admin / admin123 (Administrador)
#   medico / medico123 (Médico)
#   enfermero / enfermero123 (Enfermero)
# ================================================================

import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk
import subprocess
import sys
import os
import hashlib
from datetime import datetime

# ----------------------------------------------------------------
# IMPORTAR FUNCIONES DE AUDITORÍA
# ----------------------------------------------------------------
from Auditoria_utiles import (
    auditar_login,
    auditar_logout,
    guardar_sesion,
    limpiar_sesion,
    contar_auditoria
)


# ================================================================
# CONEXIÓN A BASE DE DATOS
# ================================================================

def conectar_bd():
    return sqlite3.connect('BD/Salud.db')


def hashear_password(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


# ================================================================
# AUTENTICACIÓN
# ================================================================

def autenticar_usuario(usuario, password):
    """Autentica un usuario contra la base de datos"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        password_hash = hashear_password(password)

        cursor.execute("""
            SELECT id, usuario, nombre_completo, email, rol, activo
            FROM Usuarios 
            WHERE usuario = ? AND password_hash = ?
        """, (usuario, password_hash))

        resultado = cursor.fetchone()
        conexion.close()

        if resultado:
            if resultado[5] == 0:
                return {'error': 'Usuario inactivo. Contacte al administrador.'}
            return {
                'id': resultado[0],
                'usuario': resultado[1],
                'nombre_completo': resultado[2],
                'email': resultado[3],
                'rol': resultado[4]
            }
        return None
    except Exception as e:
        print(f"[ERROR] Error en autenticación: {e}")
        return None


def registrar_acceso(usuario_id):
    """Registra el último acceso del usuario"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("""
            UPDATE Usuarios SET ultimo_acceso = CURRENT_TIMESTAMP WHERE id = ?
        """, (usuario_id,))
        conexion.commit()
        conexion.close()
    except Exception as e:
        print(f"[ERROR] Error al registrar acceso: {e}")


# ================================================================
# CONFIGURACIÓN DE MÓDULOS Y ROLES
# ================================================================

ROLES_PERMITIDOS = {
    'Pacientes': ['admin', 'medico', 'enfermero', 'administrativo'],
    'Profesionales': ['admin', 'administrativo'],
    'Turnos': ['admin', 'administrativo'],
    'Signos Vitales': ['admin', 'medico', 'enfermero'],
    'Prescripciones': ['admin', 'medico'],
    'Historia Clínica': ['admin', 'medico', 'enfermero'],
    'Tablas Maestras': ['admin'],
    'Exportar XML': ['admin'],
    'Importar XML': ['admin'],
    'Usuarios': ['admin']
}


MODULOS = {
    'ADMINISTRACIÓN': {
        'color': '#2196F3',
        'icono': '🟦',
        'modulos': [
            {'nombre': 'Pacientes', 'archivo': '_Pacientes_app.pyw',
             'descripcion': 'Gestión de pacientes', 'icono': '👤'},
            {'nombre': 'Profesionales', 'archivo': '_Profesionales_app.pyw',
             'descripcion': 'Gestión de profesionales', 'icono': '👨‍⚕️'},
            {'nombre': 'Turnos', 'archivo': None,
             'descripcion': 'Gestión de turnos (próximamente)', 'icono': '📅'}
        ]
    },
    'CLÍNICA': {
        'color': '#4CAF50',
        'icono': '🟩',
        'modulos': [
            {'nombre': 'Signos Vitales', 'archivo': '_Signos_vitales_app.pyw',
             'descripcion': 'Registro de signos vitales', 'icono': '❤️'},
            {'nombre': 'Prescripciones', 'archivo': '_Prescripciones_app.pyw',
             'descripcion': 'Prescripción de medicamentos', 'icono': '💊'},
            {'nombre': 'Historia Clínica', 'archivo': None,
             'descripcion': 'HCE (próximamente)', 'icono': '📋'}
        ]
    },
    'TABLAS MAESTRAS': {
        'color': '#FF9800',
        'icono': '🟨',
        'modulos': [
            {'nombre': 'Tablas Maestras', 'archivo': '_Tablas_maestras.pyw',
             'descripcion': 'Especialidades, SNOMED CT y Fármacos', 'icono': '📚'}
        ]
    },
    'INTEROPERABILIDAD': {
        'color': '#E91E63',
        'icono': '🟥',
        'modulos': [
            {'nombre': 'Exportar XML', 'archivo': None,
             'descripcion': 'Exportar a FHIR XML', 'icono': '📤'},
            {'nombre': 'Importar XML', 'archivo': None,
             'descripcion': 'Importar datos externos', 'icono': '🏥'}
        ]
    },
    'SEGURIDAD': {
        'color': '#9C27B0',
        'icono': '🔐',
        'modulos': [
            {'nombre': 'Usuarios', 'archivo': '_Usuarios_app.pyw',
             'descripcion': 'Gestión de usuarios y permisos', 'icono': '👥'}
        ]
    }
}


# ================================================================
# VENTANA DE LOGIN
# ================================================================

class VentanaLogin:
    """Ventana de login que se muestra antes del menú"""

    def __init__(self, root):
        self.root = root
        self.root.title("OpenHIS-UNLaM - Iniciar Sesión")
        self.root.geometry("450x520")
        self.root.configure(bg='#003366')
        self.root.resizable(False, False)

        # Centrar
        self.root.update_idletasks()
        ancho = self.root.winfo_width()
        alto = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (ancho // 2)
        y = (self.root.winfo_screenheight() // 2) - (alto // 2)
        self.root.geometry(f'{ancho}x{alto}+{x}+{y}')

        self.usuario_autenticado = None

        self.crear_interfaz()

    def crear_interfaz(self):
        """Crea la interfaz de login"""
        frame = tk.Frame(self.root, bg='#003366')
        frame.pack(expand=True, fill='both', padx=40, pady=30)

        # Logo
        tk.Label(frame, text="🏥", font=('Arial', 48),
                bg='#003366', fg='white').pack(pady=(10, 5))

        tk.Label(frame, text="OpenHIS-UNLaM", font=('Arial', 20, 'bold'),
                bg='#003366', fg='white').pack()

        tk.Label(frame, text="Sistema de Información Hospitalaria",
                font=('Arial', 10), bg='#003366', fg='#B0C4DE').pack(pady=(0, 20))

        # Usuario
        tk.Label(frame, text="Usuario", font=('Arial', 11, 'bold'),
                bg='#003366', fg='white', anchor='w').pack(fill='x', pady=(10, 3))

        self.entry_usuario = tk.Entry(frame, font=('Arial', 12), width=25,
                                      relief='flat', bd=5)
        self.entry_usuario.pack(fill='x', ipady=5)

        # Password
        tk.Label(frame, text="Contraseña", font=('Arial', 11, 'bold'),
                bg='#003366', fg='white', anchor='w').pack(fill='x', pady=(15, 3))

        self.entry_password = tk.Entry(frame, font=('Arial', 12), width=25,
                                       show='●', relief='flat', bd=5)
        self.entry_password.pack(fill='x', ipady=5)

        # Enter para login
        self.entry_password.bind('<Return>', lambda e: self.login())
        self.entry_usuario.bind('<Return>', lambda e: self.entry_password.focus())

        # Botón Login
        tk.Button(frame, text="🔐 INICIAR SESIÓN", font=('Arial', 12, 'bold'),
                 bg='#4CAF50', fg='white', padx=20, pady=10,
                 relief='flat', cursor='hand2',
                 command=self.login).pack(fill='x', pady=(25, 10))

        # Info de usuarios de prueba
        frame_info = tk.Frame(frame, bg='#002244', relief='solid', bd=1)
        frame_info.pack(fill='x', pady=(15, 0))

        tk.Label(frame_info, text="ℹ️  Usuarios de prueba:",
                font=('Arial', 9, 'bold'), bg='#002244', fg='#FFD700').pack(anchor='w', padx=10, pady=(5, 0))

        tk.Label(frame_info,
                text="admin / admin123 (Admin)\nmedico / medico123 (Médico)\nenfermero / enfermero123 (Enfermero)",
                font=('Arial', 9), bg='#002244', fg='white',
                justify='left').pack(anchor='w', padx=10, pady=(0, 5))

        self.entry_usuario.focus()

    def login(self):
        """Intenta autenticar al usuario"""
        usuario = self.entry_usuario.get().strip().lower()
        password = self.entry_password.get()

        if not usuario or not password:
            messagebox.showwarning("Campos vacíos",
                "Por favor, complete usuario y contraseña.")
            return

        resultado = autenticar_usuario(usuario, password)

        if resultado is None:
            messagebox.showerror("Error de autenticación",
                "❌ Usuario o contraseña incorrectos.\n\nIntente nuevamente.")
            self.entry_password.delete(0, tk.END)
            self.entry_password.focus()
            return

        if isinstance(resultado, dict) and 'error' in resultado:
            messagebox.showerror("Error", resultado['error'])
            return

        # ✅ LOGIN EXITOSO
        self.usuario_autenticado = resultado
        registrar_acceso(resultado['id'])

        # ✅ GUARDAR SESIÓN para que los módulos sepan quién es el usuario
        guardar_sesion(resultado['id'], resultado['nombre_completo'])

        # ✅ AUDITAR LOGIN
        auditar_login(
            usuario_id=resultado['id'],
            usuario_nombre=resultado['nombre_completo'],
            usuario_login=resultado['usuario']
        )

        print(f"[INFO] Login exitoso: {resultado['usuario']} ({resultado['rol']})")
        print(f"[INFO] Sesión guardada en .sesion")

        # Cerrar ventana de login y abrir menú
        self.root.destroy()


# ================================================================
# MENÚ PRINCIPAL
# ================================================================

class MenuPrincipal:
    """Menú principal con filtrado por rol"""

    def __init__(self, root, usuario):
        self.root = root
        self.usuario = usuario
        self.root.title(f"OpenHIS-UNLaM - {usuario['nombre_completo']}")
        self.root.geometry("1150x750")
        self.root.configure(bg='#f0f0f0')
        self.root.minsize(900, 600)

        # Centrar
        self.root.update_idletasks()
        ancho = self.root.winfo_width()
        alto = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (ancho // 2)
        y = (self.root.winfo_screenheight() // 2) - (alto // 2)
        self.root.geometry(f'{ancho}x{alto}+{x}+{y}')

        self.frame_principal = tk.Frame(self.root, bg='#f0f0f0')
        self.frame_principal.pack(fill='both', expand=True, padx=20, pady=20)

        self.crear_encabezado()
        self.crear_bienvenida()
        self.crear_modulos()
        self.crear_barra_estado()

    def crear_encabezado(self):
        """Encabezado con info del usuario"""
        frame_header = tk.Frame(self.frame_principal, bg='#003366', height=80)
        frame_header.pack(fill='x', pady=(0, 15))
        frame_header.pack_propagate(False)

        # Izquierda: Logo
        frame_izq = tk.Frame(frame_header, bg='#003366')
        frame_izq.pack(side='left', padx=20, pady=10)

        tk.Label(frame_izq, text="🏥 OpenHIS-UNLaM",
                font=('Arial', 20, 'bold'), bg='#003366', fg='white').pack(anchor='w')
        tk.Label(frame_izq, text="Sistema de Información Hospitalaria",
                font=('Arial', 10), bg='#003366', fg='#B0C4DE').pack(anchor='w')

        # Centro: Fecha
        frame_centro = tk.Frame(frame_header, bg='#003366')
        frame_centro.pack(side='left', expand=True, pady=20)

        self.label_fecha = tk.Label(frame_centro, text="", font=('Arial', 9),
                                    bg='#003366', fg='#B0C4DE')
        self.label_fecha.pack()
        self.actualizar_fecha()

        # Derecha: Info usuario
        frame_der = tk.Frame(frame_header, bg='#003366')
        frame_der.pack(side='right', padx=20, pady=10)

        tk.Label(frame_der, text=f"👤 {self.usuario['nombre_completo']}",
                font=('Arial', 11, 'bold'), bg='#003366', fg='white').pack(anchor='e')

        color_rol = {
            'admin': '#FFD700',
            'medico': '#87CEEB',
            'enfermero': '#98FB98',
            'administrativo': '#FFA07A'
        }.get(self.usuario['rol'], 'white')

        tk.Label(frame_der, text=f"🔑 {self.usuario['rol'].upper()}",
                font=('Arial', 9, 'bold'), bg='#003366', fg=color_rol).pack(anchor='e')

    def actualizar_fecha(self):
        """Actualiza fecha y hora"""
        ahora = datetime.now()
        texto = ahora.strftime("%A %d/%m/%Y - %H:%M:%S").capitalize()
        self.label_fecha.config(text=texto)
        self.root.after(1000, self.actualizar_fecha)

    def crear_bienvenida(self):
        """Mensaje de bienvenida"""
        frame = tk.Frame(self.frame_principal, bg='#f0f0f0')
        frame.pack(fill='x', pady=(0, 15))

        tk.Label(frame, text=f"Bienvenido/a, {self.usuario['nombre_completo']}",
                font=('Arial', 15, 'bold'), bg='#f0f0f0', fg='#003366').pack()

        tk.Label(frame, text="Seleccione un módulo para comenzar a trabajar",
                font=('Arial', 10), bg='#f0f0f0', fg='#666666').pack(pady=3)

    def crear_modulos(self):
        """Crea los botones de módulos filtrados por rol"""
        canvas = tk.Canvas(self.frame_principal, bg='#f0f0f0', highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.frame_principal, orient='vertical', command=canvas.yview)
        frame_scroll = tk.Frame(canvas, bg='#f0f0f0')

        frame_scroll.bind('<Configure>',
            lambda e: canvas.configure(scrollregion=canvas.bbox('all')))

        canvas.create_window((0, 0), window=frame_scroll, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Crear categorías
        for categoria, datos in MODULOS.items():
            modulos_permitidos = [
                m for m in datos['modulos']
                if self.usuario['rol'] in ROLES_PERMITIDOS.get(m['nombre'], [])
            ]

            if modulos_permitidos:
                self.crear_categoria(frame_scroll, categoria, datos, modulos_permitidos)

    def crear_categoria(self, parent, nombre_categoria, datos, modulos):
        """Crea una categoría con sus módulos filtrados"""
        frame_cat = tk.LabelFrame(
            parent,
            text=f" {datos['icono']}  {nombre_categoria} ",
            font=('Arial', 13, 'bold'),
            bg='#f0f0f0',
            fg=datos['color'],
            padx=15,
            pady=15,
            relief='groove',
            bd=2
        )
        frame_cat.pack(fill='x', padx=10, pady=8)

        frame_botones = tk.Frame(frame_cat, bg='#f0f0f0')
        frame_botones.pack(fill='x')

        for i, modulo in enumerate(modulos):
            fila = i // 3
            columna = i % 3
            self.crear_boton_modulo(frame_botones, modulo, datos['color'], fila, columna)

    def crear_boton_modulo(self, parent, modulo, color, fila, columna):
        """Crea un botón de módulo"""
        disponible = modulo['archivo'] is not None and os.path.exists(modulo['archivo']) if modulo['archivo'] else False

        bg_color = color if disponible else '#BDBDBD'
        fg_color = 'white' if disponible else '#666666'

        frame = tk.Frame(parent, bg='#f0f0f0', padx=8, pady=8)
        frame.grid(row=fila, column=columna, sticky='nsew', padx=5, pady=5)

        btn = tk.Button(
            frame,
            text=f"{modulo['icono']}\n\n{modulo['nombre']}",
            font=('Arial', 11, 'bold'),
            bg=bg_color,
            fg=fg_color,
            width=18,
            height=4,
            relief='raised',
            bd=3,
            cursor='hand2' if disponible else 'arrow',
            command=lambda: self.abrir_modulo(modulo['archivo'], modulo['nombre'])
        )
        btn.pack()

        if disponible:
            def on_enter(e):
                btn.config(bg=self.oscurecer_color(color))
            def on_leave(e):
                btn.config(bg=color)
            btn.bind('<Enter>', on_enter)
            btn.bind('<Leave>', on_leave)

        desc = modulo['descripcion']
        if len(desc) > 40:
            desc = desc[:37] + '...'

        tk.Label(frame, text=desc, font=('Arial', 8),
                bg='#f0f0f0', fg='#666666',
                wraplength=160, justify='center').pack(pady=(3, 0))

        parent.grid_columnconfigure(columna, weight=1)

    def oscurecer_color(self, color_hex):
        """Oscurece un color para el hover"""
        color_hex = color_hex.lstrip('#')
        r, g, b = tuple(int(color_hex[i:i+2], 16) for i in (0, 2, 4))
        r = max(0, int(r * 0.85))
        g = max(0, int(g * 0.85))
        b = max(0, int(b * 0.85))
        return f'#{r:02x}{g:02x}{b:02x}'

    def abrir_modulo(self, archivo, nombre):
        """Abre un módulo en un proceso independiente"""
        if archivo is None:
            messagebox.showinfo("Módulo no disponible",
                f"El módulo '{nombre}' estará disponible en una próxima versión.")
            return

        if not os.path.exists(archivo):
            messagebox.showerror("Error",
                f"No se encontró el archivo:\n{archivo}\n\n"
                f"Asegúrese de que el módulo esté en la misma carpeta.")
            return

        try:
            subprocess.Popen([sys.executable, archivo])
            print(f"[INFO] Módulo abierto: {archivo}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el módulo:\n{e}")

    def crear_barra_estado(self):
        """Barra inferior con info del sistema"""
        frame = tk.Frame(self.frame_principal, bg='#003366', height=30)
        frame.pack(fill='x', pady=(15, 0))
        frame.pack_propagate(False)

        tk.Label(frame, text="✅ OpenHIS-UNLaM v0.5 - Sprint 3 + Auditoría",
                font=('Arial', 9), bg='#003366', fg='white').pack(side='left', padx=15)

        # Contador de auditoría
        try:
            total_aud = contar_auditoria()
            tk.Label(frame, text=f"📋 {total_aud} registros de auditoría",
                    font=('Arial', 9), bg='#003366', fg='#B0C4DE').pack(side='left', padx=15)
        except:
            pass

        # Botones a la derecha
        tk.Button(frame, text="🚪 Cerrar Sesión", bg='#FF9800', fg='white',
                 font=('Arial', 9, 'bold'), padx=10, pady=2,
                 command=self.cerrar_sesion).pack(side='right', padx=5, pady=4)

        tk.Button(frame, text="❌ Salir", bg='#f44336', fg='white',
                 font=('Arial', 9, 'bold'), padx=10, pady=2,
                 command=self.salir).pack(side='right', padx=5, pady=4)

    def cerrar_sesion(self):
        """Cierra la sesión, audita logout y vuelve al login"""
        if messagebox.askyesno("Cerrar Sesión", "¿Está seguro de cerrar la sesión?"):
            # ✅ AUDITAR LOGOUT
            auditar_logout(
                usuario_id=self.usuario['id'],
                usuario_nombre=self.usuario['nombre_completo'],
                usuario_login=self.usuario['usuario']
            )

            # ✅ LIMPIAR SESIÓN
            limpiar_sesion()

            print(f"[INFO] Logout: {self.usuario['usuario']}")

            self.root.destroy()
            iniciar_aplicacion()

    def salir(self):
        """Cierra el sistema completo (también audita logout)"""
        if messagebox.askyesno("Salir", "¿Está seguro de cerrar el sistema?"):
            # ✅ AUDITAR LOGOUT al salir del sistema
            auditar_logout(
                usuario_id=self.usuario['id'],
                usuario_nombre=self.usuario['nombre_completo'],
                usuario_login=self.usuario['usuario']
            )

            # ✅ LIMPIAR SESIÓN
            limpiar_sesion()

            self.root.destroy()
            sys.exit(0)


# ================================================================
# INICIAR APLICACIÓN
# ================================================================

def iniciar_aplicacion():
    """Inicia la aplicación desde el login"""
    root_login = tk.Tk()
    login = VentanaLogin(root_login)
    root_login.mainloop()

    # Si el login fue exitoso, abrir el menú
    if login.usuario_autenticado:
        root_menu = tk.Tk()
        app = MenuPrincipal(root_menu, login.usuario_autenticado)
        root_menu.mainloop()


# ================================================================
# PUNTO DE ENTRADA
# ================================================================

if __name__ == "__main__":
    iniciar_aplicacion()
