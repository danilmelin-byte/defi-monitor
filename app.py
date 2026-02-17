import streamlit as st
from web3 import Web3
import requests
from datetime import date

# --- 1. НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="Architect DeFi Pro", layout="wide")

# Инициализация сессии (храним данные, пока открыта вкладка)
if "wallet" not in st.session_state: st.session_state.wallet = ""
if "inv_usdc" not in st.session_state: st.session_state.inv_usdc = 175.0
if "inv_eth" not in st.session_state: st.session_state.inv_eth = 0.0

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
    .buffer-box {
        background: rgba(251, 191, 36, 0.15);
        border: 1px solid #fbbf24;
        padding: 10px; border-radius: 12px;
        margin-bottom: 15px; text-align: center;
        font-size: 0.85rem; color: #fbbf24;
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
</style>
""", unsafe_allow_html=True)

# --- 2. КОНСТАНТЫ ---
RPC_URL = "https://arb1.arbitrum.io/rpc"
NFT_MANAGER = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"
FACTORY_ADDR = "0x1F98431c8aD98523631AE4a59f267346ea31F984"
w3 = Web3(Web3.HTTPProvider(RPC_URL))

ABI_NFT = [
    {"inputs":[{"name":"owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"type":"function"},
    {"inputs":[{"name":"owner","type":"address"},{"name":"index","type":"uint256"}],"name":"tokenOfOwnerByIndex","outputs":[{"name":"","type":"uint256"}],"type":"function"},
    {"inputs":[{"name":"tokenId","type":"uint256"}],"name":"positions","outputs":[{"name":"nonce","type":"uint96"},{"name":"operator","type":"address"},{"name":"token0","type":"address"},{"name":"token1","type":"address"},{"name":"fee","type":"uint24"},{"name":"tickLower","type":"int24"},{"name":"tickUpper","type":"int24"},{"name":"liquidity","type":"uint128"},{"name":"feeGrowthInside0LastX128","type":"uint256"},{"name":"feeGrowthInside1LastX128","type":"uint256"},{"name":"tokensOwed0","type":"uint128"},{"name":"tokensOwed1","type":"uint128"}],"type":"function"},
    {"inputs":[{"components":[{"name":"tokenId","type":"uint256"},{"name":"recipient","type":"address"},{"name":"amount0Max","type":"uint128"},{"name":"amount1Max","type":"uint128"}],"name":"params","type":"tuple"}],"name":"collect","outputs":[{"name":"amount0","type":"uint256"},{"name":"amount1","type":"uint256"}],"type":"function"}
]
ABI_ERC20 = [{"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],"type":"function"},{"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function"}]
ABI_POOL = [{"inputs":[],"name":"slot0","outputs":[{"name":"sqrtPriceX96","type":"uint160"},{"name":"tick","type":"int24"}],"type":"function"}]
ABI_FACTORY = [{"inputs":[{"name":"t0","type":"address"},{"name":"t1","type":"address"},{"name":"fee","type":"uint24"}],"name":"getPool","outputs":[{"name":"","type":"address"}],"type":"function"}]

# --- 3. ФУНКЦИИ ---
def tick_to_price(tick, d0, d1):
    return (1.0001 ** tick) * (10 ** (d0 - d1))

def get_amounts(liquidity, cur_tick, tick_low, tick_high, d0, d1):
    if liquidity == 0: return 0, 0
    sqrtP, sqrtA, sqrtB = 1.0001**(cur_tick/2), 1.0001**(tick_low/2), 1.0001**(tick_high/2)
    if cur_tick < tick_low:
        a0 = liquidity * (sqrtB - sqrtA) / (sqrtA * sqrtB); a1 = 0
    elif cur_tick < tick_high:
        a0 = liquidity * (sqrtB - sqrtP) / (sqrtP * sqrtB); a1 = liquidity * (sqrtP - sqrtA)
    else:
        a0 = 0; a1 = liquidity * (sqrtB - sqrtA)
    return a0 / (10**d0), a1 / (10**d1)

# --- 4. САЙДБАР ---
st.sidebar.title("💎 Параметры")
wallet = st.sidebar.text_input("Кошелек", value=st.session_state.wallet)
start_date = st.sidebar.date_input("Дата открытия", date(2026, 1, 1))

st.sidebar.markdown("---")
st.sidebar.write("💰 Вклад при открытии:")
inv_usdc = st.sidebar.number_input("USDC", value=st.session_state.inv_usdc)
inv_eth = st.sidebar.number_input("ETH", value=st.session_state.inv_eth)

btn = st.sidebar.button("ОБНОВИТЬ", type="primary", use_container_width=True)

if btn and wallet:
    # Сохраняем в память
    st.session_state.wallet = wallet
    st.session_state.inv_usdc = inv_usdc
    st.session_state.inv_eth = inv_eth

    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd", timeout=5).json()
        p_eth = r['ethereum']['usd']
        
        # Считаем суммарный вход в USD по текущему курсу
        total_initial_usd = inv_usdc + (inv_eth * p_eth)

        target = w3.to_checksum_address(wallet.strip())
        nft_contract = w3.eth.contract(address=NFT_MANAGER, abi=ABI_NFT)
        factory = w3.eth.contract(address=FACTORY_ADDR, abi=ABI_FACTORY)
        count = nft_contract.functions.balanceOf(target).call()
        
        st.title("Architect DeFi Pro")

        for i in range(count):
            tid = nft_contract.functions.tokenOfOwnerByIndex(target, i).call()
            pos = nft_contract.functions.positions(tid).call()
            if pos[7] == 0: continue

            t0_c, t1_c = w3.eth.contract(address=pos[2], abi=ABI_ERC20), w3.eth.contract(address=pos[3], abi=ABI_ERC20)
            s0, d0, s1, d1 = t0_c.functions.symbol().call(), t0_c.functions.decimals().call(), t1_c.functions.symbol().call(), t1_c.functions.decimals().call()
            pool_addr = factory.functions.getPool(pos[2], pos[3], pos[4]).call()
            cur_tick = w3.eth.contract(address=pool_addr, abi=ABI_POOL).functions.slot0().call()[1]

            fees = nft_contract.functions.collect({"tokenId": tid, "recipient": target, "amount0Max": 2**128-1, "amount1Max": 2**128-1}).call({'from': target})
            f0, f1 = fees[0] / (10**d0), fees[1] / (10**d1)

            is_inv = (s0 in ["USDC", "USDT", "DAI"])
            p_min_r, p_max_r, p_now_r = tick_to_price(pos[5], d0, d1), tick_to_price(pos[6], d0, d1), tick_to_price(cur_tick, d0, d1)
            p_min, p_max, p_now = (1/p_max_r, 1/p_min_r, 1/p_now_r) if is_inv else (p_min_r, p_max_r, p_now_r)

            a0, a1 = get_amounts(pos[7], cur_tick, pos[5], pos[6], d0, d1)
            val_usd = (a0 * p_eth + a1) if not is_inv else (a0 + a1 * p_eth)
            fee_usd = (f0 * p_eth + f1) if not is_inv else (f0 + f1 * p_eth)

            days = max((date.today() - start_date).days, 1)
            roi_pct = ((val_usd + fee_usd - total_initial_usd) / total_initial_usd * 100) if total_initial_usd > 0 else 0
            in_range = pos[5] <= cur_tick <= pos[6]
            p_pos = max(0, min(100, (cur_tick - pos[5]) / (pos[6] - pos[5]) * 100))

            buffer_html = ""
            if in_range:
                d_low = ((p_now - p_min) / p_now) * 100
                d_high = ((p_max - p_now) / p_now) * 100
                buffer_html = f'<div class="buffer-box">🛡️ Запас: <b>{d_low:.1f}%</b> до низа | <b>{d_high:.1f}%</b> до верха</div>'

            st.markdown(f"""
<div class="metric-card">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
        <h2 style="margin:0;">{s0}/{s1} <span style="font-size: 0.6em; opacity: 0.7;">#{tid}</span></h2>
        <span style="font-size: 1.2rem; font-weight: 800; color: {'#4ade80' if roi_pct >= 0 else '#f87171'};">{roi_pct:+.2f}% ROI</span>
    </div>
    {buffer_html}
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px;">
        <div class="stat-box">
            <div style="font-size: 0.8rem; opacity: 0.8;">Тело позиции</div>
            <div style="font-size: 1.3rem; font-weight: bold;">${val_usd:,.2f}</div>
            <div style="font-size: 0.7rem; opacity: 0.6;">{a0:.4f} {s0} + {a1:.2f} {s1}</div>
        </div>
        <div class="stat-box" style="background: rgba(74, 222, 128, 0.2);">
            <div style="font-size: 0.8rem; opacity: 0.8;">Комиссии</div>
            <div style="font-size: 1.3rem; font-weight: bold; color: #4ade80;">+${fee_usd:,.2f}</div>
            <div style="font-size: 0.7rem; opacity: 0.6;">{f0:.5f} {s0} + {f1:.4f} {s1}</div>
        </div>
    </div>
    <div class="range-bar-bg">
        <div class="range-fill" style="width: 100%;"></div>
        <div class="price-pointer" style="left: {p_pos}%;"></div>
    </div>
    <div style="display: flex; justify-content: space-between; font-size: 0.8rem;">
        <span>Мин: <b>{p_min:,.1f}</b></span>
        <span style="color: #fbbf24; font-weight: bold;">Цена: {p_now:,.1f}</span>
        <span>Макс: <b>{p_max:,.1f}</b></span>
    </div>
</div>""", unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Ошибка: {e}")
