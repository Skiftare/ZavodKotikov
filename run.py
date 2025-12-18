#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Точка входа для запуска приложения ZavodKotikov
"""

if __name__ == "__main__":
    import sys
    import os

    # Исправляем кодировку для Windows
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')

    from src.app import app

    port = int(os.getenv("FLASK_PORT", "5000"))
    host = os.getenv("FLASK_HOST", "0.0.0.0")

    print(f"\n🐱 Запуск Завода Котиков на {host}:{port}\n")
    app.run(debug=False, host=host, port=port)

