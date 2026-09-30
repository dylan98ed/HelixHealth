# generar_hash.py
import hashlib

def generar_hash(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

# Generar hashes para contraseñas comunes
passwords = ['admin123', 'medico123', 'enfermero123', 'admin2024']

print("=" * 70)
print("GENERADOR DE HASHES SHA-256")
print("=" * 70)

for pwd in passwords:
    hash_val = generar_hash(pwd)
    print(f"\nContraseña: {pwd}")
    print(f"Hash: {hash_val}")
    print(f"SQL: '{hash_val}'")

print("\n" + "=" * 70)
