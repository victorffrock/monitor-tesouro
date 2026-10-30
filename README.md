# Monitor Tesouro

[![CI](https://github.com/victorffrock/monitor-tesouro/actions/workflows/ci.yml/badge.svg)](https://github.com/victorffrock/monitor-tesouro/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/victorffrock/monitor-tesouro)](https://github.com/victorffrock/monitor-tesouro/releases/latest)

Aplicação Linux para acompanhar taxas de compra e venda dos títulos Tesouro IPCA+ principal, com alertas por patamar, histórico local, notificações e resumo diário.

## Baixar

Obtenha a versão mais recente em [Releases](https://github.com/victorffrock/monitor-tesouro/releases/latest). O release inclui:

- `Monitor-Tesouro-x86_64.AppImage`: aplicativo gráfico com Python/Tkinter e dependências de runtime incluídos.
- `Monitor-Tesouro-x86_64.AppImage.zsync`: metadado para atualização incremental no Gear Lever/AppImageUpdate.
- `Monitor-Tesouro-sem-fuse.sh`: launcher opcional que usa extract-and-run quando FUSE não está disponível.

No Fedora Silverblue, marque o AppImage como executável e abra-o. Para usar o launcher sem FUSE, mantenha os dois arquivos na mesma pasta e execute `./Monitor-Tesouro-sem-fuse.sh`.

## Recursos

- Consulta o CSV diário oficial do Tesouro Transparente.
- Filtra Tesouro IPCA+ sem juros semestrais e apresenta compra, venda, PU e data-base.
- Detecta cruzamentos de alta e de queda nos patamares configurados.
- Guarda estado, histórico e logs em `~/.local/share/monitor-tesouro/`.
- Notifica na área de trabalho e, opcionalmente, por SMTP.
- Permite habilitar timer systemd de usuário para dias úteis às 18h30.
- Não exige dependências Python externas; requer Python 3.11+ no modo código-fonte.

## Dados e privacidade

O programa baixa dados públicos do Tesouro Transparente e mantém configuração, senha SMTP, estado, histórico e logs localmente. A senha de aplicativo é salva separadamente com permissão `0600`. Nenhum dado financeiro pessoal é coletado. Este projeto serve para monitoramento informativo, não é recomendação de investimento.

## Execução pelo código-fonte

Requer Python 3.11+; no Linux, instale também Tkinter (por exemplo, `python3-tk`). Para abrir a interface:

```bash
PYTHONPATH=src python -m monitor_tesouro
```

Execute os testes e as verificações de qualidade usadas na CI:

```bash
python -m pip install -e '.[dev]'
ruff check --select E4,E7,E9,F src tests
PYTHONPATH=src python -m unittest discover -s tests -v
python -m build
```

A CI repete os testes em Python 3.11, 3.12 e 3.13, instala o pacote construído e verifica o comando de terminal. O CodeQL analisa o código em pull requests e semanalmente.

## Build e publicação

O workflow de release gera o AppImage e seu `.zsync` quando uma GitHub Release é publicada. Crie uma release com tag `v*`; o workflow anexa os três artefatos. Para reproduzir localmente em Ubuntu 24.04/Debian equivalente, instale os pacotes listados em `packaging/README.md` e execute:

```bash
GITHUB_REPOSITORY=victorffrock/monitor-tesouro GITHUB_REF_NAME=v1.0.0 packaging/build_appimage.sh
```

O AppImage contém update information `gh-releases-zsync` apontando para a release mais recente deste repositório. O arquivo `.zsync` gerado é necessário para atualizações delta.

## Licença

GPL-3.0-only. Consulte [LICENSE](LICENSE).
