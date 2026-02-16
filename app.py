import streamlit as st
import requests
from web3 import Web3
import time

# --- 1. НАСТРОЙКИ СТРАНИЦЫ И СТИЛИ ---
st.set_page_config(page_title="Architect DeFi Monitor", layout="wide", page_icon="🦄")

st.markdown("""
    <style>
    .metric-card { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #eee; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); }
    .alert-box { padding: 12px; border-radius: 7px; margin-bottom: 10px; border-left: 5px solid; font-weight: 500; }
    .alert-danger { background-color: #ffebee; border-left-color: #ef5350; color: #c62828; }
    .alert-warning { background-color: #fff3e0; border-left-color: #ffa726; color: #ef6c00; }
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
    {"inputs":[{"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"positions","outputs":[{"internalType":"uint96","name":"nonce","type":"uint96"},{"internalType":"address","name":"operator","type":"address"},{"internalType":"address","name":"token0","type":"address"},{"internalType":"address","name":"token1","type":"address"},{"internalType":"uint24","name":"fee","type":"uint24"},{"internalType":"int24","name":"tickLower","type":"int24"},{"internalType":"int24","name":"tickUpper","type":"int24"},{"internalType":"uint128","name":"liquidity","type":"uint128"},{"internalType":"uint256","name":"feeGrowthInside0LastX128","type":"uint256"},{"internalType":"uint256","name":"feeGrowthInside1LastX128","type":"uint256"},{"internalType":"uint128","name":"tokensOwed0","type":"uint128"},{"internalType":"uint128","name":"tokensOwed1","type":"uint128"}],"stateMutability":"view","type":"function"}
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

def multicall_batch(calls_info):
    if not calls_info: return []
    mc_contract = w3.eth.contract(address=MULTICALL_ADDR, abi=MULTICALL_ABI)
    
    encoded = []
    for contract_obj, fn_name, args in calls_info:
        fn_obj = contract_obj.get_function_by_name(fn_name)
        encoded.append({
            'target': contract_obj.address, 
            'callData': fn_obj(*args).encodeABI()
        })
    
    try:
        _, return_data = mc_contract.functions.aggregate(encoded).call()
        results = []
        for i, (contract, fn_name, _) in enumerate(calls_info):
            fn_obj = contract.get_function_by_name(fn_name)
            out_types = [o['type'] for o in fn_obj.abi['outputs']]
            decoded = w3.eth.codec.decode(out_types, return_data[i])
            results.append(decoded[0] if len(decoded) == 1 else decoded)
        return results
    except Exception as e:
        st.error(f"Multicall error: {e}")
        return [None] * len(calls_info)

# --- 5. ИНТЕРФЕЙС ---
with st.sidebar:
    st.header("⚙️ Настройки")
    wallet_input = st.text_input("Адрес кошелька", value="0x995907fe97C9CAd3D310c4F384453E8676F4a170")
    refresh_rate = st.selectbox("Автообновление (сек)", [0, 30, 60, 300], index=2)
    btn_scan = st.button("🔎 Сканировать", use_container_width=True)

# --- 6. ЛОГИКА ---
if (btn_scan or refresh_rate > 0) and wallet_input:
    try:
        wallet = w3.to_checksum_address(wallet_input)
        manager = w3.eth.contract(address=NFT_MANAGER, abi=MANAGER_ABI)
        factory = w3.eth.contract(address=FACTORY_ADDR, abi=FACTORY_ABI)
        
        with st.spinner("Загрузка данных из Arbitrum..."):
            count = manager.functions.balanceOf(wallet).call()
            if count == 0:
                st.warning("На этом кошельке нет активных позиций Uniswap V3.")
            else:
                # 1. ID токенов
                ids_calls = [(manager, 'tokenOfOwnerByIndex', [wallet, i]) for i in range(count)]
                token_ids = multicall_batch(ids_calls)
                
                # 2. Данные позиций
                pos_calls = [(manager, 'positions', [tid]) for tid in token_ids]
                raw_pos = multicall_batch(pos_calls)
                
                # 3. Метаданные (Символы и Десятичные)
                unique_tokens = list(set([p[2] for p in raw_pos] + [p[3] for p in raw_pos]))
                meta_calls = []
                for t in unique_tokens:
                    c = w3.eth.contract(address=t, abi=ERC20_ABI)
                    meta_calls.extend([(c, 'symbol', []), (c, 'decimals', [])])
                
                # 4. Адреса пулов
                for p in raw_pos:
                    meta_calls.append((factory, 'getPool', [p[2], p[3], p[4]]))
                
                meta_res = multicall_batch(meta_calls)
                
                # Маппинг результатов
                sym_map = {unique_tokens[i]: meta_res[i*2] for i in range(len(unique_tokens))}
                dec_map = {unique_tokens[i]: meta_res[i*2+1] for i in range(len(unique_tokens))}
                
                offset = len(unique_tokens) * 2
                pool_map = {}
                for i in range(len(raw_pos)):
                    pool_map[i] = meta_res[offset + i]
                
                # 5. Текущие тики (цены) в пулах
                unique_pools = list(set(pool_map.values()))
                tick_calls = [(w3.eth.contract(address=a, abi=POOL_ABI), 'slot0', []) for a in unique_pools if a != "0x0000000000000000000000000000000000000000"]
                tick_res = multicall_batch(tick_calls)
                tick_data = {unique_pools[i]: tick_res[i][1] for i in range(len(tick_res)) if tick_res[i]}

                # ВЫВОД РЕЗУЛЬТАТОВ
                st.subheader("🔔 Статус позиций")
                cols = st.columns(3)
                
                for i, p in enumerate(raw_pos):
                    tid = token_ids[i]
                    pool_addr = pool_map[i]
                    curr_tick = tick_data.get(pool_addr, 0)
                    
                    in_range = p[5] <= curr_tick <= p[6]
                    s0, s1 = sym_map[p[2]], sym_map[p[3]]
                    
                    with cols[i % 3]:
                        if in_range:
                            st.markdown(f"<div class='alert-box' style='background-color: #e8f5e9; border-left-color: #4caf50; color: #2e7d32;'>✅ #{tid} {s0}/{s1}<br>В диапазоне</div>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<div class='alert-box alert-danger'>🚨 #{tid} {s0}/{s1}<br>ВНЕ ДИАПАЗОНА!</div>", unsafe_allow_html=True)
                        
                        st.caption(f"Комиссия: {p[4]/10000}%")

    except Exception as e:
        st.error(f"Ошибка приложения: {e}")

    if refresh_rate > 0:
        time.sleep(refresh_rate)
        st.rerun()
