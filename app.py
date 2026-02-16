import streamlit as st
from web3 import Web3

# --- 1. НАСТРОЙКИ ---
st.set_page_config(page_title="DeFi Architect", layout="wide")
st.title("🦄 Uniswap V3: Анализ кошелька")

# Тобольск или Москва — блокчейн везде один и тот же
RPC_URL = "https://arb1.arbitrum.io/rpc"
NFT_MANAGER = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"
w3 = Web3(Web3.HTTPProvider(RPC_URL))

# Маппинг популярных токенов для красоты
TOKEN_NAMES = {
    "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1": "WETH",
    "0xaf88d065e77c8cC2239327C5EDb3A432268e5831": "USDC",
    "0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8": "USDC.e",
    "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9": "USDT",
    "0x912CE59144191C1204E64559FE8253a0e49E6548": "ARB",
    "0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f": "WBTC"
}

ABI = [
    {"inputs":[{"name":"owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"type":"function"},
    {"inputs":[{"name":"owner","type":"address"},{"name":"index","type":"uint256"}],"name":"tokenOfOwnerByIndex","outputs":[{"name":"","type":"uint256"}],"type":"function"},
    {"inputs":[{"name":"tokenId","type":"uint256"}],"name":"positions","outputs":[{"name":"nonce","type":"uint96"},{"name":"operator","type":"address"},{"name":"token0","type":"address"},{"name":"token1","type":"address"},{"name":"fee","type":"uint24"},{"name":"tickLower","type":"int24"},{"name":"tickUpper","type":"int24"},{"name":"liquidity","type":"uint128"},{"name":"feeGrowthInside0LastX128","type":"uint256"},{"name":"feeGrowthInside1LastX128","type":"uint256"},{"name":"tokensOwed0","type":"uint128"},{"name":"tokensOwed1","type":"uint128"}],"type":"function"}
]

# --- 2. ИНТЕРФЕЙС ---
st.sidebar.header("Ввод данных")
# Оставляем поле пустым или с твоим адресом по умолчанию, но теперь оно РАБОТАЕТ
target_wallet = st.sidebar.text_input("Введите адрес кошелька", "")
scan_button = st.sidebar.button("🔎 Найти позиции")

if scan_button and target_wallet:
    try:
        # Проверка валидности адреса
        if not w3.is_address(target_wallet):
            st.error("Это не похоже на валидный Ethereum/Arbitrum адрес")
        else:
            addr = w3.to_checksum_address(target_wallet)
            contract = w3.eth.contract(address=NFT_MANAGER, abi=ABI)
            
            with st.spinner(f"Сканируем блокчейн для {addr[:10]}..."):
                count = contract.functions.balanceOf(addr).call()
                
                if count == 0:
                    st.warning("На этом кошельке не найдено NFT-позиций Uniswap V3.")
                else:
                    st.balloons() # Маленький праздник первого успеха
                    st.subheader(f"✅ Найдено позиций: {count}")
                    
                    cols = st.columns(3)
                    for i in range(count):
                        token_id = contract.functions.tokenOfOwnerByIndex(addr, i).call()
                        pos = contract.functions.positions(token_id).call()
                        
                        # Определяем названия токенов
                        name0 = TOKEN_NAMES.get(pos[2], f"Token0: {pos[2][:6]}...")
                        name1 = TOKEN_NAMES.get(pos[3], f"Token1: {pos[3][:6]}...")
                        
                        with cols[i % 3]:
                            st.info(f"**NFT #{token_id}**")
                            st.write(f"🪙 {name0} / {name1}")
                            st.write(f"📊 Fee: {pos[4]/10000}%")
                            
                            if pos[7] > 0:
                                st.success(f"Ликвидность: {pos[7]}")
                            else:
                                st.warning("Empty (No Liquidity)")
                            st.divider()
    except Exception as e:
        st.error(f"Произошла ошибка: {e}")
elif scan_button and not target_wallet:
    st.warning("Сначала введите адрес кошелька в боковом меню.")

st.markdown("---")
st.caption("Создано с помощью мобильного телефона и Gemini. Даниил, ты в деле!")
