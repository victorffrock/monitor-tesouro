# Contribuindo

1. Abra uma issue para discutir mudanças maiores ou alterações no formato do CSV.
2. Faça mudanças em uma branch e envie um pull request com objetivo, comportamento alterado e validação feita.
3. Instale os utilitários de qualidade e execute as mesmas verificações da CI:
   ```bash
   python -m pip install -e '.[dev]'
   ruff check --select E4,E7,E9,F src tests
   PYTHONPATH=src python -m unittest discover -s tests -v
   python -m build
   ```
4. Mantenha as dependências de runtime na biblioteca padrão e preserve a compatibilidade Python 3.11+.
5. Não inclua configurações pessoais, logs, histórico, senhas ou AppImages nos commits.

As alterações devem seguir o estilo do projeto e manter mensagens e documentação em português claro. O GitHub Actions executa os testes em Python 3.11–3.13, verifica lint e pacote, e analisa o código com CodeQL.
