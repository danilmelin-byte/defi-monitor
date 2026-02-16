import streamlit as st
from web3 import Web3
import requests
import time

# --- 1. КОНФИГУРАЦИЯ СТРАНИЦЫ ---
st.set_page_config(page_title="Architect DeFi Pro", layout="wide", page_icon="🦄")

# Стили для карточек и визуализации
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .metric-card { 
        background-color: #ffffff; 
        padding: 20px; 
        border-radius: 15px; 
        border: 1px solid #eee; 
        box-shadow: 0 4px 12px rgba(0,0,0,0.05); 
        margin-bottom: 20px; 
    }
    .range-bar-bg { 
        background-color: #f0f0f0; 
        height: 12px; 
        border-radius: 6px; 
        position: relative; 
        margin: 25px 0 10px 0; 
        border: 1px solid #e0e0e0;
    }
    .range-fill { 
        background-color: #4caf50; 
        height: 100%; 
        border-radius: 6px; 
        opacity: 0.15; 
        width: 100%;
    }
    .price-pointer { 
        position: absolute; 
        top: -6px; 
        width: 4px; 
        height: 24px; 
        background-color: #2196f3; 
        border-radius: 2px; 
        box-shadow: 0 0 8px rgba(33,150,243,0.6);
        z-index: 2;
    }
    .status-badge {
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.8em;
        font-weight: bold;
    }
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
    {"inputs":[{"name":"tokenId","type":"uint256"}],"name":"positions","outputs":[{"name":"nonce","type":"uint96"},{"name":"operator","type":"address"},{"name":"token0","type":"address"},{"name":"token1","type":"address"},{"name":"fee","type":"uint24"},{"name":"tickLower","type":"int24"},{"name":"tickUpper","type":"int24"},{"name":"liquidity","type":"uint128"},{"name":"feeGrowthInside0LastX128","type":"uint256"},{"name":"feeGrowthInside1LastX128","type":"uint256"},{"name":"tokensOwed0","type":"uint128"},{"name":"tokensOwed1","type":"uint128"}],"type":"function"},
    {"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],"type":"function"},
    {"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function"},
    {"inputs":[{"name":"t0","type":"address"},{"name":"t1","type":"address"},{"name":"fee","type":"uint24"}],"name":"getPool","outputs":[{"name":"","type":"address"}],"type":"function"},
    {"inputs":[],"name":"slot0","outputs":[{"name":"sqrtPriceX96","type":"uint160"},{"name":"tick","type":"int24"}],"type":"function"}
]

# --- 3. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
@st.cache_data(ttl=300)
def get_usd_prices():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=ethereum,usd-coin,tether,arbitrum,bitcoin&vs_currencies=usd"
        data = requests.get(url, timeout=5).json()
        mapping = {
            'WETH': data.get('ethereum', {}).get('usd', 2700),
            'USDC': data.get('usd-coin', {}).get('usd', 1),
            'USDC.e': data.get('usd-coin', {}).get('usd', 1),
            'USDT': data.get('tether', {}).get('usd', 1),
            'ARB': data.get('arbitrum', {}).get('usd', 1),
            'WBTC': data.get('bitcoin', {}).get('usd', 65000)
        }
        return mapping
    except:
        return {}

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
st.sidebar.title("🛠 Контрольная панель")
wallet_input = st.sidebar.text_input("Адрес кошелька Arbitrum", "0x995907fe97C9CAd3D310c4F384453E8676F4a170")
status_filter = st.sidebar.toggle("Только активные (LP > 0)", value=True)
scan_btn = st.sidebar.button("🚀 ЗАПУСТИТЬ МОНИТОРИНГ", use_container_width=True)

