import streamlit as st
from web3 import Web3
import requests

# — 1. НАСТРОЙКИ —

st.set_page_config(page_title=“Architect DeFi Pro”, layout=“wide”)

st.markdown(”””

<style>
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 25px; border-radius: 20px;
        box-shadow: 0 8px 32px rgba(102, 126, 234, 0.3);
        margin-bottom: 25px; color: #fff;
    }
    .metric-card h3 {
        margin: 0 0 15px 0;
        font-size: 1.4em;
        font-weight: 600;
    }
    .stat-box {
        background: rgba(255,255,255,0.1);
        backdrop-filter: blur(10px);
        padding: 15px;
        border-radius: 12px;
        border: 1px solid rgba(255,255,255,0.2);
    }
    .stat-label {
        color: rgba(255,255,255,0.8);
        font-size: 0.85em;
        margin-bottom: 5px;
    }
    .stat-value {
        font-size: 1.6em;
        font-weight: bold;
        color: #fff;
    }
    .stat-details {
        font-size: 0.9em;
        color: rgba(255,255,255,0.9);
        margin-top: 5px;
    }
    .range-bar-bg {
        background: rgba(255,255,255,0.2);
        height: 14px;
        border-radius: 7px;
        position: relative;
        margin: 25px 0 15px 0;
        overflow: hidden;
    }
    .range-fill {
        background: linear-gradient(90deg, #4ade80 0%, #22c55e 100%);
        height: 100%;
        border-radius: 7px;
        opacity: 0.4;
        width: 100%;
    }
    .price-pointer {
        position: absolute;
        top: -8px;
        width: 6px;
        height: 30px;
        background: #fbbf24;
        border-radius: 3px;
        box-shadow: 0 0 10px rgba(251, 191, 36, 0.8);
    }
    .range-labels {
        display: flex;
        justify-content: space-between;
        font-size: 0.95em;
        font-weight: 500;
        margin-top: 10px;
    }
    .status-badge {
        display: inline-block;
        padding: 6px 16px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85em;
        letter-spacing: 0.5px;
    }
    .status-active {
        background: rgba(74, 222, 128, 0.2);
        color: #4ade80;
        border: 1px solid #4ade80;
    }
    .status-inactive {
        background: rgba(248, 113, 113, 0.2);
        color: #f87171;
        border: 1px solid #f87171;
    }
    .fees-highlight {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        padding: 15px;
        border-radius: 12px;
        margin-top: 15px;
        border: 2px solid rgba(16, 185, 129, 0.3);
    }
</style>

“””, unsafe_allow_html=True)

# — 2. КОНСТАНТЫ —

RPC_URL = “https://arb1.arbitrum.io/rpc”
NFT_MANAGER = “0xC36442b4a4522E871399CD717aBDD847Ab11FE88”
FACTORY_ADDR = “0x1F98431c8aD98523631AE4a59f267346ea31F984”
w3 = Web3(Web3.HTTPProvider(RPC_URL))

ABI_NFT = [
{“inputs”:[{“name”:“owner”,“type”:“address”}],“name”:“balanceOf”,“outputs”:[{“name”:””,“type”:“uint256”}],“type”:“function”},
{“inputs”:[{“name”:“owner”,“type”:“address”},{“name”:“index”,“type”:“uint256”}],“name”:“tokenOfOwnerByIndex”,“outputs”:[{“name”:””,“type”:“uint256”}],“type”:“function”},
{“inputs”:[{“name”:“tokenId”,“type”:“uint256”}],“name”:“positions”,“outputs”:[{“name”:“nonce”,“type”:“uint96”},{“name”:“operator”,“type”:“address”},{“name”:“token0”,“type”:“address”},{“name”:“token1”,“type”:“address”},{“name”:“fee”,“type”:“uint24”},{“name”:“tickLower”,“type”:“int24”},{“name”:“tickUpper”,“type”:“int24”},{“name”:“liquidity”,“type”:“uint128”},{“name”:“feeGrowthInside0LastX128”,“type”:“uint256”},{“name”:“feeGrowthInside1LastX128”,“type”:“uint256”},{“name”:“tokensOwed0”,“type”:“uint128”},{“name”:“tokensOwed1”,“type”:“uint128”}],“type”:“function”},
]

ABI_TOKEN = [
{“inputs”:[],“name”:“symbol”,“outputs”:[{“name”:””,“type”:“string”}],“type”:“function”},
{“inputs”:[],“name”:“decimals”,“outputs”:[{“name”:””,“type”:“uint8”}],“type”:“function”},
]

