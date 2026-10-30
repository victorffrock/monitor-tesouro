# Build do AppImage

Alvo inicial: Linux x86_64, construído em Ubuntu 24.04. O AppImage inclui a versão de Python do sistema de build, GTK 4, libadwaita, PyGObject and Cairo, OpenSSL e bibliotecas compartilhadas não pertencentes à glibc necessárias ao programa. A glibc fica no sistema hospedeiro para preservar compatibilidade com distribuições Linux.

Dependências Ubuntu: `python3`, `python3-tk`, `libssl3t64` (ou `libssl3`), `libtcl8.6`, `libtk8.6`, `libxss1`, `libzstd1`, `librsvg2-bin`, `zsync`, `squashfs-tools`, `file`, `curl`, `ca-certificates`.

O script baixa appimagetool e o runtime Type 2 de fontes oficiais, valida SHA-256 fixados no próprio script, empacota o AppDir e gera o `.zsync`. Atualize deliberadamente os hashes ao atualizar ferramentas.
