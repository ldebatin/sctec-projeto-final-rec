---
id: kb-010-acesso-negado-pasta
titulo: Acesso negado a pasta compartilhada ou unidade de rede
categoria: suporte
tags: [acesso negado, pasta compartilhada, permissao, unidade de rede, compartilhamento, grupo, ntfs, arquivos]
servicos: [servidor-arquivos, active-directory]
---
## Sintomas
- Mensagem "acesso negado" ao abrir uma pasta da rede que antes funcionava, ou ao acessar pasta de outra área.
- Unidade de rede aparece desconectada com um X vermelho.
- Colegas da mesma equipe acessam normalmente.

## Causa provável
Usuário fora do grupo de segurança que dá acesso à pasta (mudança de área, conta recriada), permissões
alteradas pelo dono da pasta ou credenciais antigas em cache na estação.

## Procedimento
1. Confirmar o caminho exato da pasta e se o acesso é novo ou deixou de funcionar.
2. Verificar a que grupo de segurança a pasta está vinculada e se o usuário pertence a ele.
3. Se for acesso novo, solicitar aprovação do gestor da área dona da pasta antes de incluir no grupo.
4. Após inclusão no grupo, orientar logoff e logon para atualizar o token de acesso.
5. Se a unidade estiver desconectada, reconectar pelo script de logon ou manualmente.

## Escalonamento
Perda de acesso de toda uma equipe indica alteração indevida de permissões: escalar para a equipe de
Identidade e registrar como possível incidente de segurança.
