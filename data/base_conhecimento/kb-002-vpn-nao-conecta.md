---
id: kb-002-vpn-nao-conecta
titulo: VPN corporativa não conecta ou cai com frequência
categoria: infraestrutura
tags: [vpn, conexao, remoto, home office, cliente vpn, timeout, tunel, intermitente]
servicos: [vpn]
---
## Sintomas
- Cliente VPN fica em "conectando" e retorna erro de tempo esgotado.
- Conexão estabelece e cai depois de alguns minutos (intermitente).
- Funciona em uma rede (celular) e falha em outra (Wi-Fi doméstico).

## Causa provável
Bloqueio de portas UDP pelo roteador doméstico, cliente VPN desatualizado, certificado do usuário
expirado ou saturação do concentrador em horários de pico.

## Procedimento
1. Verificar no painel de status se o serviço de VPN está operacional para todos (se não, tratar como incidente).
2. Pedir ao usuário para testar em outra rede (4G); se funcionar, o problema é o roteador local: orientar reinício e uso do protocolo alternativo (TCP 443) no cliente.
3. Confirmar a versão do cliente VPN e atualizar se estiver abaixo da versão homologada.
4. Validar se a senha do AD não expirou (a VPN usa a mesma credencial).
5. Se o certificado do usuário estiver expirado, emitir novo pelo portal de certificados.

## Escalonamento
Vários usuários com queda simultânea indicam problema no concentrador: escalar para a equipe de Redes
com horário das quedas e regiões afetadas.
