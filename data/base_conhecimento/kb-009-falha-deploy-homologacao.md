---
id: kb-009-falha-deploy-homologacao
titulo: Falha de deploy ou pipeline em homologação
categoria: software
tags: [deploy, pipeline, homologacao, build, ci, testes, rollback, versao, release]
servicos: [portal-clientes, erp, api-pagamentos]
---
## Sintomas
- Pipeline termina com erro na etapa de build, testes ou publicação.
- Aplicação em homologação não sobe após o deploy ou sobe com a versão anterior.
- Equipe de testes bloqueada aguardando a nova versão.

## Causa provável
Dependência quebrada, variável de ambiente ausente no ambiente de homologação, migração de banco incompatível
ou falta de espaço no servidor de homologação.

## Procedimento
1. Ler o log da etapa que falhou e identificar a primeira mensagem de erro.
2. Se a falha for de teste, devolver ao time de desenvolvimento com o log anexado.
3. Se a falha for de ambiente (variável, permissão, espaço), corrigir a configuração e reexecutar o pipeline.
4. Se a aplicação não subir, executar rollback para a última versão estável e registrar a versão problemática.
5. Confirmar com a equipe de testes que o ambiente voltou a estar disponível.

## Escalonamento
Falha em homologação não é incidente de produção: prioridade média, salvo quando bloqueia uma entrega com prazo
regulatório, caso em que deve ser tratada com prioridade alta.
