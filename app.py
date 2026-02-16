import streamlit as st
from web3 import Web3

# 1. Настройки
st.set_page_config(page_title="DeFi Monitor", page_icon="🦄")
st.title("🦄 My DeFi Dashboard")

RPC_URL = "https://arb1.arbitrum.io/rpc"
NFT_MANAGER = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"
w3 = Web3(Web3.HTTPProvider(RPC_URL))

# ABI только для одной функции, чтобы не грузить память
ABI_BALANCE = [{"inputs":[{"name":"owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"type":"function"}]

# 2. Ввод данных
wallet = st.sidebar.text_input("Wallet Address", "0x995907fe97C9CAd3D310c4F384453E8676F4a170")

if st.button("Просканировать позиции Uniswap V3"):
    try:
        addr = w3.to_checksum_address(wallet)
        contract = w3.eth.contract(address=NFT_MANAGER, abi=ABI_BALANCE)
        
        # Получаем количество NFT позиций
        count = contract.functions.balanceOf(addr).call()
        
        st.metric("Всего активных позиций (NFT)", count)
        
        if count > 0:
            st.success(f"Найдено {count} позиций! Начинаю сбор детальных данных...")
            # Тут мы в следующем шаге добавим вывод каждой карточки
        else:
            st.info("Активных LP-позиций не обнаружено.")
            
    except Exception as e:
        st.error(f"Ошибка: {e}")
