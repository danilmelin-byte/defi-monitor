import streamlit as st
from web3 import Web3

# --- 1. НАСТРОЙКИ ---
st.set_page_config(page_title="DeFi Architect Pro", layout="wide")

st.markdown("""
    <style>
    .metric-card { background-color: #ffffff; padding: 20px; border-radius: 15px; border: 1px solid #eee; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px; }
    .fee-text { color: #2e7d32; font-weight: bold; font-size: 1.1em; }
    .range-bar-bg { background-color: #eee; height: 10px; border-radius: 5px; position: relative; margin: 20px 0; }
    .range-fill { background-color: #4caf50; height: 100%; border-radius: 5px; opacity: 0.3; }
    .price-pointer { position: absolute; top: -5px; width: 4px; height: 20px; background-color: #2196f3; border-radius: 2px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. КОНСТАНТЫ ---
RPC_URL = "https://arb1.arbitrum.io/rpc"
NFT_MANAGER = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"
FACTORY_ADDR = "0x1F98431c8aD98523631AE4a59f267346ea31F984"
w3 = Web3(Web3.HTTPProvider(RPC_URL))

ABI = [
    {"inputs":[{"name":"owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"type":"function"},
    {"inputs":[{"name":"owner","type":"address"},{"name":"index","type":"uint256"}],"name":"tokenOfOwnerByIndex","outputs":[{"name":"","type":"uint256"}],"type":"function"},
    {"inputs":[{"name":"tokenId","type":"uint256"}],"name":"positions","outputs":[{"name":"nonce","type":"uint96"},{"name":"operator","type":"address"},{"name":"token0","type":"address"},{"name":"token1","type":"address"},{"name":"fee","type":"uint24"},{"name":"tickLower","type":"int24"},{"name":"tickUpper","type":"int24"},{"name":"liquidity","type":"uint128"},{"name":"feeGrowthInside0LastX128","type":"uint256"},{"name":"feeGrowthInside1LastX128","type":"uint256"},{"name":"tokensOwed0","type":"uint128"},{"name":"tokensOwed1","type":"uint128"}],"type":"function"},
    {"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],"type":"function"},
    {"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function"},
    {"inputs":[{"name":"","type":"address"},{"name":"","type":"address"},{"name":"","type":"uint24"}],"name":"getPool","outputs":[{"name":"","type":"address"}],"type":"function"},
    {"inputs":[],"name":"slot0","outputs":[{"name":"sqrtPriceX96","type":"uint160"},{"name":"tick","type":"int24"},{"name":"observationIndex","type":"uint16"},{"name":"observationCardinality","type":"uint16"},{"name":"observationCardinalityNext","type":"uint16"},{"name":"feeProtocol","type":"uint8"},{"name":"unlocked","type":"bool"}],"type":"function"}
]

# --- 3. ФУНКЦИИ ---
def get_amounts(liquidity, current_tick, tick_lower, tick_upper, dec0, dec1):
    if liquidity == 0: return 0.0, 0.0
    sqrt_p = 1.0001 ** (current_tick / 2)
    sqrt_p_a = 1.0001 ** (tick_lower / 2)
    sqrt_p_b = 1.0001 ** (tick_upper / 2)
    if current_tick < tick_lower:
        a0 = liquidity * (sqrt_p_b - sqrt_p_a) / (sqrt_p_a * sqrt_p_b)
        a1 = 0
    elif current_tick < tick_upper:
        a0 = liquidity * (sqrt_p_b - sqrt_p) / (sqrt_p * sqrt_p_b)
        a1 = liquidity * (sqrt_p - sqrt_p_a)
    else:
        a0 = 0
        a1 = liquidity * (sqrt_p_b - sqrt_p_a)
    return a0 / (10**dec0), a1 / (10**dec1)

@st.cache_data(ttl=3600)
def get_token_info(address):
    try:
        c = w3.eth.contract(address=w3.to_checksum_address(address), abi=ABI)
        return c.functions.symbol().call(), c.functions.decimals().call()
    except: return "???", 18

# --- 4. ИНТЕРФЕЙС ---
wallet_input = st.sidebar.text_input("Кошелек", "0x995907fe97C9CAd3D310c4F384453E8676F4a170")
scan_btn = st.sidebar.button("🔎 Анализ прибыли")

if scan_btn and wallet_input:
    try:
        addr = w3.to_checksum_address(wallet_input)
        manager = w3.eth.contract(address=NFT_MANAGER, abi=ABI)
        factory = w3.eth.contract(address=FACTORY_ADDR, abi=ABI)
        
        count = manager.functions.balanceOf(addr).call()
        st.subheader(f"Всего позиций: {count}")
        
        for i in range(count):
            tid = manager.functions.tokenOfOwnerByIndex(addr, i).call()
            p = manager.functions.positions(tid).call()
            
            if p[7] == 0: continue # Пропускаем пустые
            
            s0, d0 = get_token_info(p[2])
            s1, d1 = get_token_info(p[3])
            
            pool_addr = factory.functions.getPool(p[2], p[3], p[4]).call()
            pool_contract = w3.eth.contract(address=pool_addr, abi=ABI)
            curr_tick = pool_contract.functions.slot0().call()[1]
            
            # Балансы и комиссии
            amt0, amt1 = get_amounts(p[7], curr_tick, p[5], p[6], d0, d1)
            unclaimed0 = p[10] / (10**d0)
            unclaimed1 = p[11] / (10**d1)
            
            # Визуализация диапазона (процент нахождения цены внутри)
            total_range = p[6] - p[5]
            price_pos = (curr_tick - p[5]) / total_range * 100 if total_range != 0 else 50
            price_pos = max(0, min(100, price_pos)) # Ограничиваем 0-100%

            st.markdown(f"""
            <div class="metric-card">
                <h3>NFT #{tid}: {s0}/{s1}</h3>
                <div style="display: flex; justify-content: space-between;">
                    <span><b>Баланс пула:</b> {amt0:.4f} {s0} | {amt1:.4f} {s1}</span>
                    <span class="fee-text">🎁 Комиссии: {unclaimed0:.4f} {s0} + {unclaimed1:.4f} {s1}</span>
                </div>
                
                <div class="range-bar-bg">
                    <div class="range-fill" style="width: 100%;"></div>
                    <div class="price-pointer" style="left: {price_pos}%;"></div>
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 0.8em; color: #666;">
                    <span>Мин: {p[5]} (tick)</span>
                    <span>Текущая цена: {curr_tick}</span>
                    <span>Макс: {p[6]} (tick)</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
    except Exception as e:
        st.error(f"Ошибка: {e}")
