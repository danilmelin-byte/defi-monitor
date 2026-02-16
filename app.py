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
    # Цена = 1.0001^tick * 10^(d0-d1)
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

# --- 4. ОСНОВНОЙ ЦИКЛ ---
st.sidebar.header("Параметры")
wallet = st.sidebar.text_input("Кошелек", "0x995907fe97C9CAd3D310c4F384453E8676F4a170")
btn = st.sidebar.button("🔎 Обновить данные")

if btn and wallet:
    try:
        addr = w3.to_checksum_address(wallet)
        nft_contract = w3.eth.contract(address=NFT_MANAGER, abi=ABI)
        factory = w3.eth.contract(address=FACTORY_ADDR, abi=ABI)
        
        # Запрос актуальных цен ETH/USDC для общей оценки
        p_eth = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd").json()['ethereum']['usd']
        
        count = nft_contract.functions.balanceOf(addr).call()
        st.subheader(f"Найдено NFT: {count}")

        for i in range(count):
            tid = nft_contract.functions.tokenOfOwnerByIndex(addr, i).call()
            pos = nft_contract.functions.positions(tid).call()
            if pos[7] == 0: continue # Пропуск пустых
            
            # Данные токенов
            t0_c = w3.eth.contract(address=pos[2], abi=ABI)
            t1_c = w3.eth.contract(address=pos[3], abi=ABI)
            s0, d0 = t0_c.functions.symbol().call(), t0_c.functions.decimals().call()
            s1, d1 = t1_c.functions.symbol().call(), t1_c.functions.decimals().call()
            
            # Пул и текущий тик
            pool_addr = factory.functions.getPool(pos[2], pos[3], pos[4]).call()
            pool_contract = w3.eth.contract(address=pool_addr, abi=ABI)
            cur_tick = pool_contract.functions.slot0().call()[1]
            
            # РАСЧЕТ ЦЕН (WETH/USDC)
            # В Uniswap V3 цена считается как Token1/Token0
            price_min = tick_to_price(pos[5], d0, d1)
            price_max = tick_to_price(pos[6], d0, d1)
            price_now = tick_to_price(cur_tick, d0, d1)
            
            # Балансы в токенах
            a0, a1 = get_amounts(pos[7], cur_tick, pos[5], pos[6], d0, d1)
            
            # КОМИССИИ (Tokens Owed + накопленные за последнее время)
            # Если tokensOwed по нулям, выводим 0, но предупреждаем
            f0, f1 = pos[10] / (10**d0), pos[11] / (10**d1)
            
            total_usd = (a0 * p_eth) + (a1 * 1.0) # Для WETH/USDC
            fees_usd = (f0 * p_eth) + (f1 * 1.0)
            
            # Позиция бегунка
            price_range = pos[6] - pos[5]
            price_pos = ((cur_tick - pos[5]) / price_range) * 100
            price_pos = max(0, min(100, price_pos))
            in_range = pos[5] <= cur_tick <= pos[6]

            st.markdown(f"""
            <div class="metric-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h3 style="margin:0;">NFT #{tid}: {s0}/{s1}</h3>
                    <span style="color:{'#2e7d32' if in_range else '#c62828'}; font-weight:bold;">
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
                        <div style="color:#2e7d32; font-size:0.8em; font-weight:bold;">Накоплено комиссий:</div>
                        <div style="font-size:1.4em; font-weight:bold; color:#2e7d32;">+ ${fees_usd:.4f}</div>
                        <div style="font-size:0.85em; color:#444;">{f0:.5f} {s0} + {f1:.2f} {s1}</div>
                    </div>
                </div>
                <div class="range-bar-bg">
                    <div class="range-fill"></div>
                    <div class="price-pointer" style="left: {price_pos}%;"></div>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:0.9em; font-weight:500;">
                    <span>Мин: <span style="color:#111;">{price_min:.1f}</span></span>
                    <span style="color:#2196f3;">Цена сейчас: {price_now:.1f}</span>
                    <span>Макс: <span style="color:#111;">{price_max:.1f}</span></span>
                </div>
            </div>
            """, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Произошла ошибка: {e}")