if scan_btn and wallet_input:
    try:
        addr = w3.to_checksum_address(wallet_input)
        manager = w3.eth.contract(address=NFT_MANAGER, abi=ABI)
        factory = w3.eth.contract(address=FACTORY_ADDR, abi=ABI)
        
        prices = get_usd_prices()
        
        with st.spinner("Синхронизация с узлом Arbitrum..."):
            count = manager.functions.balanceOf(addr).call()
            
            if count == 0:
                st.warning("На этом кошельке не найдено позиций Uniswap V3.")
            else:
                st.subheader(f"📊 Найдено позиций: {count}")
                
                for i in range(count):
                    tid = manager.functions.tokenOfOwnerByIndex(addr, i).call()
                    p = manager.functions.positions(tid).call()
                    
                    if status_filter and p[7] == 0: continue
                    
                    s0, d0 = get_token_info(p[2])
                    s1, d1 = get_token_info(p[3])
                    
                    # Данные пула и цены
                    pool_addr = factory.functions.getPool(p[2], p[3], p[4]).call()
                    pool_contract = w3.eth.contract(address=pool_addr, abi=ABI)
                    curr_tick = pool_contract.functions.slot0().call()[1]
                    
                    # Расчеты
                    amt0, amt1 = get_amounts(p[7], curr_tick, p[5], p[6], d0, d1)
                    unclaimed0 = p[10] / (10**d0)
                    unclaimed1 = p[11] / (10**d1)
                    
                    # Оценка в USD
                    val_usd = (amt0 * prices.get(s0, 0)) + (amt1 * prices.get(s1, 0))
                    fees_usd = (unclaimed0 * prices.get(s0, 0)) + (unclaimed1 * prices.get(s1, 0))
                    
                    in_range = p[5] <= curr_tick <= p[6]
                    
                    # Расчет шкалы
                    total_range = p[6] - p[5]
                    price_pos = (curr_tick - p[5]) / total_range * 100 if total_range != 0 else 50
                    price_pos = max(0, min(100, price_pos))

                    # ВЫВОД КАРТОЧКИ
                    st.markdown(f"""
                    <div class="metric-card">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <h3 style="margin:0;">NFT #{tid}: {s0} / {s1}</h3>
                            <span class="status-badge" style="background: {'#e8f5e9' if in_range else '#ffebee'}; color: {'#2e7d32' if in_range else '#c62828'};">
                                {'● В ДИАПАЗОНЕ' if in_range else '● ВНЕ ДИАПАЗОНА'}
                            </span>
                        </div>
                        
                        <div style="margin: 15px 0; display: flex; justify-content: space-between;">
                            <div>
                                <div style="font-size: 0.85em; color: #666;">Текущая стоимость:</div>
                                <div style="font-size: 1.3em; font-weight: bold; color: #1565c0;">${val_usd:.2f}</div>
                                <div style="font-size: 0.8em; color: #888;">{amt0:.4f} {s0} + {amt1:.4f} {s1}</div>
                            </div>
                            <div style="text-align: right;">
                                <div style="font-size: 0.85em; color: #666;">Накоплено комиссий:</div>
                                <div style="font-size: 1.3em; font-weight: bold; color: #2e7d32;">+ ${fees_usd:.4f}</div>
                                <div style="font-size: 0.8em; color: #888;">{unclaimed0:.5f} {s0} + {unclaimed1:.5f} {s1}</div>
                            </div>
                        </div>

                        <div class="range-bar-bg">
                            <div class="range-fill"></div>
                            <div class="price-pointer" style="left: {price_pos}%;"></div>
                        </div>
                        <div style="display: flex; justify-content: space-between; font-size: 0.7em; color: #999; font-family: monospace;">
                            <span>MIN TICK: {p[5]}</span>
                            <span style="color: #2196f3; font-weight: bold;">ТЕКУЩИЙ: {curr_tick}</span>
                            <span>MAX TICK: {p[6]}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            
    except Exception as e:
        st.error(f"Ошибка системы: {e}")

st.divider()
st.caption("Architect DeFi Monitor | Работает на данных Arbitrum | 2026")
