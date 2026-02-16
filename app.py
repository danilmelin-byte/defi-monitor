import streamlit as st
from web3 import Web3
import requests

# --- 1. НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="Architect DeFi Pro", layout="wide")

st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
        padding: 25px; border-radius: 20px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.2);
        margin-bottom: 25px; color: #fff;
    }
    .stat-box {
        background: rgba(255,255,255,0.15);
        backdrop-filter: blur(5px);
        padding: 15px; border-radius: 12px;
        border: 1px solid rgba(255,255,255,0.2);
    }
    .range-bar-bg {
        background: rgba(255,255,255,0.3);
        height: 12px; border-radius: 6px;
        position: relative; margin: 20px 0;
    }
    .range-fill { background: #4ade80; height: 100%; border-radius: 6px; opacity: 0.5; }
    .price-pointer {
        position: absolute; top: -6px; width: 6px; height: 24px;
        background: #fbbf24; border-radius: 3px;
        box-shadow: 0 0 10px #fbbf24;
    }
    .status-badge {
        padding: 5px 12px; border-radius: 15px; font-size: 0.8em; font-weight: bold;
        background: rgba(255,255,255,0.2); border: 1px solid #fff;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. КОНСТАНТЫ ---
RPC_URL = "https://arb1.arbitrum.io/rpc"
NFT_MANAGER = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"
FACTORY_ADDR = "0x1F98431c8aD98523631AE4a59f267346ea31F984"
w3 = Web3(Web3.HTTPProvider(RPC_URL))

# Добавили функцию collect в ABI
ABI_NFT = [
    {"inputs":[{"name":"owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"type":"function"},
    {"inputs":[{"name":"owner","type":"address"},{"name":"index","type":"uint256"}],"name":"tokenOfOwnerByIndex","outputs":[{"name":"","type":"uint256"}],"type":"function"},
    {"inputs":[{"name":"tokenId","type":"uint256"}],"name":"positions","outputs":[{"name":"nonce","type":"uint96"},{"name":"operator","type":"address"},{"name":"token0","type":"address"},{"name":"token1","type":"address"},{"name":"fee","type":"uint24"},{"name":"tickLower","type":"int24"},{"name":"tickUpper","type":"int24"},{"name":"liquidity","type":"uint128"},{"name":"feeGrowthInside0LastX128","type":"uint256"},{"name":"feeGrowthInside1LastX128","type":"uint256"},{"name":"tokensOwed0","type":"uint128"},{"name":"tokensOwed1","type":"uint128"}],"type":"function"},
    {"inputs":[{"components":[{"name":"tokenId","type":"uint256"},{"name":"recipient","type":"address"},{"name":"amount0Max","type":"uint128"},{"name":"amount1Max","type":"uint128"}],"name":"params","type":"tuple"}],"name":"collect","outputs":[{"name":"amount0","type":"uint256"},{"name":"amount1","type":"uint256"}],"type":"function"}
]
ABI_ERC20 = [
    {"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],"type":"function"},
    {"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function"}
]
ABI_POOL = [{"inputs":[],"name":"slot0","outputs":[{"name":"sqrtPriceX96","type":"uint160"},{"name":"tick","type":"int24"}],"type":"function"}]
ABI_FACTORY = [{"inputs":[{"name":"t0","type":"address"},{"name":"t1","type":"address"},{"name":"fee","type":"uint24"}],"name":"getPool","outputs":[{"name":"","type":"address"}],"type":"function"}]

# --- 3. ФУНКЦИИ ---
def tick_to_price(tick, d0, d1):
    return (1.0001 ** tick) * (10 ** (d0 - d1))

def get_amounts(liquidity, cur_tick, tick_low, tick_high, d0, d1):
    if liquidity == 0: return 0, 0
    sqrtP, sqrtA, sqrtB = 1.0001**(cur_tick/2), 1.0001**(tick_low/2), 1.0001**(tick_high/2)
    if cur_tick < tick_low:
        a0 = liquidity * (sqrtB - sqrtA) / (sqrtA * sqrtB)
        a1 = 0
    elif cur_tick < tick_high:
        a0 = liquidity * (sqrtB - sqrtP) / (sqrtP * sqrtB)
        a1 = liquidity * (sqrtP - sqrtA)
    else:
        a0, a1 = 0, liquidity * (sqrtB - sqrtA)
    return a0 / (10**d0), a1 / (10**d1)

# --- 4. ИНТЕРФЕЙС ---
st.title("Architect DeFi Pro")
wallet = st.sidebar.text_input("Кошелек", "")
btn = st.sidebar.button("ОБНОВИТЬ ДАННЫЕ", type="primary")

if btn and wallet:
    try:
        # Получаем актуальную цену ETH для оценки
        try:
            r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd", timeout=5).json()
            p_eth = r['ethereum']['usd']
        except: p_eth = 2750.0

        target = w3.to_checksum_address(wallet)
        nft_contract = w3.eth.contract(address=NFT_MANAGER, abi=ABI_NFT)
        factory = w3.eth.contract(address=FACTORY_ADDR, abi=ABI_FACTORY)

        count = nft_contract.functions.balanceOf(target).call()
        
        for i in range(count):
            tid = nft_contract.functions.tokenOfOwnerByIndex(target, i).call()
            pos = nft_contract.functions.positions(tid).call()
            if pos[7] == 0: continue

            # Токены
            t0_c, t1_c = w3.eth.contract(address=pos[2], abi=ABI_ERC20), w3.eth.contract(address=pos[3], abi=ABI_ERC20)
            s0, d0 = t0_c.functions.symbol().call(), t0_c.functions.decimals().call()
            s1, d1 = t1_c.functions.symbol().call(), t1_c.functions.decimals().call()

            # Текущая цена в пуле
            pool_addr = factory.functions.getPool(pos[2], pos[3], pos[4]).call()
            pool_c = w3.eth.contract(address=pool_addr, abi=ABI_POOL)
            cur_tick = pool_c.functions.slot0().call()[1]

            # --- СИМУЛЯЦИЯ COLLECT (ГЛАВНЫЙ ФИКС) ---
            MAX_UINT128 = 2**128 - 1
            collect_params = {
                "tokenId": tid,
                "recipient": target,
                "amount0Max": MAX_UINT128,
                "amount1Max": MAX_UINT128
            }
            live_fees = nft_contract.functions.collect(collect_params).call({'from': target})
            f0 = live_fees[0] / (10**d0)
            f1 = live_fees[1] / (10**d1)

            # Расчет цен с инверсией (WETH/USDC)
            is_inv = (s0 in ["USDC", "USDT", "DAI"])
            p_min_r, p_max_r, p_now_r = tick_to_price(pos[5], d0, d1), tick_to_price(pos[6], d0, d1), tick_to_price(cur_tick, d0, d1)
            
            if is_inv: p_min, p_max, p_now = 1/p_max_r, 1/p_min_r, 1/p_now_r
            else: p_min, p_max, p_now = p_min_r, p_max_r, p_now_r

            # Депозит и стоимость
            a0, a1 = get_amounts(pos[7], cur_tick, pos[5], pos[6], d0, d1)
            val_usd = (a0 * p_eth + a1) if not is_inv else (a0 + a1 * p_eth)
            fee_usd = (f0 * p_eth + f1) if not is_inv else (f0 + f1 * p_eth)
            
            in_range = pos[5] <= cur_tick <= pos[6]
            p_pos = max(0, min(100, (cur_tick - pos[5]) / (pos[6] - pos[5]) * 100))

            st.markdown(f"""
            <div class="metric-card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                    <h3 style="margin:0;">NFT #{tid}: {s0}/{s1}</h3>
                    <span class="status-badge">{'● В ДИАПАЗОНЕ' if in_range else '○ ВНЕ ДИАПАЗОНА'}</span>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                    <div class="stat-box">
                        <div style="font-size: 0.8em; opacity: 0.8;">Ликвидность</div>
                        <div style="font-size: 1.5em; font-weight: bold;">${val_usd:,.2f}</div>
                        <div style="font-size: 0.75em;">{a0:.4f} {s0} + {a1:.2f} {s1}</div>
                    </div>
                    <div class="stat-box" style="background: rgba(16, 185, 129, 0.3); border: 1px solid #4ade80;">
                        <div style="font-size: 0.8em; opacity: 0.8; font-weight: bold;">Накоплено комиссий</div>
                        <div style="font-size: 1.5em; font-weight: bold; color: #4ade80;">+ ${fee_usd:,.4f}</div>
                        <div style="font-size: 0.75em;">{f0:.5f} {s0} + {f1:.4f} {s1}</div>
                    </div>
                </div>
                <div class="range-bar-bg">
                    <div class="range-fill" style="width: 100%;"></div>
                    <div class="price-pointer" style="left: {p_pos}%;"></div>
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 0.9em;">
                    <span>Мин: <b>{p_min:,.1f}</b></span>
                    <span style="color: #fbbf24; font-weight: bold;">Цена: {p_now:,.1f}</span>
                    <span>Макс: <b>{p_max:,.1f}</b></span>
                </div>
            </div>
            """, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Ошибка получения данных: {e}")
