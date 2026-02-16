import streamlit as st
from web3 import Web3
import requests

# --- 1. КОНФИГ И СТИЛИ ---
st.set_page_config(page_title="DeFi Architect Pro", layout="wide")

st.markdown("""
    <style>
    .metric-card { background-color: #ffffff; padding: 20px; border-radius: 15px; border: 1px solid #eee; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px; }
    .status-badge { padding: 4px 8px; border-radius: 5px; font-size: 12px; font-weight: bold; }
    .in-range { background-color: #e8f5e9; color: #2e7d32; }
    .out-range { background-color: #ffebee; color: #c62828; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. КОНСТАНТЫ И ПОДКЛЮЧЕНИЕ ---
RPC_URL = "https://arb1.arbitrum.io/rpc"
NFT_MANAGER = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"
FACTORY_ADDR = "0x1F98431c8aD98523631AE4a59f267346ea31F984"
w3 = Web3(Web3.HTTPProvider(RPC_URL))

ABI = [
    {"inputs":[{"name":"owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"type":"function"},
    {"inputs":[{"name":"owner","type":"address"},{"name":"index","type":"uint256"}],"name":"tokenOfOwnerByIndex","outputs":[{"name":"","type":"uint256"}],"type":"function"},
    {"inputs":[{"name":"tokenId","type":"uint256"}],"name":"positions","outputs":[{"name":"nonce","type":"uint96"},{"name":"operator","type":"address"},{"name":"token0","type":"address"},{"name":"token1","type":"address"},{"name":"fee","type":"uint24"},{"name":"tickLower","type":"int24"},{"name":"tickUpper","type":"int24"},{"name":"uint128","name":"liquidity","type":"uint128"},{"name":"feeGrowthInside0LastX128","type":"uint256"},{"name":"feeGrowthInside1LastX128","type":"uint256"},{"name":"tokensOwed0","type":"uint128"},{"name":"tokensOwed1","type":"uint128"}],"type":"function"},
    {"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],"type":"function"},
    {"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function"},
    {"inputs":[{"name":"","type":"address"},{"name":"","type":"address"},{"name":"","type":"uint24"}],"name":"getPool","outputs":[{"name":"","type":"address"}],"type":"function"},
    {"inputs":[],"name":"slot0","outputs":[{"name":"sqrtPriceX96","type":"uint160"},{"name":"tick","type":"int24"},{"name":"observationIndex","type":"uint16"},{"name":"observationCardinality","type":"uint16"},{"name":"observationCardinalityNext","type":"uint16"},{"name":"feeProtocol","type":"uint8"},{"name":"unlocked","type":"bool"}],"type":"function"}
]

# --- 3. МАТЕМАТИКА И ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def get_amounts(liquidity, current_tick, tick_lower, tick_upper, dec0, dec1):
    """Рассчитывает количество токенов в позиции на основе ликвидности и тиков"""
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
    except:
        return "???", 18

# --- 4. ИНТЕРФЕЙС ---
st.sidebar.header("🚀 DeFi Architect")
target_wallet = st.sidebar.text_input("Кошелек", "0x995907fe97C9CAd3D310c4F384453E8676F4a170")
status_filter = st.sidebar.toggle("Только активные", value=True)
scan_btn = st.sidebar.button("🔎 Анализ")

if scan_btn and target_wallet:
    try:
        addr = w3.to_checksum_address(target_wallet)
        manager = w3.eth.contract(address=NFT_MANAGER, abi=ABI)
        factory = w3.eth.contract(address=FACTORY_ADDR, abi=ABI)
        
        count = manager.functions.balanceOf(addr).call()
        
        if count == 0:
            st.warning("Позиций не найдено.")
        else:
            st.subheader(f"Найдено позиций: {count}")
            cols = st.columns(2)
            
            for i in range(count):
                tid = manager.functions.tokenOfOwnerByIndex(addr, i).call()
                p = manager.functions.positions(tid).call()
                # p[7] - ликвидность
                
                if status_filter and p[7] == 0: continue
                
                # Получаем инфо о токенах
                s0, d0 = get_token_info(p[2])
                s1, d1 = get_token_info(p[3])
                
                # Получаем текущую цену (тик) пула
                pool_addr = factory.functions.getPool(p[2], p[3], p[4]).call()
                pool_contract = w3.eth.contract(address=pool_addr, abi=ABI)
                current_tick = pool_contract.functions.slot0().call()[1]
                
                # Считаем балансы
                amt0, amt1 = get_amounts(p[7], current_tick, p[5], p[6], d0, d1)
                
                in_range = p[5] <= current_tick <= p[6]
                
                with cols[i % 2]:
                    st.markdown(f"""
                    <div class="metric-card">
                        <div style="display: flex; justify-content: space-between;">
                            <b>NFT #{tid}</b>
                            <span class="status-badge {'in-range' if in_range else 'out-range'}">
                                {'В ДИАПАЗОНЕ' if in_range else 'ВНЕ ДИАПАЗОНА'}
                            </span>
                        </div>
                        <h3 style="margin: 10px 0;">{s0} / {s1}</h3>
                        <p style="color: #666; font-size: 0.9em;">Комиссия: {p[4]/10000}%</p>
                        <hr>
                        <div style="display: flex; justify-content: space-between;">
                            <span>Баланс {s0}:</span> <b>{amt0:.4f}</b>
                        </div>
                        <div style="display: flex; justify-content: space-between;">
                            <span>Баланс {s1}:</span> <b>{amt1:.4f}</b>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
    except Exception as e:
        st.error(f"Ошибка: {e}")
