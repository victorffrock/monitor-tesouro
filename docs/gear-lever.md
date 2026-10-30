# Atualizações pelo Gear Lever

O build usa `appimagetool -u` para embutir no AppImage a origem `gh-releases-zsync|victorffrock|monitor-tesouro|latest|Monitor-Tesouro-x86_64.AppImage.zsync`. O workflow anexa à mesma GitHub Release tanto o AppImage quanto o `.zsync` com esse nome fixo.

No Gear Lever, adicione o AppImage da página Releases. A ferramenta lê o update information embutido, consulta a release mais recente e aplica a atualização delta com o `.zsync`. O AppImage e o arquivo `.zsync` precisam permanecer como assets da release mais recente. Não renomeie o asset sem atualizar o padrão do build.

Se for configurar manualmente uma origem no Gear Lever, use o repositório `victorffrock/monitor-tesouro` e mantenha a seleção na release mais recente.
