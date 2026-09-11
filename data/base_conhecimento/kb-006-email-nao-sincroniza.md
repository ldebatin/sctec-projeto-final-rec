---
id: kb-006-email-nao-sincroniza
titulo: E-mail não sincroniza no Outlook ou no celular
categoria: suporte
tags: [email, outlook, sincronizacao, celular, caixa postal, cota, enviar, receber, exchange]
servicos: [email-corporativo]
---
## Sintomas
- Mensagens novas não aparecem no Outlook ou no aplicativo do celular.
- Erro ao enviar: "caixa postal cheia" ou "não foi possível conectar ao servidor".
- Webmail funciona normalmente.

## Causa provável
Cota da caixa postal atingida, senha do AD alterada e não atualizada no dispositivo, perfil do Outlook
corrompido ou modo offline ativado.

## Procedimento
1. Testar o webmail: se funcionar, o serviço está operacional e o problema é local ao cliente.
2. Verificar a cota da caixa postal; se cheia, orientar arquivamento ou limpeza da pasta Itens Excluídos.
3. Confirmar que a senha salva no dispositivo é a atual (ver artigo de senha do AD).
4. No Outlook, desativar "Trabalhar offline" e, se persistir, recriar o perfil.
5. No celular, remover e adicionar novamente a conta corporativa.

## Escalonamento
Se o webmail também falhar para vários usuários, tratar como incidente do serviço de e-mail e escalar
para a equipe de Colaboração.
