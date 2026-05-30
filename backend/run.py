"""Punto de entrada para correr la aplicación en desarrollo."""
from app import create_app

app = create_app()

if __name__ == '__main__':
    # debug=True recarga automáticamente al editar archivos
    app.run(host='0.0.0.0', port=5000, debug=True)
