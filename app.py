import streamlit as st
from web3 import Web3
import requests

# --- 1. НАСТРОЙКИ ---
st.set_page_config(page_title="Architect DeFi Pro", layout="wide")

st.markdown("""
<style>
    .metric-card {
        background-color: #ffffff; padding: 20px; border-radius: 15px;
        border: 1px solid #eee; box-shadow: 0 4px 10px rgba(0,0,0,0.05);
        margin-bottom: 20px; color: #111;
    }
    .range-bar-bg {
        background-color: #eee; height: 12px; border-radius: 6px;
        position: relative; margin: 20px 0;
    }
    .range-fill {
        background-color: #4caf50; height: 100%; border-radius: 6px;
        opacity: 0.2; width: 100%;
    }
    .price-pointer {
        position: absolute; top: -6px; width: 4px; height: 24px;
        background-color: #2196f3; border-radius: 2px;
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

# --- 3. МАТЕМАТИКА ---
def tick_to_price(tick, d0, d1):
    # Формула Uniswap V3: Цена = 1.0001^tick
    return (1.0001 ** tick) * (10 ** (d0 - d1))

def get_amounts(liquidity, cur_tick, tick_low, tick_high, d0, d1):
    if liquidity == 0: return 0, 0
    sqrtP = 1.0001 ** (cur_tick / 2)
    sqrtA = 1.0001 ** (tick_low / 2)
    sqrtB = 1.0001 ** (tick_high / 2)
    if cur_tick < tick_low:
        a0 = liquidity * (sqrtB - sqrtA) / (sqrtA * sqrtB)
        a1 = 0
    elif cur_tick < tick_high:
        a0 = liquidity * (sqrtB - sqrtP) / (sqrtP * sqrtB)
        a1 = liquidity * (sqrtP - sqrtA)
    else:
        a0 = 0
        a1 = liquidity * (sqrtB - sqrtA)
    return a0 / (10**d0), a1 / (10**d1)

# --- 4. ИНТЕРФЕЙС ---
st.sidebar.header("Параметры")
wallet = st.sidebar.text_input("Кошелек", "0x995907fe97C9CAd3D310c4F384453E8676F4a170")
btn = st.sidebar.button("🔎 Обновить данные")

if btn and wallet:
    try:
        addr = w3.to_checksum_address(wallet)
        nft_contract = w3.eth.contract(address=NFT_MANAGER, abi=ABI)
        factory = w3.eth.contract(address=FACTORY_ADDR, abi=ABI)
        
        # Безопасный запрос цены ETH
        try:
            r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd", timeout=5).json()
            p_eth = r['ethereum']['usd']
        except:
            p_eth = 2750.0 # Фолбэк, если API лежит
        
        count = nft_contract.functions.balanceOf(addr).call()
        st.subheader(f"Найдено позиций: {count}")

        for i in range(count):
            tid = nft_contract.functions.tokenOfOwnerByIndex(addr, i).call()
            pos = nft_contract.functions.positions(tid).call()
            if pos[7] == 0: continue
            
            s0, d0 = w3.eth.contract(address=pos[2], abi=ABI).functions.symbol().call(), w3.eth.contract(address=pos[2], abi=ABI).functions.decimals().call()
            s1, d1 = w3.eth.contract(address=pos[3], abi=ABI).functions.symbol().call(), w3.eth.contract(address=pos[3], abi=ABI).functions.decimals().call()
            
            pool_addr = factory.functions.getPool(pos[2], pos[3], pos[4]).call()
            cur_tick = w3.eth.contract(address=pool_addr, abi=ABI).functions.slot0().call()[1]
            
            # --- ЛОГИКА ИНВЕРСИИ ДЛЯ ПАР С USDC ---
            # В паре WETH/USDC (токен0/токен1), цена обычно USDC за WETH.
            # Если USDC - это token0, формулу нужно перевернуть.
            is_inverted = (s0 == "USDC" or s0 == "USDT")
            
            p_min_raw = tick_to_price(pos[5], d0, d1)
            p_max_raw = tick_to_price(pos[6], d0, d1)
            p_now_raw = tick_to_price(cur_tick, d0, d1)

            if is_inverted:
                p_min, p_max, p_now = 1/p_max_raw, 1/p_min_raw, 1/p_now_raw
            else:
                p_min, p_max, p_now = p_min_raw, p_max_raw, p_now_raw
            
            # Балансы
            a0, a1 = get_amounts(pos[7], cur_tick, pos[5], pos[6], d0, d1)
            
            # Комиссии (Tokens Owed)
            f0, f1 = pos[10] / (10**d0), pos[11] / (10**d1)
            
            # Оценка стоимости (упрощенно для WETH/USDC)
            if s1 in ["USDC", "USDT"]:
                total_usd = (a0 * p_eth) + a1
                fees_usd = (f0 * p_eth) + f1
            else:
                total_usd = (a0 * p_eth) + (a1 * p_eth) # На случай пар ETH/ETH
                fees_usd = (f0 * p_eth) + (f1 * p_eth)
            
            # Визуализация шкалы
            p_range = pos[6] - pos[5]
            p_pos = ((cur_tick - pos[5]) / p_range * 100) if p_range != 0 else 50
            p_pos = max(0, min(100, p_pos))
            in_range = pos[5] <= cur_tick <= pos[6]

            st.markdown(f"""
            <div class="metric-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h3 style="margin:0;">NFT #{tid}: {s0}/{s1}</h3>
                    <span style="color:{'#2e7d32' if in_range else '#c62828'}; font-weight:bold; font-size:0.9em;">
                        {'● В ДИАПАЗОНЕ' if in_range else '● ВНЕ ДИАПАЗОНА'}
                    </span>
                </div>
                <div style="margin:20px 0; display:flex; justify-content:space-between;">
                    <div>
                        <div style="color:#666; font-size:0.8em;">Ваш депозит:</div>
                        <div style="font-size:1.4em; font-weight:bold;">${total_usd:.2f}</div>
                        <div style="font-size:0.85em; color:#444;">{a0:.4f} {s0} + {a1:.2f} {s1}</div>
                    </div>
                    <div style="text-align:right;">
                        <div style="color:#2e7d32; font-size:0.8em; font-weight:bold;">Комиссии (Uncollected):</div>
                        <div style="font-size:1.4em; font-weight:bold; color:#2e7d32;">+ ${fees_usd:.4f}</div>
                        <div style="font-size:0.85em; color:#444;">{f0:.5f} {s0} + {f1:.4f} {s1}</div>
                    </div>
                </div>
                <div class="range-bar-bg">
                    <div class="range-fill"></div>
                    <div class="price-pointer" style="left: {p_pos}%;"></div>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:0.9em; font-weight:500;">
                    <span>Мин: <span style="color:#111;">{p_min:.1f}</span></span>
                    <span style="color:#2196f3;">Цена сейчас: {p_now:.1f}</span>
                    <span>Макс: <span style="color:#111;">{p_max:.1f}</span></span>
                </div>
            </div>
            """, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Произошла ошибка: {e}")
