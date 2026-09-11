---
id: kb-008-certificado-tls-expirado
titulo: Certificado TLS expirado em site ou API
categoria: infraestrutura
tags: [certificado, tls, ssl, https, expirado, conexao nao segura, api, integracao, renovacao]
servicos: [portal-clientes, api-pagamentos]
---
## Sintomas
- Navegador exibe "sua conexão não é particular" ou "certificado expirado".
- Integrações via API falham com erro de handshake TLS.
- Problema começa exatamente na data de vencimento do certificado.

## Causa provável
Renovação automática do certificado falhou ou não estava configurada; certificado renovado, mas não
implantado no balanceador ou no gateway.

## Procedimento
1. Confirmar a data de expiração do certificado apresentado pelo servidor.
2. Emitir ou renovar o certificado pela autoridade certificadora utilizada.
3. Implantar o novo certificado no balanceador, gateway e servidores de aplicação envolvidos.
4. Validar o handshake em navegador e com cliente de linha de comando; validar a cadeia completa.
5. Registrar a nova data de expiração no inventário e configurar alerta com 30 dias de antecedência.

## Escalonamento
Certificado expirado em serviço público (Portal de Clientes, API de Pagamentos) é incidente crítico:
acionar a equipe de Infraestrutura e a equipe do serviço afetado imediatamente.
