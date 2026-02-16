import streamlit as st
import requests
from web3 import Web3
import time

# --- 1. НАСТРОЙКИ СТРАНИЦЫ И СТИЛИ ---
st.set_page_config(page_title="Architect DeFi Monitor", layout="wide", page_icon="🦄")

st.markdown("""
    <style>
    .metric-card { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #eee; }
    .stProgress > div > div > div > div { background-color: #00CC66 !important; }
    .alert-box { padding: 12px; border-radius: 7px; margin-bottom: 10px; border-left: 5px solid; font-weight: 500; }
    .alert-danger { background-color: #ffebee; border-left-color: #ef5350; color: #c62828; }
    .alert-warning { background-color: #fff3e0; border-left-color: #ffa726; color: #ef6c00; }
    .usd-total { font-size: 1.4em; font-weight: bold; color: #1565C0; }
    .fee-total { font-size: 1.2em; font-weight: bold; color: #2E7D32; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. КОНСТАНТЫ И АДРЕСА ---
RPC_URL = "https://arb1.arbitrum.io/rpc"
NFT_MANAGER = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"
FACTORY_ADDR = "0x1F98431c8aD98523631AE4a59f267346ea31F984"
MULTICALL_ADDR = "0xcA11bde05977b3631167028862bE2a173976CA11"

COINGECKO_MAP = {
    'WETH': 'ethereum', 'ETH': 'ethereum', 'USDC': 'usd-coin', 'USDC.e': 'usd-coin',
    'USDT': 'tether', 'ARB': 'arbitrum', 'WBTC': 'bitcoin', 'DAI': 'dai', 'UNI': 'uniswap'
}

# --- 3. ABI ОПРЕДЕЛЕНИЯ ---
MANAGER_ABI = [
    {"inputs":[{"internalType":"address","name":"owner","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"internalType":"address","name":"owner","type":"address"},{"internalType":"uint256","name":"index","type":"uint256"}],"name":"tokenOfOwnerByIndex","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"positions","outputs":[{"internalType":"uint96","name":"nonce","type":"uint96"},{"internalType":"address","name":"operator","type":"address"},{"internalType":"address","name":"token0","type":"address"},{"internalType":"address","name":"token1","type":"address"},{"internalType":"uint24","name":"fee","type":"uint24"},{"internalType":"int24","name":"tickLower","type":"int24"},{"internalType":"int24","name":"tickUpper","type":"int24"},{"internalType":"uint128","name":"liquidity","type":"uint128"},{"internalType":"uint256","name":"feeGrowthInside0LastX128","type":"uint256"},{"internalType":"uint256","name":"feeGrowthInside1LastX128","type":"uint256"},{"internalType":"uint128","name":"tokensOwed0","type":"uint128"},{"internalType":"uint128","name":"tokensOwed1","type":"uint128"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"components":[{"internalType":"uint256","name":"tokenId","type":"uint256"},{"internalType":"address","name":"recipient","type":"address"},{"internalType":"uint128","name":"amount0Max","type":"uint128"},{"internalType":"uint128","name":"amount1Max","type":"uint128"}],"internalType":"struct INonfungiblePositionManager.CollectParams","name":"params","type":"tuple"}],"name":"collect","outputs":[{"internalType":"uint256","name":"amount0","type":"uint256"},{"internalType":"uint256","name":"amount1","type":"uint256"}],"stateMutability":"payable","type":"function"}
]
ERC20_ABI = [
    {"inputs":[],"name":"symbol","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"stateMutability":"view","type":"function"}
]
POOL_ABI = [{"inputs":[],"name":"slot0","outputs":[{"internalType":"uint160","name":"sqrtPriceX96","type":"uint160"},{"internalType":"int24","name":"tick","type":"int24"},{"internalType":"uint16","name":"observationIndex","type":"uint16"},{"internalType":"uint16","name":"observationCardinality","type":"uint16"},{"internalType":"uint16","name":"observationCardinalityNext","type":"uint16"},{"internalType":"uint8","name":"feeProtocol","type":"uint8"},{"internalType":"bool","name":"unlocked","type":"bool"}],"stateMutability":"view","type":"function"}]
FACTORY_ABI = [{"inputs":[{"internalType":"address","name":"","type":"address"},{"internalType":"address","name":"","type":"address"},{"internalType":"uint24","name":"","type":"uint24"}],"name":"getPool","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"}]
MULTICALL_ABI = [{"inputs":[{"components":[{"internalType":"address","name":"target","type":"address"},{"internalType":"bytes","name":"callData","type":"bytes"}],"internalType":"struct Multicall3.Call[]","name":"calls","type":"tuple[]"}],"name":"aggregate","outputs":[{"internalType":"uint256","name":"blockNumber","type":"uint256"},{"internalType":"bytes[]","name":"returnData","type":"bytes[]"}],"stateMutability":"payable","type":"function"}]

# --- 4. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
@st.cache_resource
def get_web3():
    return Web3(Web3.HTTPProvider(RPC_URL))

w3 = get_web3()

@st.cache_data(ttl=300)
def get_usd_prices(symbols):
    ids = [COINGECKO_MAP[s.upper()] for s in symbols if s.upper() in COINGECKO_MAP]
    if not ids: return {}
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={','.join(set(ids))}&vs_currencies=usd"
    try:
        data = requests.get(url, timeout=5).json()
        return {sym: data.get(COINGECKO_MAP.get(sym.upper()), {}).get('usd', 0) for sym in symbols}
    except: return {}

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

def multicall_batch(calls_info):
    if not calls_info: return []
    mc_contract = w3.eth.contract(address=MULTICALL_ADDR, abi=MULTICALL_ABI)
    # СТАЛО:
encoded = [{'target': c[0].address, 'callData': c[0].functions[c[1]](*c[2]).encodeABI()} for c in calls_info]
    try:
        _, return_data = mc_contract.functions.aggregate(encoded).call()
        results = []
        for i, (contract, fn_name, _) in enumerate(calls_info):
            out_types = [o['type'] for o in contract.get_function_by_name(fn_name).abi['outputs']]
            decoded = w3.eth.codec.decode(out_types, return_data[i])
            results.append(decoded[0] if len(decoded) == 1 else decoded)
        return results
    except Exception as e:
        st.error(f"Multicall error: {e}")
        return [None] * len(calls_info)

# --- 5. САЙДБАР И АВТООБНОВЛЕНИЕ ---
with st.sidebar:
    st.header("⚙️ Settings")
    wallet_input = st.text_input("Wallet Address", value="0x995907fe97C9CAd3D310c4F384453E8676F4a170")
    refresh_rate = st.selectbox("Auto-refresh", [0, 30, 60, 300], index=2)
    btn_scan = st.button("🔎 Scan Network", use_container_width=True)

# --- 6. ОСНОВНАЯ ЛОГИКА ---
if (btn_scan or refresh_rate > 0) and wallet_input:
    wallet = w3.to_checksum_address(wallet_input)
    manager = w3.eth.contract(address=NFT_MANAGER, abi=MANAGER_ABI)
    factory = w3.eth.contract(address=FACTORY_ADDR, abi=FACTORY_ABI)
    
    with st.spinner("Batching blockchain data..."):
        try:
            count = manager.functions.balanceOf(wallet).call()
            if count == 0:
                st.warning("No active Uniswap V3 positions.")
            else:
                # PHASE 1: Token IDs
                ids_calls = [(manager, 'tokenOfOwnerByIndex', [wallet, i]) for i in range(count)]
                token_ids = multicall_batch(ids_calls)
                
                # PHASE 2: Positions
                pos_calls = [(manager, 'positions', [tid]) for tid in token_ids]
                raw_pos = multicall_batch(pos_calls)
                
                # PHASE 3: Metadata & Pools
                unique_tokens = list(set([p[2] for p in raw_pos] + [p[3] for p in raw_pos]))
                meta_calls = []
                for t in unique_tokens:
                    c = w3.eth.contract(address=t, abi=ERC20_ABI)
                    meta_calls.extend([(c, 'symbol', []), (c, 'decimals', [])])
                
                for p in raw_pos:
                    meta_calls.append((factory, 'getPool', [p[2], p[3], p[4]]))
                
                meta_res = multicall_batch(meta_calls)
                
                # Parsing Metadata
                sym_map = {unique_tokens[i]: meta_res[i*2] for i in range(len(unique_tokens))}
                dec_map = {unique_tokens[i]: meta_res[i*2+1] for i in range(len(unique_tokens))}
                pool_map = { (raw_pos[i][2], raw_pos[i][3], raw_pos[i][4]): meta_res[len(unique_tokens)*2 + i] for i in range(len(raw_pos))}
                
                # PHASE 4: Ticks
                pool_addrs = list(set(pool_map.values()))
                tick_calls = [(w3.eth.contract(address=a, abi=POOL_ABI), 'slot0', []) for a in pool_addrs if a != "0x0000..."]
                tick_res = multicall_batch(tick_calls)
                tick_map = {pool_addrs[i]: tick_res[i][1] for i in range(len(tick_res)) if tick_res[i]}

                # --- SUMMARY & ALERTS ---
                final_data = []
                price_map = get_usd_prices(list(sym_map.values()))
                
                st.subheader("🔔 Priority Alerts")
                alert_count = 0
                
                for i, p in enumerate(raw_pos):
                    tid = token_ids[i]
                    pool = pool_map[(p[2], p[3], p[4])]
                    curr_tick = tick_map.get(pool, 0)
                    s0, s1 = sym_map[p[2]], sym_map[p[3]]
                    d0, d1 = dec_map[p[2]], dec_map[p[3]]
                    
                    amt0, amt1 = get_amounts(p[7], curr_tick, p[5], p[6], d0, d1)
                    
                    # Check Range
                    in_range = p[5] <= curr_tick <= p[6]
                    if p[7] > 0 and not in_range:
                        st.markdown(f"<div class='alert-box alert-danger'>🚨 Position #{tid} ({s0}/{s1}) is OUT OF RANGE!</div>", unsafe_allow_html=True)
                        alert_count += 1
                
                if alert_count == 0: st.info("✅ All positions are healthy and earning fees.")

                # --- DASHBOARD RENDER ---
                st.divider()
                cols = st.columns(len(raw_pos) if len(raw_pos) < 4 else 3)
                for i, p in enumerate(raw_pos):
                    with cols[i % 3]:
                        st.markdown(f"**Position #{token_ids[i]}** ({sym_map[p[2]]}/{sym_map[p[3]]})")
                        st.caption(f"Fee: {p[4]/10000}%")
                        # (Additional UI details can be added here)

        except Exception as e:
            st.error(f"Logic Error: {e}")

    # Auto-refresh trigger
    if refresh_rate > 0:
        time.sleep(refresh_rate)
        st.rerun()
