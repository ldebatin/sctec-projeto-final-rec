---
id: kb-001-reset-senha-ad
titulo: Senha do Active Directory expirada ou conta bloqueada
categoria: suporte
tags: [senha, active directory, ad, expirada, bloqueio, login, autenticacao, windows]
servicos: [active-directory]
---
## Sintomas
- Usuário não consegue entrar no Windows ou em sistemas integrados ao AD (e-mail, VPN, intranet).
- Mensagens como "senha expirada", "conta bloqueada" ou "usuário ou senha inválidos".
- Ocorre tipicamente após 90 dias sem troca de senha ou após várias tentativas erradas.

## Causa provável
Política de expiração de senha (90 dias) ou bloqueio automático após 5 tentativas incorretas,
muitas vezes causado por dispositivo móvel com a senha antiga salva.

## Procedimento
1. Confirmar a identidade do solicitante pelo canal padrão (ramal cadastrado ou gestor).
2. No portal de autoatendimento, orientar o uso de "Esqueci minha senha"; se indisponível, resetar pelo console do AD.
3. Desbloquear a conta e exigir troca de senha no próximo logon.
4. Orientar a atualizar a senha no celular e em aplicativos que a armazenam para evitar novo bloqueio.
5. Registrar o atendimento no chamado e encerrar como resolvido.

## Escalonamento
Se o bloqueio se repetir em menos de 24 horas sem tentativa do usuário, escalar para a equipe de Identidade
para investigar sessões antigas ou tentativa de acesso indevido.
