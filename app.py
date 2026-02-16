import streamlit as st
from web3 import Web3
import requests

# --- 1. НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="Architect DeFi Monitor", layout="wide")

# CSS стили (встраиваем напрямую)
st.markdown("""
<style>
    .metric-card {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 15px;
        border: 1px solid #eee;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05);
        margin-bottom: 20px;
        color: #111;
    }
    .range-bar-bg {
        background-color: #eee;
        height: 12px;
        border-radius: 6px;
        position: relative;
        margin: 20px 0;
    }
    .range-fill {
        background-color: #4caf50;
        height: 100%;
        border-radius: 6px;
        opacity: 0.2;
        width: 100%;
    }
    .price-pointer {
        position: absolute;
        top: -6px;
        width: 4px;
        height: 24px;
        background-color: #2196f3;
        border-radius: 2px;
        box-shadow: 0 0 5px rgba(33,150,243,0.5);
    }
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
    {"inputs":[{"name":"t0","type":"address"},{"name":"t1","type":"address"},{"name":"fee","type":"uint24"}],"name":"getPool","outputs":[{"name":"","type":"address"}],"type":"function"},
    {"inputs":[],"name":"slot0","outputs":[{"name":"sqrtPriceX96","type":"uint160"},{"name":"tick","type":"int24"}],"type":"function"}
]

# --- 3. ЛОГИКА ---
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

@st.cache_data(ttl=300)
def get_prices():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=ethereum,usd-coin&vs_currencies=usd", timeout=5).json()
        return r['ethereum']['usd'], r['usd-coin']['usd']
    except: return 2700.0, 1.0

# --- 4. ИНТЕРФЕЙС ---
st.sidebar.header("Настройки")
wallet = st.sidebar.text_input("Кошелек", "0x995907fe97C9CAd3D310c4F384453E8676F4a170")
btn = st.sidebar.button("🔎 Начать сканирование")

if btn and wallet:
    try:
        addr = w3.to_checksum_address(wallet)
        manager = w3.eth.contract(address=NFT_MANAGER, abi=ABI)
        factory = w3.eth.contract(address=FACTORY_ADDR, abi=ABI)
        eth_p, usdc_p = get_prices()
        
        count = manager.functions.balanceOf(addr).call()
        st.subheader(f"Найдено позиций: {count}")
        
        for i in range(count):
            tid = manager.functions.tokenOfOwnerByIndex(addr, i).call()
            p = manager.functions.positions(tid).call()
            if p[7] == 0: continue
            
            # Токены
            c0 = w3.eth.contract(address=p[2], abi=ABI)
            c1 = w3.eth.contract(address=p[3], abi=ABI)
            s0, d0 = c0.functions.symbol().call(), c0.functions.decimals().call()
            s1, d1 = c1.functions.symbol().call(), c1.functions.decimals().call()
            
            # Пул
            pool_addr = factory.functions.getPool(p[2], p[3], p[4]).call()
            curr_tick = w3.eth.contract(address=pool_addr, abi=ABI).functions.slot0().call()[1]
            
            # Расчеты
            amt0, amt1 = get_amounts(p[7], curr_tick, p[5], p[6], d0, d1)
            f0, f1 = p[10]/(10**d0), p[11]/(10**d1)
            total_usd = (amt0 * eth_p) + (amt1 * usdc_p)
            fees_usd = (f0 * eth_p) + (f1 * usdc_p)
            
            # Позиция бегунка
            price_pos = max(0, min(100, (curr_tick - p[5]) / (p[6] - p[5]) * 100))
            in_range = p[5] <= curr_tick <= p[6]

            # ВЫВОД КАРТОЧКИ (Markdown + HTML)
            st.markdown(f"""
            <div class="metric-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h3 style="margin:0;">NFT #{tid}: {s0}/{s1}</h3>
                    <span style="background:{'#e8f5e9' if in_range else '#ffebee'}; color:{'#2e7d32' if in_range else '#c62828'}; padding:5px 10px; border-radius:10px; font-weight:bold;">
                        {'● В ДИАПАЗОНЕ' if in_range else '● ВНЕ ДИАПАЗОНА'}
                    </span>
                </div>
                <div style="margin:15px 0; display:flex; justify-content:space-between;">
                    <div>
                        <div style="color:#666; font-size:0.8em;">Стоимость:</div>
                        <div style="font-size:1.3em; font-weight:bold;">${total_usd:.2f}</div>
                        <div style="font-size:0.8em; color:#888;">{amt0:.4f} {s0} + {amt1:.2f} {s1}</div>
                    </div>
                    <div style="text-align:right;">
                        <div style="color:#666; font-size:0.8em;">Комиссии:</div>
                        <div style="font-size:1.3em; font-weight:bold; color:#2e7d32;">+ ${fees_usd:.4f}</div>
                        <div style="font-size:0.8em; color:#888;">{f0:.5f} {s0} + {f1:.2f} {s1}</div>
                    </div>
                </div>
                <div class="range-bar-bg">
                    <div class="range-fill"></div>
                    <div class="price-pointer" style="left: {price_pos}%;"></div>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:0.7em; color:#999; font-family:monospace;">
                    <span>MIN: {p[5]}</span>
                    <span style="color:#2196f3; font-weight:bold;">ТЕКУЩИЙ: {curr_tick}</span>
                    <span>MAX: {p[6]}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
    except Exception as e:
        st.error(f"Ошибка: {e}")
