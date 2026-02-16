import streamlit as st
from web3 import Web3

# 1. Простейший заголовок
st.title("DeFi Architect Monitor")

# 2. Подключение к сети
RPC_URL = "https://arb1.arbitrum.io/rpc"
w3 = Web3(Web3.HTTPProvider(RPC_URL))

# 3. Сайдбар
wallet = st.sidebar.text_input("Wallet", "0x995907fe97C9CAd3D310c4F384453E8676F4a170")

# 4. Проверка соединения
if st.button("Проверить баланс ETH"):
    try:
        if w3.is_connected():
            balance = w3.eth.get_balance(wallet)
            eth_val = w3.from_wei(balance, 'ether')
            st.success(f"Соединение установлено!")
            st.metric("Баланс ETH на Arbitrum", f"{eth_val:.4f} ETH")
        else:
            st.error("Ошибка подключения к узлу")
    except Exception as e:
        st.error(f"Ошибка: {e}")

st.info("Если этот блок работает, значит мы на верном пути. Напиши мне, что появилось на экране.")
