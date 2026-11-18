"""Create the first owner from a private server console, never from public UI."""

from getpass import getpass

from database import store
from services import auth


def main():
    if store.identity_user_count():
        raise SystemExit("Acesso principal já configurado.")
    username = input("Usuário principal: ").strip()
    password = getpass("Senha (mínimo 12 caracteres): ")
    confirmation = getpass("Confirme a senha: ")
    if password != confirmation:
        raise SystemExit("As senhas não coincidem.")
    store.initialize()
    auth.create_account(username, password, role="owner")
    print("Acesso principal criado. Abra o portal e entre com sua senha.")


if __name__ == "__main__":
    main()
