import streamlit as st
from web3 import Web3
import requests
from datetime import date
import math

# --- 1. НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="Architect DeFi Pro", layout="wide")

if "wallet" not in st.session_state: st.session_state.wallet = ""
if "inv_usdc" not in st.session_state: st.session_state.inv_usdc = 175.0
if "inv_eth" not in st.session_state: st.session_state.inv_eth = 0.0

# Стили вынесены отдельно
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
        padding: 20px; border-radius: 15px; margin-bottom: 20px; color: white; font-family: sans-serif;
    }
    .stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 15px 0; }
    .stat-box { background: rgba(255,255,255,0.1); padding: 10px; border-radius: 10px; }
    .exit-box { background: rgba(0,0,0,0.2); padding: 12px; border-radius: 10px; border: 1px dashed #4ade80; font-size: 0.9em; }
    .range-bar { background: rgba(255,255,255,0.2); height: 8px; border-radius: 4px; position: relative; margin: 15px 0 5px 0; }
    .pointer { position: absolute; top: -4px; width: 4px; height: 16px; background: #fbbf24; box-shadow: 0 0 8px #fbbf24; }
</style>
""", unsafe_allow_html=True)

# --- 2. КОНСТАНТЫ И ФУНКЦИИ ---
RPC_URL = "https://arb1.arbitrum.io/rpc"
NFT_MANAGER = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"
w3 = Web3(Web3.HTTPProvider(RPC_URL))

ABI_NFT = [
    {"inputs":[{"name":"owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"type":"function"},
    {"inputs":[{"name":"owner","type":"address"},{"name":"index","type":"uint256"}],"name":"tokenOfOwnerByIndex","outputs":[{"name":"","type":"uint256"}],"type":"function"},
    {"inputs":[{"name":"tokenId","type":"uint256"}],"name":"positions","outputs":[{"name":"nonce","type":"uint96"},{"name":"operator","type":"address"},{"name":"token0","type":"address"},{"name":"token1","type":"address"},{"name":"fee","type":"uint24"},{"name":"tickLower","type":"int24"},{"name":"tickUpper","type":"int24"},{"name":"liquidity","type":"uint128"},{"name":"feeGrowthInside0LastX128","type":"uint256"},{"name":"feeGrowthInside1LastX128","type":"uint256"},{"name":"tokensOwed0","type":"uint128"},{"name":"tokensOwed1","type":"uint128"}],"type":"function"}
]
ABI_ERC20 = [{"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],"type":"function"},{"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function"}]

def tick_to_p(tick, d0, d1): return (1.0001 ** tick) * (10 ** (d0 - d1))

# --- 3. ИНТЕРФЕЙС ---
st.title("Architect DeFi Pro")
st.sidebar.header("Настройки")
wallet = st.sidebar.text_input("Кошелек", value=st.session_state.wallet)
inv_usdc = st.sidebar.number_input("Вклад USDC", value=float(st.session_state.inv_usdc))
inv_eth = st.sidebar.number_input("Вклад ETH", value=float(st.session_state.inv_eth))

if st.sidebar.button("ОБНОВИТЬ", type="primary") and wallet:
    st.session_state.wallet, st.session_state.inv_usdc, st.session_state.inv_eth = wallet, inv_usdc, inv_eth
    try:
        p_eth = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd").json()['ethereum']['usd']
        base_usd = inv_usdc + (inv_eth * p_eth)
        
        target = w3.to_checksum_address(wallet.strip())
        nft = w3.eth.contract(address=NFT_MANAGER, abi=ABI_NFT)
        for i in range(nft.functions.balanceOf(target).call()):
            tid = nft.functions.tokenOfOwnerByIndex(target, i).call()
            pos = nft.functions.positions(tid).call()
            if pos[7] == 0: continue

            t0, t1 = w3.eth.contract(pos[2], abi=ABI_ERC20), w3.eth.contract(pos[3], abi=ABI_ERC20)
            s0, d0, s1, d1 = t0.functions.symbol().call(), t0.functions.decimals().call(), t1.functions.symbol().call(), t1.functions.decimals().call()
            
            # Цены
            p_low_raw = tick_to_p(pos[5], d0, d1)
            p_high_raw = tick_to_p(pos[6], d0, d1)
            
            # Определяем где ETH (обычно это WETH)
            is_eth_token1 = "USD" in s0
            p_min = 1/p_high_raw if is_eth_token1 else p_low_raw
            p_max = 1/p_low_raw if is_eth_token1 else p_high_raw
            p_now = p_eth
            
            # Расчет активов (упрощенная модель Uniswap V3)
            L = pos[7]
            sqrtA, sqrtB, sqrtP = math.sqrt(p_min), math.sqrt(p_max), math.sqrt(p_now)
            
            # Корректный расчет для выхода
            if is_eth_token1:
                e_exit_eth = (L * (sqrtB - sqrtA) / (sqrtA * sqrtB)) / (10**d1)
                e_exit_usdc = (L * (sqrtB - sqrtA)) / (10**d0)
            else:
                e_exit_eth = (L * (sqrtB - sqrtA) / (sqrtA * sqrtB)) / (10**d0)
                e_exit_usdc = (L * (sqrtB - sqrtA)) / (10**d1)

            avg_p = e_exit_usdc / e_exit_eth if e_exit_eth > 0 else 0
            p_pos = max(0, min(100, (p_now - p_min) / (p_max - p_min) * 100))

            # Рендеринг через f-строку и st.html
            card_html = f"""
            <div class="metric-card">
                <div style="display: flex; justify-content: space-between;">
                    <b>{s0}/{s1} #{tid}</b>
                    <b style="color: #4ade80;">ROI: {((e_exit_usdc-base_usd)/base_usd*100):+.1f}%</b>
                </div>
                <div class="stat-grid">
                    <div class="stat-box">Текущая цена: ${p_now:,.1f}</div>
                    <div class="stat-box">Вложено: ${base_usd:,.1f}</div>
                </div>
                <div class="exit-box">
                    <div style="display:flex; justify-content:space-between">
                        <span>📉 Выход вниз:</span> <b>{e_exit_eth:.3f} ETH (ср. ${avg_p:,.1f})</b>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-top:5px">
                        <span>📈 Выход вверх:</span> <b>{e_exit_usdc:,.1f} USDC</b>
                    </div>
                </div>
                <div class="range-bar"><div class="pointer" style="left: {p_pos}%;"></div></div>
                <div style="display:flex; justify-content:space-between; font-size:0.8em; opacity:0.8">
                    <span>MIN: {p_min:,.1f}</span><span>MAX: {p_max:,.1f}</span>
                </div>
            </div>
            """
            st.markdown(card_html, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Ошибка: {e}")
