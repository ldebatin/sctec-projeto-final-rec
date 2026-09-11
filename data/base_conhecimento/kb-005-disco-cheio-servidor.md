---
id: kb-005-disco-cheio-servidor
titulo: Servidor com disco cheio ou espaço crítico
categoria: infraestrutura
tags: [disco, espaco, armazenamento, servidor, cheio, logs, alerta, particao, arquivos]
servicos: [servidor-arquivos, banco-dados]
---
## Sintomas
- Alertas de monitoramento de uso de disco acima de 90%.
- Aplicações falham ao gravar arquivos, banco de dados recusa novas escritas, serviços param de iniciar.
- Usuários relatam erro ao salvar na pasta compartilhada.

## Causa provável
Crescimento de logs sem rotação, backups antigos acumulados na mesma partição, arquivos temporários
não limpos ou crescimento legítimo de dados sem expansão planejada.

## Procedimento
1. Identificar a partição afetada e os maiores diretórios (logs, temp, backups).
2. Liberar espaço com segurança: compactar ou remover logs antigos já coletados, limpar temporários, mover backups para o storage de longa retenção.
3. Confirmar que a rotação de logs está configurada e ativa.
4. Se o crescimento for legítimo, abrir solicitação de expansão de disco com previsão de consumo.
5. Validar que os serviços afetados voltaram a operar e registrar o espaço liberado.

## Escalonamento
Disco cheio em servidor de banco de dados de produção é crítico: acionar a equipe de Infraestrutura e o DBA
antes de qualquer remoção de arquivos.
