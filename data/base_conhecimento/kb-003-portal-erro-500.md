---
id: kb-003-portal-erro-500
titulo: Portal de Clientes retorna erro 500 ou página em branco
categoria: software
tags: [portal, erro 500, indisponivel, fora do ar, pagina em branco, gateway, aplicacao web, clientes]
servicos: [portal-clientes]
---
## Sintomas
- Erro HTTP 500 ou página em branco em todas as telas do Portal de Clientes.
- Impacto em todos os usuários externos; login e consultas indisponíveis.
- Pode vir acompanhado de erro 502/504 no gateway.

## Causa provável
Falha na aplicação após deploy, esgotamento do pool de conexões com o banco de dados ou indisponibilidade
de um serviço dependente (API de Pagamentos, autenticação).

## Procedimento
1. Confirmar a abrangência: reproduzir em janela anônima e verificar o health check do portal.
2. Checar se houve deploy nas últimas horas; se sim, acionar rollback pelo runbook do serviço.
3. Verificar logs do gateway e da aplicação em busca de exceções recorrentes e de erros de conexão com o banco.
4. Verificar o status das dependências (API de Pagamentos, Active Directory federado).
5. Comunicar o incidente no canal de status e manter atualização a cada 30 minutos até normalizar.

## Escalonamento
Erro 500 generalizado em produção é incidente crítico: acionar imediatamente a equipe responsável pelo portal
e o plantão, com o horário de início e as evidências coletadas.
