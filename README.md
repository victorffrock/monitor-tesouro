# Monitor Tesouro

[![CI](https://github.com/victorffrock/monitor-tesouro/actions/workflows/ci.yml/badge.svg)](https://github.com/victorffrock/monitor-tesouro/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/victorffrock/monitor-tesouro)](https://github.com/victorffrock/monitor-tesouro/releases/latest)

Aplicação Linux para acompanhar taxas dos títulos Tesouro IPCA+ principal, com um gráfico histórico de compra e venda, alertas simples e dados guardados localmente.

## Baixar

Obtenha a versão mais recente em [Releases](https://github.com/victorffrock/monitor-tesouro/releases/latest). O release inclui:

- `Monitor-Tesouro-x86_64.AppImage`: aplicativo gráfico com Python/Tkinter e dependências de runtime incluídos.
- `Monitor-Tesouro-x86_64.AppImage.zsync`: metadado para atualização incremental no Gear Lever/AppImageUpdate.
- `Monitor-Tesouro-sem-fuse.sh`: launcher opcional que usa extract-and-run quando FUSE não está disponível.

No Fedora Silverblue, marque o AppImage como executável e abra-o. Para usar o launcher sem FUSE, mantenha os dois arquivos na mesma pasta e execute `./Monitor-Tesouro-sem-fuse.sh`.

## Acompanhar as taxas

A tela principal mostra um gráfico amplo com a evolução das taxas de compra e venda. Escolha o vencimento e o período que deseja ver. A tabela abaixo mostra as taxas mais recentes; selecione uma linha para abrir o histórico daquele título.

O histórico é criado a partir das atualizações feitas enquanto o app está instalado e fica em `~/.local/share/monitor-tesouro/historico.csv`. Registros anteriores são preservados ao atualizar o aplicativo. Os dados históricos não são baixados de outro serviço, então o gráfico vai ganhando pontos com o uso.

## Recursos

- Consulta o CSV diário oficial do Tesouro Transparente.
- Mostra taxas de compra e venda, preço unitário e data-base.
- Compara a evolução das taxas ao longo do tempo por vencimento.
- Detecta cruzamentos dos patamares configurados e pode exibir notificações na área de trabalho.
- Guarda estado, histórico e logs localmente em `~/.local/share/monitor-tesouro/`.
- Não envia e-mails nem exige dependências Python externas; requer Python 3.11+ no modo código-fonte.

## Dados e privacidade

O programa consulta dados públicos do Tesouro Transparente e mantém configuração, histórico e logs localmente. Notificações, se habilitadas, usam a área de trabalho do Linux. O app não pede endereço de e-mail nem senha SMTP. Este projeto serve para monitoramento informativo, não é recomendação de investimento.

## Execução pelo código-fonte

Requer Python 3.11+; no Linux, instale também Tkinter (por exemplo, `python3-tk`). Para abrir a interface:

```bash
PYTHONPATH=src python -m monitor_tesouro
```

Execute os testes da biblioteca padrão:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Build e publicação

O workflow de release gera o AppImage e seu `.zsync` quando uma GitHub Release é publicada. Crie uma release com tag `v*`; o workflow anexa os três artefatos. Para reproduzir localmente em Ubuntu 24.04/Debian equivalente, instale os pacotes listados em `packaging/README.md` e execute:

```bash
GITHUB_REPOSITORY=victorffrock/monitor-tesouro GITHUB_REF_NAME=v1.0.0 packaging/build_appimage.sh
```

O AppImage contém update information `gh-releases-zsync` apontando para a release mais recente deste repositório. O arquivo `.zsync` gerado é necessário para atualizações delta.

## Licença

GPL-3.0-only. Consulte [LICENSE](LICENSE).
