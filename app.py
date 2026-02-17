import streamlit as st
from web3 import Web3
import requests
from datetime import date
import math

# --- 1. НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="Architect DeFi Pro", layout="wide")

# Память сессии (чтобы данные не пропадали)
if "wallet" not in st.session_state: st.session_state.wallet = ""
if "inv_usdc" not in st.session_state: st.session_state.inv_usdc = 175.0
if "inv_eth" not in st.session_state: st.session_state.inv_eth = 0.0
if "start_date" not in st.session_state: st.session_state.start_date = date(2026, 1, 1)

st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
        padding: 25px; border-radius: 20px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.2);
        margin-bottom: 25px; color: #fff; font-family: sans-serif;
    }
    .stat-box {
        background: rgba(255,255,255,0.15);
        padding: 15px; border-radius: 12px;
        border: 1px solid rgba(255,255,255,0.2);
    }
    .exit-box {
        background: rgba(15, 23, 42, 0.4);
        border: 1px dashed #4ade80;
        padding: 15px; border-radius: 12px;
        margin-top: 15px;
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

# --- 2. КОНСТАНТЫ И ФУНКЦИИ ---
RPC_URL = "https://arb1.arbitrum.io/rpc"
NFT_MANAGER = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"
w3 = Web3(Web3.HTTPProvider(RPC_URL))

ABI_NFT = [
    {"inputs":[{"name":"owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"type":"function"},
    {"inputs":[{"name":"owner","type":"address"},{"name":"index","type":"uint256"}],"name":"tokenOfOwnerByIndex","outputs":[{"name":"","type":"uint256"}],"type":"function"},
    {"inputs":[{"name":"tokenId","type":"uint256"}],"name":"positions","outputs":[{"name":"nonce","type":"uint96"},{"name":"operator","type":"address"},{"name":"token0","type":"address"},{"name":"token1","type":"address"},{"name":"fee","type":"uint24"},{"name":"tickLower","type":"int24"},{"name":"tickUpper","type":"int24"},{"name":"liquidity","type":"uint128"},{"name":"feeGrowthInside0LastX128","type":"uint256"},{"name":"feeGrowthInside1LastX128","type":"uint256"},{"name":"tokensOwed0","type":"uint128"},{"name":"tokensOwed1","type":"uint128"}],"type":"function"},
    {"inputs":[{"components":[{"name":"tokenId","type":"uint256"},{"name":"recipient","type":"address"},{"name":"amount0Max","type":"uint128"},{"name":"amount1Max","type":"uint128"}],"name":"params","type":"tuple"}],"name":"collect","outputs":[{"name":"amount0","type":"uint256"},{"name":"amount1","type":"uint256"}],"type":"function"}
]
ABI_ERC20 = [{"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],"type":"function"},{"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function"}]

def get_tick_p(tick, d0, d1): return (1.0001 ** tick) * (10 ** (d0 - d1))

# --- 3. ИНТЕРФЕЙС ---
st.title("Architect DeFi Pro")
st.sidebar.header("Параметры")

wallet = st.sidebar.text_input("Кошелек Arbitrum", value=st.session_state.wallet)
start_date = st.sidebar.date_input("Дата открытия", value=st.session_state.start_date)
u_inv = st.sidebar.number_input("Вклад USDC", min_value=0.0, value=float(st.session_state.inv_usdc))
e_inv = st.sidebar.number_input("Вклад ETH", min_value=0.0, value=float(st.session_state.inv_eth))

if st.sidebar.button("ОБНОВИТЬ ДАННЫЕ", type="primary") and wallet:
    st.session_state.wallet, st.session_state.inv_usdc, st.session_state.inv_eth, st.session_state.start_date = wallet, u_inv, e_inv, start_date
    try:
        p_eth = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd").json()['ethereum']['usd']
        initial_usd = u_inv + (e_inv * p_eth)
        
        target = w3.to_checksum_address(wallet.strip())
        nft = w3.eth.contract(address=NFT_MANAGER, abi=ABI_NFT)
        count = nft.functions.balanceOf(target).call()

        for i in range(count):
            tid = nft.functions.tokenOfOwnerByIndex(target, i).call()
            pos = nft.functions.positions(tid).call()
            if pos[7] == 0: continue

            t0_c, t1_c = w3.eth.contract(pos[2], abi=ABI_ERC20), w3.eth.contract(pos[3], abi=ABI_ERC20)
            s0, d0, s1, d1 = t0_c.functions.symbol().call(), t0_c.functions.decimals().call(), t1_c.functions.symbol().call(), t1_c.functions.decimals().call()
            
            is_inv = "USD" in s0
            p_min = 1/get_tick_p(pos[6], d0, d1) if is_inv else get_tick_p(pos[5], d0, d1)
            p_max = 1/get_tick_p(pos[5], d0, d1) if is_inv else get_tick_p(pos[6], d0, d1)
            
            # Комиссии
            f_raw = nft.functions.collect({"tokenId": tid, "recipient": target, "amount0Max": 2**128-1, "amount1Max": 2**128-1}).call({'from': target})
            fee_usd = (f_raw[0]/(10**d0)*p_eth + f_raw[1]/(10**d1)) if not is_inv else (f_raw[0]/(10**d0) + f_raw[1]/(10**d1)*p_eth)
            
            # Математика выхода
            L = pos[7]
            sqrtA, sqrtB = math.sqrt(1.0001**pos[5]), math.sqrt(1.0001**pos[6])
            if is_inv:
                max_usdc = (L * (sqrtB - sqrtA)) / (10**d0)
                max_eth = (L * (sqrtB - sqrtA) / (sqrtA * sqrtB)) / (10**d1)
            else:
                max_eth = (L * (sqrtB - sqrtA) / (sqrtA * sqrtB)) / (10**d0)
                max_usdc = (L * (sqrtB - sqrtA)) / (10**d1)

            avg_p = max_usdc / max_eth if max_eth > 0 else 0
            roi = (fee_usd / initial_usd * 100) if initial_usd > 0 else 0
            p_pos = max(0, min(100, (p_eth - p_min) / (p_max - p_min) * 100))

            card_html = f"""<div class="metric-card">
<div style="display:flex;justify-content:space-between;align-items:center;">
<h2 style="margin:0;">{s0}/{s1} #{tid}</h2>
<span style="font-size:1.5em;font-weight:bold;color:#4ade80;">{roi:+.2f}% ROI (fees)</span>
</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-top:15px;">
<div class="stat-box">
<div style="opacity:0.7;font-size:0.8em;">Вход (база)</div>
<div style="font-size:1.4em;font-weight:bold;">${initial_usd:,.2f}</div>
</div>
<div class="stat-box" style="background:rgba(16,185,129,0.2);">
<div style="opacity:0.7;font-size:0.8em;">Комиссии</div>
<div style="font-size:1.4em;font-weight:bold;color:#4ade80;">+${fee_usd:,.2f}</div>
</div>
</div>
<div class="exit-box">
<div style="display:flex;justify-content:space-between;">
<span>📉 Выход вниз (100% ETH):</span>
<b>~{max_eth:.3f} ETH (ср. ${avg_p:,.1f})</b>
</div>
<div style="display:flex;justify-content:space-between;margin-top:8px;">
<span>📈 Выход вверх (100% USDC):</span>
<b>~{max_usdc:,.1f} USDC</b>
</div>
</div>
<div class="range-bar-bg"><div class="range-fill" style="width:100%;"></div><div class="price-pointer" style="left:{p_pos}%;"></div></div>
<div style="display:flex;justify-content:space-between;font-size:0.85em;">
<span>MIN: {p_min:,.1f}</span>
<span style="color:#fbbf24;font-weight:bold;">Цена ETH: {p_eth:,.1f}</span>
<span>MAX: {p_max:,.1f}</span>
</div>
</div>"""
            st.markdown(card_html, unsafe_allow_html=True)
            
    except Exception as e:
        st.error(f"Ошибка: {e}")
