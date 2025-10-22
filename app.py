# app.py
import streamlit as st
import ipaddress
import pandas as pd
import json
from html import escape

st.set_page_config(page_title="Calculadora de IP", layout="centered")

# ---------- Funções utilitárias ----------
def parse_input(ip_input: str):
    """
    Tenta criar um ip_network a partir da entrada.
    Aceita '192.168.10.0/24' ou '192.168.10.5' (neste caso requer seleção de máscara).
    Retorna (network_obj, error_msg)
    """
    ip_input = ip_input.strip()
    if not ip_input:
        return None, "Entrada vazia"
    try:
        # strict=False permite host bits 1 (ex.: 192.168.10.5/24)
        net = ipaddress.ip_network(ip_input, strict=False)
        return net, None
    except Exception as e:
        return None, f"Entrada inválida: {e}"

def calc_basic(network: ipaddress.IPv4Network):
    p = network.prefixlen
    results = {}
    results['network_address'] = str(network.network_address)
    results['broadcast_address'] = str(network.broadcast_address)
    # hosts count (total addresses)
    total_addrs = network.num_addresses
    results['total_addresses'] = total_addrs
    # usable hosts calculation
    if p == 32:
        usable = 1
        first = last = str(network.network_address)
    elif p == 31:
        # RFC3021: /31 has 2 addresses, ambos "routable" em enlaces ponto-a-ponto
        usable = 2
        first = str(list(network.hosts())[0]) if network.num_addresses >= 2 else str(network.network_address)
        last = str(list(network.hosts())[-1]) if network.num_addresses >= 2 else str(network.network_address)
    else:
        usable = max(0, (2 ** (32 - p)) - 2)
        if usable == 0:
            first = last = "-"
        else:
            first = str(list(network.hosts())[0])
            last = str(list(network.hosts())[-1])
    results['usable_hosts'] = usable
    results['first_usable'] = first
    results['last_usable'] = last
    results['prefixlen'] = p
    results['netmask'] = str(network.netmask)
    results['with_prefix'] = f"{results['network_address']}/{p}"
    return results

def generate_subnets(network: ipaddress.IPv4Network, new_prefix: int, limit=2000):
    """
    Gera sub-redes de tamanho new_prefix dentro de network.
    Retorna lista de strings. Limite para evitar travar em redes enormes.
    """
    if new_prefix < network.prefixlen:
        # new_prefix é mais curto => supernet (não sub-redes)
        return None, f"Prefixo {new_prefix} é menor que prefixo da rede base {network.prefixlen}. Não é possível gerar sub-redes maiores (é um supernet)."
    if new_prefix == network.prefixlen:
        return [str(network)], None
    try:
        subnets = list(network.subnets(new_prefix=new_prefix))
        if len(subnets) > limit:
            return None, f"Resultado muito grande ({len(subnets)} sub-redes). Limite = {limit}. Escolha um prefixo maior."
        return [str(s) for s in subnets], None
    except Exception as e:
        return None, f"Erro ao gerar sub-redes: {e}"

def format_results_text(results: dict):
    lines = [
        f"Rede: {results['with_prefix']}",
        f"Máscara: {results['netmask']} (/ {results['prefixlen']})",
        f"Endereço de Broadcast: {results['broadcast_address']}",
        f"Primeiro endereço válido: {results['first_usable']}",
        f"Último endereço válido: {results['last_usable']}",
        f"Hosts possíveis (utilizáveis): {results['usable_hosts']}",
        f"Total de endereços na sub-rede: {results['total_addresses']}",
    ]
    return "\n".join(lines)

# ---------- UI ----------
st.title("🖧 Calculadora de IP — completa")

# Tema claro/escuro simples (aplica CSS minimal)
theme_dark = st.checkbox("Tema escuro", value=False)

# Inputs
col1, col2 = st.columns([2,1])
with col1:
    ip_input = st.text_input("Endereço IP / CIDR (ex.: 192.168.10.0/24) ou apenas IP (192.168.10.5)", value="")
with col2:
    # seletor de máscara / prefixo (0-32)
    selected_prefix = st.selectbox("Escolher máscara (prefixo)", options=list(range(0,33)), index=24)

# Ações
action_col1, action_col2 = st.columns(2)
with action_col1:
    calcular = st.button("Calcular")
with action_col2:
    limpar = st.button("Limpar")

if limpar:
    # Simples "reset": recarrega a página
    st.experimental_rerun()

# Área para mensagens de erro
msg_placeholder = st.empty()

