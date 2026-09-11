---
id: kb-004-erp-lentidao
titulo: ERP lento ao abrir telas ou gerar relatórios
categoria: software
tags: [erp, lentidao, desempenho, relatorio, travando, demora, timeout, financeiro]
servicos: [erp]
---
## Sintomas
- Telas do ERP demoram vários segundos para abrir; relatórios excedem o tempo limite.
- Lentidão concentrada em horários de fechamento (início e fim do mês).
- Outros sistemas funcionam normalmente para o mesmo usuário.

## Causa provável
Relatórios pesados executados em horário de pico, índices desatualizados no banco de dados, sessões presas
ou estação do usuário com poucos recursos.

## Procedimento
1. Perguntar se a lentidão afeta um usuário, uma equipe ou todos, e em quais telas ou relatórios.
2. Se for um único usuário: limpar cache do cliente ERP, verificar antivírus e memória disponível na estação.
3. Se for geral: verificar consumo do servidor de aplicação e do banco; identificar relatórios em execução prolongada.
4. Orientar o agendamento de relatórios pesados fora do horário comercial.
5. Registrar horários e relatórios envolvidos no chamado para análise de capacidade.

## Escalonamento
Lentidão generalizada em fechamento contábil impacta prazos legais: escalar para a equipe do ERP com prioridade alta.