ABI_POOL = [
{“inputs”:[],“name”:“slot0”,“outputs”:[{“name”:“sqrtPriceX96”,“type”:“uint160”},{“name”:“tick”,“type”:“int24”},{“name”:“observationIndex”,“type”:“uint16”},{“name”:“observationCardinality”,“type”:“uint16”},{“name”:“observationCardinalityNext”,“type”:“uint16”},{“name”:“feeProtocol”,“type”:“uint8”},{“name”:“unlocked”,“type”:“bool”}],“type”:“function”},
{“inputs”:[],“name”:“feeGrowthGlobal0X128”,“outputs”:[{“name”:””,“type”:“uint256”}],“type”:“function”},
{“inputs”:[],“name”:“feeGrowthGlobal1X128”,“outputs”:[{“name”:””,“type”:“uint256”}],“type”:“function”},
{“inputs”:[{“name”:“tickLower”,“type”:“int24”},{“name”:“tickUpper”,“type”:“int24”}],“name”:“ticks”,“outputs”:[{“name”:“liquidityGross”,“type”:“uint128”},{“name”:“liquidityNet”,“type”:“int128”},{“name”:“feeGrowthOutside0X128”,“type”:“uint256”},{“name”:“feeGrowthOutside1X128”,“type”:“uint256”}],“type”:“function”},
]

ABI_FACTORY = [
{“inputs”:[{“name”:“t0”,“type”:“address”},{“name”:“t1”,“type”:“address”},{“name”:“fee”,“type”:“uint24”}],“name”:“getPool”,“outputs”:[{“name”:””,“type”:“address”}],“type”:“function”},
]

# — 3. МАТЕМАТИКА —

def tick_to_price(tick, d0, d1):
return (1.0001 ** tick) * (10 ** (d0 - d1))

def get_amounts(liquidity, cur_tick, tick_low, tick_high, d0, d1):
if liquidity == 0:
return 0, 0
sqrtP = 1.0001 ** (cur_tick / 2)
sqrtA = 1.0001 ** (tick_low / 2)
sqrtB = 1.0001 ** (tick_high / 2)

```
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
```

def calculate_fees_earned(pool_contract, position_data, decimals0, decimals1):
try:
fee_growth_global_0 = pool_contract.functions.feeGrowthGlobal0X128().call()
fee_growth_global_1 = pool_contract.functions.feeGrowthGlobal1X128().call()

```
    tick_lower = position_data[5]
    tick_upper = position_data[6]
    liquidity = position_data[7]
    fee_growth_inside_0_last = position_data[8]
    fee_growth_inside_1_last = position_data[9]
    
    try:
        tick_lower_data = pool_contract.functions.ticks(tick_lower).call()
        tick_upper_data = pool_contract.functions.ticks(tick_upper).call()
        
        fee_growth_below_0 = tick_lower_data[2]
        fee_growth_below_1 = tick_lower_data[3]
        fee_growth_above_0 = tick_upper_data[2]
        fee_growth_above_1 = tick_upper_data[3]
    except:
        fee_growth_below_0 = 0
        fee_growth_below_1 = 0
        fee_growth_above_0 = 0
        fee_growth_above_1 = 0
    
    current_tick = pool_contract.functions.slot0().call()[1]
    
    if current_tick < tick_lower:
        fee_growth_inside_0 = fee_growth_below_0 - fee_growth_above_0
        fee_growth_inside_1 = fee_growth_below_1 - fee_growth_above_1
    elif current_tick < tick_upper:
        fee_growth_inside_0 = fee_growth_global_0 - fee_growth_below_0 - fee_growth_above_0
        fee_growth_inside_1 = fee_growth_global_1 - fee_growth_below_1 - fee_growth_above_1
    else:
        fee_growth_inside_0 = fee_growth_above_0 - fee_growth_below_0
        fee_growth_inside_1 = fee_growth_above_1 - fee_growth_below_1
    
    fee_growth_inside_0 = fee_growth_inside_0 % (2**256)
    fee_growth_inside_1 = fee_growth_inside_1 % (2**256)
    
    fees_0_delta = fee_growth_inside_0 - fee_growth_inside_0_last
    fees_1_delta = fee_growth_inside_1 - fee_growth_inside_1_last
    
    if fees_0_delta < 0:
        fees_0_delta += 2**256
    if fees_1_delta < 0:
        fees_1_delta += 2**256
    
    Q128 = 2**128
    fees_0 = (liquidity * fees_0_delta) // Q128
    fees_1 = (liquidity * fees_1_delta) // Q128
    
    fees_0 += position_data[10]
    fees_1 += position_data[11]
    
    return fees_0 / (10**decimals0), fees_1 / (10**decimals1)

except Exception as e:
    return position_data[10] / (10**decimals0), position_data[11] / (10**decimals1)
```

# — 4. ИНТЕРФЕЙС —

