# Build do AppImage

O build x86_64 roda em Ubuntu 24.04. O artefato inclui Python, GTK 4, libadwaita, PyGObject, Cairo e o fechamento das bibliotecas compartilhadas usadas por esses componentes. A glibc continua sendo fornecida pelo sistema hospedeiro.

Dependências de build no Ubuntu: `python3`, `python3-gi`, `python3-gi-cairo`, `gir1.2-gtk-4.0`, `gir1.2-adw-1`, `libgtk-4-1`, `libadwaita-1-0`, `libzstd1`, `librsvg2-bin`, `xvfb`, `zsync`, `squashfs-tools`, `file`, `curl` e `ca-certificates`.

Antes de criar a imagem, o script executa `packaging/gtk_smoke.py` sob Xvfb usando somente o runtime montado no AppDir. Esse passo instancia a janela e renderiza duas séries de taxas; assim, problemas de Cairo ou de bibliotecas empacotadas falham no workflow de release antes da publicação do artefato.

O script baixa appimagetool e o runtime Type 2 de fontes oficiais e valida os SHA-256 fixados nele. Atualize os hashes deliberadamente ao atualizar essas ferramentas.
