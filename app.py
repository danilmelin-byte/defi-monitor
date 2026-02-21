import streamlit as st
from web3 import Web3
import requests
from datetime import date
import math

# --- 1. PAGE SETTINGS ---
st.set_page_config(page_title="Architect DeFi Pro", layout="wide")

# Session memory (values persist between updates)
if "wallet" not in st.session_state: st.session_state.wallet = ""
if "inv_usdc" not in st.session_state: st.session_state.inv_usdc = 175.0
if "inv_eth" not in st.session_state: st.session_state.inv_eth = 0.0
if "start_date" not in st.session_state: st.session_state.start_date = date(2026, 1, 1)
if "p_eth_entry" not in st.session_state: st.session_state.p_eth_entry = None
if "goal_name" not in st.session_state: st.session_state.goal_name = ""
if "goal_cost" not in st.session_state: st.session_state.goal_cost = 0.0

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
    .income-box {
        background: rgba(74, 222, 128, 0.15);
        border: 1px solid #4ade80;
        padding: 15px; border-radius: 12px;
        margin-top: 15px;
    }
    .exit-box {
        background: rgba(15, 23, 42, 0.4);
        border: 1px dashed #4ade80;
        padding: 15px; border-radius: 12px;
        margin-top: 15px;
    }
    .hodl-box {
        background: rgba(251, 191, 36, 0.1);
        border: 1px solid #fbbf24;
        padding: 15px; border-radius: 12px;
        margin-top: 10px;
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
    .goal-box {
        background: rgba(139, 92, 246, 0.15);
        border: 1px solid #8b5cf6;
        padding: 20px; border-radius: 16px;
        margin-top: 15px;
        display: flex; align-items: center; gap: 24px;
    }
    .goal-ring-wrap {
        flex-shrink: 0;
    }
    .goal-info {
        flex: 1;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. CONSTANTS ---
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

# --- 3. FUNCTIONS ---
def tick_to_price(tick, d0, d1):
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
        a0, a1 = 0, liquidity * (sqrtB - sqrtA)
    return a0 / (10 ** d0), a1 / (10 ** d1)

# --- 4. INTERFACE ---
st.title("Architect DeFi Pro")
st.sidebar.header("Parameters")

wallet = st.sidebar.text_input("Arbitrum Wallet", value=st.session_state.wallet)
start_date = st.sidebar.date_input("Position Open Date", value=st.session_state.start_date)
u_inv = st.sidebar.number_input("USDC Deposit", min_value=0.0, value=float(st.session_state.inv_usdc))
e_inv = st.sidebar.number_input("ETH Deposit", min_value=0.0, value=float(st.session_state.inv_eth))

st.sidebar.markdown("---")
goal_name = st.sidebar.text_input("Savings Goal", value=st.session_state.goal_name, placeholder="e.g. Laptop, Vacation...")
goal_cost = st.sidebar.number_input("Goal Cost ($)", min_value=0.0, value=float(st.session_state.goal_cost))

if st.sidebar.button("REFRESH DATA", type="primary") and wallet:
    st.session_state.wallet = wallet
    st.session_state.inv_usdc = u_inv
    st.session_state.inv_eth = e_inv
    st.session_state.start_date = start_date
    st.session_state.goal_name = goal_name
    st.session_state.goal_cost = goal_cost

    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd",
            timeout=5
        ).json()
        p_eth = r['ethereum']['usd']

        # Store ETH price at first run for accurate HODL comparison
        if st.session_state.p_eth_entry is None:
            st.session_state.p_eth_entry = p_eth
        p_eth_entry = st.session_state.p_eth_entry

        # Deposit value at entry and current HODL value of the same tokens
        initial_usd = u_inv + e_inv * p_eth_entry
        hodl_usd = u_inv + e_inv * p_eth

        target = w3.to_checksum_address(wallet.strip())
        nft_contract = w3.eth.contract(address=NFT_MANAGER, abi=ABI_NFT)
        factory = w3.eth.contract(address=FACTORY_ADDR, abi=ABI_FACTORY)
        count = nft_contract.functions.balanceOf(target).call()

        for i in range(count):
            tid = nft_contract.functions.tokenOfOwnerByIndex(target, i).call()
            pos = nft_contract.functions.positions(tid).call()
            if pos[7] == 0: continue

            t0_c = w3.eth.contract(address=pos[2], abi=ABI_ERC20)
            t1_c = w3.eth.contract(address=pos[3], abi=ABI_ERC20)
            s0, d0 = t0_c.functions.symbol().call(), t0_c.functions.decimals().call()
            s1, d1 = t1_c.functions.symbol().call(), t1_c.functions.decimals().call()

            # Exact current tick from pool (via Factory)
            pool_addr = factory.functions.getPool(pos[2], pos[3], pos[4]).call()
            cur_tick = w3.eth.contract(address=pool_addr, abi=ABI_POOL).functions.slot0().call()[1]

            is_inv = s0 in ["USDC", "USDT", "DAI"]

            # Range boundaries
            p_min_r = tick_to_price(pos[5], d0, d1)
            p_max_r = tick_to_price(pos[6], d0, d1)
            p_now_r = tick_to_price(cur_tick, d0, d1)
            if is_inv:
                p_min, p_max, p_now = 1 / p_max_r, 1 / p_min_r, 1 / p_now_r
            else:
                p_min, p_max, p_now = p_min_r, p_max_r, p_now_r

            # Current token amounts in position
            a0, a1 = get_amounts(pos[7], cur_tick, pos[5], pos[6], d0, d1)
            val_usd = (a0 * p_eth + a1) if not is_inv else (a0 + a1 * p_eth)

            # Accumulated fees
            live_fees = nft_contract.functions.collect({
                "tokenId": tid, "recipient": target,
                "amount0Max": 2**128 - 1, "amount1Max": 2**128 - 1
            }).call({'from': target})
            f0 = live_fees[0] / (10 ** d0)
            f1 = live_fees[1] / (10 ** d1)
            fee_usd = (f0 * p_eth + f1) if not is_inv else (f0 + f1 * p_eth)

            # Exit scenarios at range boundary breach
            L = pos[7]
            sqrtA = math.sqrt(1.0001 ** pos[5])
            sqrtB = math.sqrt(1.0001 ** pos[6])
            if is_inv:
                exit_usdc = (L * (sqrtB - sqrtA)) / (10 ** d0)
                exit_eth = (L * (sqrtB - sqrtA) / (sqrtA * sqrtB)) / (10 ** d1)
            else:
                exit_eth = (L * (sqrtB - sqrtA) / (sqrtA * sqrtB)) / (10 ** d0)
                exit_usdc = (L * (sqrtB - sqrtA)) / (10 ** d1)
            avg_exit_p = exit_usdc / exit_eth if exit_eth > 0 else 0

            # Analytics
            days = max((date.today() - start_date).days, 1)
            total_current = val_usd + fee_usd
            roi_abs = total_current - initial_usd
            roi_pct = (roi_abs / initial_usd * 100) if initial_usd > 0 else 0
            daily = fee_usd / days
            monthly = daily * 30
            apr = (fee_usd / val_usd) * (365 / days) * 100 if val_usd > 0 else 0
            vs_hodl = total_current - hodl_usd

            # Savings goal
            g_name = st.session_state.goal_name
            g_cost = st.session_state.goal_cost
            goal_html = ""
            if g_name and g_cost > 0:
                g_pct = min(fee_usd / g_cost * 100, 100)
                # SVG ring: r=45, circumference ≈ 282.74
                radius = 45
                circ = 2 * math.pi * radius
                dash_fill = circ * g_pct / 100
                dash_gap = circ - dash_fill
                # Ring color: red → yellow → green
                if g_pct < 50:
                    t = g_pct / 50
                    r_c = 255
                    g_c = int(t * 220)
                    ring_color = f"rgb({r_c},{g_c},40)"
                elif g_pct < 100:
                    t = (g_pct - 50) / 50
                    r_c = int(255 * (1 - t))
                    ring_color = f"rgb({r_c},220,40)"
                else:
                    ring_color = "#4ade80"
                days_left = ((g_cost - fee_usd) / daily) if daily > 0 else 0
                goal_html = f"""
<div class="goal-box">
  <div class="goal-ring-wrap">
    <svg width="120" height="120" viewBox="0 0 120 120">
      <circle cx="60" cy="60" r="{radius}"
        fill="none" stroke="rgba(255,255,255,0.1)" stroke-width="10"/>
      <circle cx="60" cy="60" r="{radius}"
        fill="none" stroke="{ring_color}" stroke-width="10"
        stroke-linecap="round"
        stroke-dasharray="{dash_fill:.2f} {dash_gap:.2f}"
        transform="rotate(-90 60 60)"/>
      <text x="60" y="55" text-anchor="middle"
        font-size="16" font-weight="bold" fill="#fff">{g_pct:.1f}%</text>
      <text x="60" y="72" text-anchor="middle"
        font-size="9" fill="rgba(255,255,255,0.7)">completed</text>
    </svg>
  </div>
  <div class="goal-info">
    <div style="font-size:0.75em;opacity:0.7;margin-bottom:4px;">Savings Goal</div>
    <div style="font-size:1.15em;font-weight:bold;color:#c4b5fd;margin-bottom:8px;">🎯 {g_name}</div>
    <div style="font-size:0.85em;margin-bottom:4px;">
      Accumulated: <b style="color:#4ade80;">${fee_usd:,.2f}</b>
      <span style="opacity:0.6;"> / ${g_cost:,.2f}</span>
    </div>
    <div style="font-size:0.8em;opacity:0.75;">
      {'✅ Goal reached!' if g_pct >= 100 else f'Remaining: <b>${g_cost - fee_usd:,.2f}</b> (~{int(days_left)} days at current rate)'}
    </div>
  </div>
</div>"""

            # Position on range bar (via ticks — exact calculation)
            p_pos = max(0, min(100, (cur_tick - pos[5]) / (pos[6] - pos[5]) * 100))
            in_range = pos[5] <= cur_tick <= pos[6]

            html_content = f"""
<div class="metric-card">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
<h2 style="margin:0;">{s0}/{s1} <span style="font-size:0.6em;opacity:0.7;">#{tid}</span></h2>
<span style="padding:5px 15px;border-radius:20px;border:1px solid #fff;font-size:0.8em;font-weight:bold;">
{'● IN RANGE' if in_range else '○ OUT OF RANGE'}
</span>
</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;">
<div class="stat-box">
<div style="opacity:0.8;font-size:0.9em;">Current Liquidity</div>
<div style="font-size:1.8em;font-weight:bold;">${val_usd:,.2f}</div>
<div style="font-size:0.8em;">{a0:.4f} {s0} + {a1:.4f} {s1}</div>
</div>
<div class="stat-box" style="background:rgba(16,185,129,0.2);">
<div style="opacity:0.8;font-size:0.9em;">Accumulated Fees</div>
<div style="font-size:1.8em;font-weight:bold;color:#4ade80;">+${fee_usd:,.2f}</div>
<div style="font-size:0.8em;">{f0:.5f} {s0} + {f1:.5f} {s1}</div>
</div>
</div>
<div class="income-box">
<div style="display:grid;grid-template-columns:1fr 1fr 1fr;text-align:center;">
<div>
<div style="font-size:0.8em;opacity:0.9;">ROI (total)</div>
<div style="font-size:1.2em;font-weight:bold;color:#4ade80;">{roi_pct:+.1f}%</div>
<div style="font-size:0.7em;">${roi_abs:+.2f} vs deposit</div>
</div>
<div>
<div style="font-size:0.8em;opacity:0.9;">APR (fees)</div>
<div style="font-size:1.2em;font-weight:bold;">{apr:.1f}%</div>
<div style="font-size:0.75em;">annualized</div>
</div>
<div>
<div style="font-size:0.8em;opacity:0.9;">Monthly Forecast</div>
<div style="font-size:1.2em;font-weight:bold;">${monthly:,.2f}</div>
<div style="font-size:0.75em;">${daily:,.2f} / day</div>
</div>
</div>
</div>
<div class="exit-box">
<div style="opacity:0.7;font-size:0.8em;margin-bottom:8px;">Exit scenarios at range boundary breach:</div>
<div style="display:flex;justify-content:space-between;margin-bottom:6px;">
<span>📉 Exit down (100% ETH):</span>
<b>~{exit_eth:.4f} ETH (avg ${avg_exit_p:,.0f})</b>
</div>
<div style="display:flex;justify-content:space-between;">
<span>📈 Exit up (100% USDC):</span>
<b>~{exit_usdc:,.1f} USDC</b>
</div>
</div>
<div class="hodl-box">
<div style="display:flex;justify-content:space-between;align-items:center;">
<span style="font-size:0.9em;color:#fbbf24;">📊 <b>LP vs HODL:</b></span>
<span style="font-size:1.1em;font-weight:bold;">
{'+' if vs_hodl >= 0 else ''}${vs_hodl:,.2f}
<span style="font-size:0.7em;font-weight:normal;opacity:0.8;">
{'better than holding' if vs_hodl >= 0 else 'worse than holding'}
</span>
</span>
</div>
</div>
<div class="range-bar-bg">
<div class="range-fill" style="width:100%;"></div>
<div class="price-pointer" style="left:{p_pos}%;"></div>
</div>
<div style="display:flex;justify-content:space-between;font-size:0.9em;">
<span>Min: <b>{p_min:,.1f}</b></span>
<span style="color:#fbbf24;font-weight:bold;">ETH Price: {p_now:,.1f}</span>
<span>Max: <b>{p_max:,.1f}</b></span>
</div>
{goal_html}
</div>
"""
            st.markdown(html_content, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Error: {e}")
