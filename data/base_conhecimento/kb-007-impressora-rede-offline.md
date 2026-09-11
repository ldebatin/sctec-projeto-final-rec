---
id: kb-007-impressora-rede-offline
titulo: Impressora de rede offline ou fila travada
categoria: infraestrutura
tags: [impressora, impressao, offline, fila, spooler, rede, toner, papel, driver]
servicos: []
---
## Sintomas
- Impressora aparece como "offline" para um ou vários usuários.
- Documentos ficam presos na fila e nada é impresso.
- Painel da impressora sem erro aparente.

## Causa provável
Endereço IP da impressora alterado por DHCP, serviço de spooler travado no servidor de impressão,
driver desatualizado ou problema físico (papel, toner, cabo de rede).

## Procedimento
1. Verificar no painel da impressora se há papel, toner e conexão de rede ativa.
2. Confirmar o IP atual da impressora e se corresponde ao configurado no servidor de impressão; fixar reserva no DHCP se necessário.
3. Reiniciar o serviço de spooler no servidor de impressão e limpar a fila.
4. Se apenas um usuário for afetado, reinstalar a impressora na estação a partir do servidor.
5. Testar impressão de página de configuração e registrar no chamado.

## Escalonamento
Falha em impressora de setor crítico (expedição, faturamento) com impacto operacional deve ser escalada
para a equipe de Suporte de Campo com prioridade alta.
