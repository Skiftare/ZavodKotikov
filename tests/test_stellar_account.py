#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тест проверки аккаунта Stellar
"""

import os
from dotenv import load_dotenv

load_dotenv()

print("=" * 70)
print("🧪 ТЕСТИРОВАНИЕ STELLAR PAYMENT GATEWAY")
print("=" * 70)

# Проверяем конфигурацию
print("\n📋 Конфигурация:")
print(f"  USE_STELLAR_PAYMENT: {os.getenv('USE_STELLAR_PAYMENT', 'false')}")
print(f"  STELLAR_NETWORK: {os.getenv('STELLAR_NETWORK', 'testnet')}")
print(f"  STELLAR_DESTINATION_ADDRESS: {os.getenv('STELLAR_DESTINATION_ADDRESS', 'NOT SET')}")

use_stellar = os.getenv('USE_STELLAR_PAYMENT', 'false').lower() == 'true'

if not use_stellar:
    print("\n⚠️  Stellar payments отключены (USE_STELLAR_PAYMENT=false)")
    print("   Включите в .env файле для тестирования")
    exit(0)

print("\n" + "=" * 70)
print("🚀 Инициализация Stellar Gateway...")
print("=" * 70 + "\n")

try:
    from payment_gateway import StellarPaymentGateway

    gateway = StellarPaymentGateway()

    print("\n" + "=" * 70)
    print("📊 ПОЛУЧЕНИЕ АКТУАЛЬНОЙ ИНФОРМАЦИИ ОБ АККАУНТЕ")
    print("=" * 70 + "\n")

    account_info = gateway.get_account_info()

    if account_info is None:
        print("❌ Не удалось получить информацию об аккаунте")
    elif not account_info.get('exists', False):
        print(f"❌ Аккаунт не существует в сети: {account_info.get('id')}")
        print("\n💡 Для активации аккаунта в testnet:")
        print(f"   https://friendbot.stellar.org?addr={account_info.get('id')}")
    else:
        print("✅ Аккаунт активен и готов принимать платежи!")
        print(f"\n📝 ID: {account_info['id']}")
        print(f"🔢 Sequence: {account_info['sequence']}")
        print(f"📦 Subentries: {account_info['subentry_count']}")

        print(f"\n💰 Балансы:")
        for balance in account_info['balances']:
            if balance['is_native']:
                print(f"   • {balance['asset']}: {balance['balance']:.7f}")
            else:
                issuer_short = balance['issuer'][:8] + "..."
                print(f"   • {balance['asset']}: {balance['balance']:.7f} (Issuer: {issuer_short})")

    print("\n" + "=" * 70)
    print("🛑 Остановка мониторинга...")
    print("=" * 70)

    gateway.stop()
    print("✅ Gateway остановлен")

except Exception as e:
    print(f"\n❌ ОШИБКА: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("✅ ТЕСТ ЗАВЕРШЕН")
print("=" * 70)