st.title(“Architect DeFi Pro Dashboard”)
st.markdown(”### Управление ликвидностью Uniswap V3”)

st.sidebar.header(“Параметры”)
wallet = st.sidebar.text_input(“Адрес кошелька”, “0x995907fe97C9CAd3D310c4F384453E8676F4a170”)
btn = st.sidebar.button(“Обновить данные”, type=“primary”)

if btn and wallet:
with st.spinner(‘Загрузка данных…’):
try:
addr = w3.to_checksum_address(wallet)
nft_contract = w3.eth.contract(address=NFT_MANAGER, abi=ABI_NFT)
factory = w3.eth.contract(address=FACTORY_ADDR, abi=ABI_FACTORY)

```
        try:
            r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd", timeout=5).json()
            p_eth = r['ethereum']['usd']
        except:
            p_eth = 2750.0
        
        count = nft_contract.functions.balanceOf(addr).call()
        
        if count == 0:
            st.info("Позиции не найдены для данного кошелька")
        else:
            st.success(f"Найдено активных позиций: **{count}**")
            
            total_value = 0
            total_fees = 0
            
            for i in range(count):
                tid = nft_contract.functions.tokenOfOwnerByIndex(addr, i).call()
                pos = nft_contract.functions.positions(tid).call()
                
                if pos[7] == 0:
                    continue
                
                token0_contract = w3.eth.contract(address=pos[2], abi=ABI_TOKEN)
                token1_contract = w3.eth.contract(address=pos[3], abi=ABI_TOKEN)
                
                s0 = token0_contract.functions.symbol().call()
                s1 = token1_contract.functions.symbol().call()
                d0 = token0_contract.functions.decimals().call()
                d1 = token1_contract.functions.decimals().call()
                
                pool_addr = factory.functions.getPool(pos[2], pos[3], pos[4]).call()
                pool_contract = w3.eth.contract(address=pool_addr, abi=ABI_POOL)
                slot0 = pool_contract.functions.slot0().call()
                cur_tick = slot0[1]
                
                is_inverted = (s0 in ["USDC", "USDT", "DAI"])
                
                p_min_raw = tick_to_price(pos[5], d0, d1)
                p_max_raw = tick_to_price(pos[6], d0, d1)
                p_now_raw = tick_to_price(cur_tick, d0, d1)

                if is_inverted:
                    p_min, p_max, p_now = 1/p_max_raw, 1/p_min_raw, 1/p_now_raw
                    display_pair = f"{s1}/{s0}"
                else:
                    p_min, p_max, p_now = p_min_raw, p_max_raw, p_now_raw
                    display_pair = f"{s0}/{s1}"
                
                a0, a1 = get_amounts(pos[7], cur_tick, pos[5], pos[6], d0, d1)
                f0, f1 = calculate_fees_earned(pool_contract, pos, d0, d1)
                
                if s1 in ["USDC", "USDT", "DAI"]:
                    position_usd = (a0 * p_eth) + a1
                    fees_usd = (f0 * p_eth) + f1
                elif s0 in ["USDC", "USDT", "DAI"]:
                    position_usd = a0 + (a1 * p_eth)
                    fees_usd = f0 + (f1 * p_eth)
                else:
                    position_usd = (a0 * p_eth) + (a1 * p_eth)
                    fees_usd = (f0 * p_eth) + (f1 * p_eth)
                
                total_value += position_usd
                total_fees += fees_usd
                
                p_range = pos[6] - pos[5]
                p_pos = ((cur_tick - pos[5]) / p_range * 100) if p_range != 0 else 50
                p_pos = max(0, min(100, p_pos))
                in_range = pos[5] <= cur_tick <= pos[6]

                st.markdown(f"""
                <div class="metric-card">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                        <h3>NFT #{tid}: {display_pair}</h3>
                        <span class="status-badge {'status-active' if in_range else 'status-inactive'}">
                            {'АКТИВНА' if in_range else 'НЕАКТИВНА'}
                        </span>
                    </div>
                    
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 20px;">
                        <div class="stat-box">
                            <div class="stat-label">Депозит</div>
                            <div class="stat-value">${position_usd:,.2f}</div>
                            <div class="stat-details">
                                {a0:.6f} {s0}<br>
                                {a1:.6f} {s1}
                            </div>
                        </div>
                        
                        <div class="stat-box">
                            <div class="stat-label">Ценовой диапазон</div>
                            <div class="stat-value">{p_min:,.2f} - {p_max:,.2f}</div>
                            <div class="stat-details">
                                Текущая цена: <strong>{p_now:,.2f}</strong>
                            </div>
                        </div>
                    </div>
                    
                    <div class="fees-highlight">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <div style="font-size: 0.9em; opacity: 0.9;">Несобранные комиссии</div>
                                <div style="font-size: 2em; font-weight: bold; margin-top: 5px;">
                                    ${fees_usd:,.4f}
                                </div>
                            </div>
                            <div style="text-align: right; font-size: 0.95em;">
                                <div>{f0:.8f} {s0}</div>
                                <div>{f1:.8f} {s1}</div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="range-bar-bg">
                        <div class="range-fill"></div>
                        <div class="price-pointer" style="left: {p_pos}%;"></div>
                    </div>
                    
                    <div class="range-labels">
                        <span>Мин: {p_min:,.1f}</span>
                        <span style="color: #fbbf24;">Сейчас: {p_now:,.1f}</span>
                        <span>Макс: {p_max:,.1f}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("---")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Общая стоимость позиций", f"${total_value:,.2f}")
            with col2:
                st.metric("Всего несобранных комиссий", f"${total_fees:,.4f}")
            with col3:
                roi = (total_fees / total_value * 100) if total_value > 0 else 0
                st.metric("ROI от комиссий", f"{roi:.3f}%")

    except Exception as e:
        st.error(f"Произошла ошибка: {e}")
        st.exception(e)
```

else:
st.info(“Введите адрес кошелька и нажмите ‘Обновить данные’”)
