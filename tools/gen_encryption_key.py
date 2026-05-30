"""
Gera uma chave Fernet para CREDENTIAL_ENCRYPTION_KEY.

Ver ADR-014 (docs/adr/014-cripto-segredos-usuario.md).

Uso:
    python tools/gen_encryption_key.py

Imprime no stdout uma chave urlsafe-base64 de 44 caracteres. Use para o setup
inicial do dev (colar no .env) e para a primeira configuração no Render
(painel → env var CREDENTIAL_ENCRYPTION_KEY, sync: false).

NUNCA commitar o valor gerado em lugar nenhum.
"""

from cryptography.fernet import Fernet


def main() -> None:
    print(Fernet.generate_key().decode())


if __name__ == "__main__":
    main()
