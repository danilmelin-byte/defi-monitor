import streamlit as st
from web3 import Web3

# --- 1. НАСТРОЙКИ ---
st.set_page_config(page_title="DeFi Architect", layout="wide")
st.title("🦄 Uniswap V3 Monitor")

RPC_URL = "https://arb1.arbitrum.io/rpc"
NFT_MANAGER = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"
w3 = Web3(Web3.HTTPProvider(RPC_URL))

# ABI для получения ID токенов и данных позиций
ABI = [
    {"inputs":[{"name":"owner","type":"address"},{"name":"index","type":"uint256"}],"name":"tokenOfOwnerByIndex","outputs":[{"name":"","type":"uint256"}],"type":"function"},
    {"inputs":[{"name":"tokenId","type":"uint256"}],"name":"positions","outputs":[{"name":"nonce","type":"uint96"},{"name":"operator","type":"address"},{"name":"token0","type":"address"},{"name":"token1","type":"address"},{"name":"fee","type":"uint24"},{"name":"tickLower","type":"int24"},{"name":"tickUpper","type":"int24"},{"name":"liquidity","type":"uint128"},{"name":"feeGrowthInside0LastX128","type":"uint256"},{"name":"feeGrowthInside1LastX128","type":"uint256"},{"name":"tokensOwed0","type":"uint128"},{"name":"tokensOwed1","type":"uint128"}],"type":"function"},
    {"inputs":[{"name":"owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"type":"function"}
]

# --- 2. ИНТЕРФЕЙС ---
wallet = st.sidebar.text_input("Wallet", "0x995907fe97C9CAd3D310c4F384453E8676F4a170")
btn = st.button("🔎 Просканировать детали")

if btn:
    try:
        addr = w3.to_checksum_address(wallet)
        contract = w3.eth.contract(address=NFT_MANAGER, abi=ABI)
        
        count = contract.functions.balanceOf(addr).call()
        st.subheader(f"Найдено позиций: {count}")

        if count > 0:
            cols = st.columns(min(count, 3))
            
            for i in range(count):
                # Получаем ID каждого NFT
                token_id = contract.functions.tokenOfOwnerByIndex(addr, i).call()
                
                # Получаем данные позиции
                pos = contract.functions.positions(token_id).call()
                # pos[2] - token0, pos[3] - token1, pos[5] - tickLower, pos[6] - tickUpper, pos[7] - liquidity
                
                with cols[i % 3]:
                    with st.container():
                        st.markdown(f"### NFT #{token_id}")
                        st.caption(f"Fee: {pos[4]/10000}%")
                        
                        # Короткие адреса токенов для визуала
                        t0_short = f"{pos[2][:6]}...{pos[2][-4:]}"
                        t1_short = f"{pos[3][:6]}...{pos[3][-4:]}"
                        st.write(f"🔹 {t0_short}")
                        st.write(f"🔸 {t1_short}")
                        
                        if pos[7] > 0:
                            st.info(f"Ликвидность: {pos[7]}")
                        else:
                            st.warning("Пустая позиция")
                            
                        st.divider()
            
            st.success("Все данные успешно загружены!")
            
    except Exception as e:
        st.error(f"Ошибка при сборе данных: {e}")