# Quando calcular
if calcular:
    # Se usuário passou IP sem /prefix, adicionamos selected_prefix
    net_obj = None
    if "/" in ip_input:
        net_obj, err = parse_input(ip_input)
        if err:
            msg_placeholder.error(err)
    else:
        # tenta parsear como IP e aplicar selected_prefix
        if not ip_input.strip():
            msg_placeholder.error("Informe um IP ou IP/CIDR.")
            st.stop()
        try:
            # cria uma IPv4Interface e extrai a rede com o prefixo selecionado
            ip_interface = ipaddress.ip_interface(f"{ip_input}/{selected_prefix}")
            net_obj = ip_interface.network
        except Exception as e:
            msg_placeholder.error(f"Entrada inválida: {e}")
            st.stop()

    if net_obj is None:
        st.stop()

    # Cálculos básicos
    results = calc_basic(net_obj)
    st.subheader("Resultados")
    st.code(format_results_text(results), language=None)

    # Botão copiar (usando JS)
    results_text = format_results_text(results).replace("\n", "\\n")
    copy_button_html = f"""
    <button onclick="navigator.clipboard.writeText('{escape(format_results_text(results))}')" style="
        background-color: #4CAF50; border: none; color: white; padding: 8px 12px;
        text-align: center; text-decoration: none; display: inline-block; font-size: 14px; border-radius:6px;">
        Copiar resultados
    </button>
    """
    st.markdown(copy_button_html, unsafe_allow_html=True)

    # Export CSV (dados principais)
    df_summary = pd.DataFrame([{
        "network": results['with_prefix'],
        "netmask": results['netmask'],
        "broadcast": results['broadcast_address'],
        "first_usable": results['first_usable'],
        "last_usable": results['last_usable'],
        "usable_hosts": results['usable_hosts'],
        "total_addresses": results['total_addresses']
    }])
    csv = df_summary.to_csv(index=False).encode('utf-8')
    st.download_button("Baixar resumo (CSV)", data=csv, file_name="ip_summary.csv", mime="text/csv")

    # Mostrar sub-redes com base no selected_prefix (se for maior ou igual)
    st.subheader("Gerar sub-redes (dentro da rede acima)")
    chosen_prefix = st.number_input("Prefixo para gerar sub-redes (novo tamanho de sub-rede)", min_value=net_obj.prefixlen, max_value=32, value=max(net_obj.prefixlen, selected_prefix))
    generate = st.button("Gerar sub-redes")

    if generate:
        subnets_list, err = generate_subnets(net_obj, int(chosen_prefix), limit=2000)
        if err:
            st.error(err)
        else:
            st.write(f"Quantidade de sub-redes geradas: {len(subnets_list)}")
            df_sub = pd.DataFrame(subnets_list, columns=["subnet"])
            st.dataframe(df_sub)
            csv_sub = df_sub.to_csv(index=False).encode('utf-8')
            st.download_button("Baixar lista de sub-redes (CSV)", data=csv_sub, file_name="subnets.csv", mime="text/csv")

    # Mostrar lista de hosts (com aviso)
    st.subheader("Listar hosts (atenção: redes grandes podem ser enormes)")
    list_hosts = st.checkbox("Gerar lista de hosts (limitar a 5000 entradas)", value=False)
    if list_hosts:
        max_show = 5000
        hosts_iter = list(net_obj.hosts())
        if len(hosts_iter) > max_show:
            st.warning(f"A rede tem {len(hosts_iter)} hosts. Só serão exibidos os primeiros {max_show}.")
            hosts_iter = hosts_iter[:max_show]
        df_hosts = pd.DataFrame([str(h) for h in hosts_iter], columns=["host"])
        st.dataframe(df_hosts)
        csv_hosts = df_hosts.to_csv(index=False).encode('utf-8')
        st.download_button("Baixar hosts (CSV)", data=csv_hosts, file_name="hosts.csv", mime="text/csv")

# ---------- Aparência (tema) ----------
if theme_dark:
    dark_css = """
    <style>
    .stApp { background-color: #0e1117; color: #D8DEE9; }
    .stButton>button { background-color: #2a475e; color: white; }
    .stTextInput>div>div>input { background-color: #111217; color: #D8DEE9; }
    .stSelectbox>div>div>div { background-color: #111217; color:#D8DEE9; }
    </style>
    """
    st.markdown(dark_css, unsafe_allow_html=True)
else:
    light_css = """
    <style>
    .stApp { background-color: white; color: #111; }
    </style>
    """
    st.markdown(light_css, unsafe_allow_html=True)

# Footer / instruções rápidas
st.markdown("---")
st.markdown(
    "Instruções: informe `IP` ou `IP/CIDR`. Se informar apenas `IP`, selecione o prefixo desejado no menu. "
    "Use a geração de sub-redes para dividir a rede. Evite listar hosts para redes muito grandes."
)