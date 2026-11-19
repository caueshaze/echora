"""Provision the first administrator; use an operator-only PostgreSQL connection."""
import argparse
import getpass
import os
import sys
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from backend.app.services.bootstrap_service import bootstrap_admin


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--email', required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    url = os.environ.get('MIGRATION_DATABASE_URL')
    if not url:
        parser.error('MIGRATION_DATABASE_URL é obrigatória')
    if not sys.stdin.isatty():
        parser.error('Um terminal interativo é obrigatório')
    password = getpass.getpass('Senha temporária: ')
    if password != getpass.getpass('Confirme a senha temporária: '):
        parser.error('As senhas não coincidem')
    engine = create_engine(url, hide_parameters=True)
    try:
        try:
            with Session(engine) as db, db.begin():
                user_id = bootstrap_admin(db, email=args.email, full_name=args.name, password=password)
        except ValidationError:
            parser.error('Dados inválidos; confira e-mail, nome e política de senha')
        print(f'Administrador criado: {user_id}. A troca de senha é obrigatória.')
    finally:
        engine.dispose()

if __name__ == '__main__':
    main()
