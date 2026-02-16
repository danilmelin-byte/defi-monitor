import streamlit as st
from web3 import Web3

# --- 1. НАСТРОЙКИ ---
st.set_page_config(page_title="DeFi Architect Pro", layout="wide")
st.title("🦄 Uniswap V3: Продвинутый Монитор")

RPC_URL = "https://arb1.arbitrum.io/rpc"
NFT_MANAGER = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"
w3 = Web3(Web3.HTTPProvider(RPC_URL))

# Расширенный ABI для имен токенов и позиций
ABI = [
    {"inputs":[{"name":"owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"type":"function"},
    {"inputs":[{"name":"owner","type":"address"},{"name":"index","type":"uint256"}],"name":"tokenOfOwnerByIndex","outputs":[{"name":"","type":"uint256"}],"type":"function"},
    {"inputs":[{"name":"tokenId","type":"uint256"}],"name":"positions","outputs":[{"name":"nonce","type":"uint96"},{"name":"operator","type":"address"},{"name":"token0","type":"address"},{"name":"token1","type":"address"},{"name":"fee","type":"uint24"},{"name":"tickLower","type":"int24"},{"name":"tickUpper","type":"int24"},{"name":"liquidity","type":"uint128"},{"name":"feeGrowthInside0LastX128","type":"uint256"},{"name":"feeGrowthInside1LastX128","type":"uint256"},{"name":"tokensOwed0","type":"uint128"},{"name":"tokensOwed1","type":"uint128"}],"type":"function"},
    {"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],"type":"function"}
]

@st.cache_data(ttl=3600)
def get_token_symbol(address):
    """Получает символ токена (например, WETH) по его адресу"""
    try:
        token_contract = w3.eth.contract(address=w3.to_checksum_address(address), abi=ABI)
        return token_contract.functions.symbol().call()
    except:
        return f"{address[:6]}..."

# --- 2. ИНТЕРФЕЙС ---
st.sidebar.header("⚙️ Управление")
target_wallet = st.sidebar.text_input("Адрес кошелька", "")
# ТОТ САМЫЙ ТУМБЛЕР (Radio-кнопка)
status_filter = st.sidebar.radio("Показать позиции:", ["Активные (с ликвидностью)", "Все (включая закрытые)"])
scan_button = st.sidebar.button("🔎 Найти")

if scan_button and target_wallet:
    try:
        addr = w3.to_checksum_address(target_wallet)
        contract = w3.eth.contract(address=NFT_MANAGER, abi=ABI)
        
        with st.spinner("Синхронизация с Arbitrum..."):
            total_count = contract.functions.balanceOf(addr).call()
            
            if total_count == 0:
                st.warning("Позиций не найдено.")
            else:
                display_list = []
                
                # Собираем данные обо всех позициях
                for i in range(total_count):
                    token_id = contract.functions.tokenOfOwnerByIndex(addr, i).call()
                    pos_data = contract.functions.positions(token_id).call()
                    
                    is_active = pos_data[7] > 0 # Ликвидность больше нуля
                    
                    # Фильтруем согласно тумблеру
                    if status_filter == "Активные (с ликвидностью)" and not is_active:
                        continue
                        
                    display_list.append({
                        "id": token_id,
                        "t0_addr": pos_data[2],
                        "t1_addr": pos_data[3],
                        "fee": pos_data[4] / 10000,
                        "liq": pos_data[7],
                        "active": is_active
                    })

                if not display_list:
                    st.info("Нет позиций, подходящих под выбранный фильтр.")
                else:
                    st.subheader(f"📊 Результат: {len(display_list)} поз.")
                    cols = st.columns(3)
                    
                    for idx, item in enumerate(display_list):
                        with cols[idx % 3]:
                            # Динамически получаем имена токенов
                            s0 = get_token_symbol(item["t0_addr"])
                            s1 = get_token_symbol(item["t1_addr"])
                            
                            color = "#e8f5e9" if item["active"] else "#f5f5f5"
                            border = "#4caf50" if item["active"] else "#bdbdbd"
                            
                            st.markdown(f"""
                            <div style="background-color:{color}; padding:15px; border-radius:10px; border-left: 5px solid {border}; margin-bottom:10px">
                                <h4 style="margin:0">NFT #{item['id']}</h4>
                                <p style="margin:5px 0"><b>{s0} / {s1}</b></p>
                                <small>Комиссия: {item['fee']}%</small><br>
                                <small>Ликвидность: {item['liq']}</small>
                            </div>
                            """, unsafe_allow_html=True)
                            
    except Exception as e:
        st.error(f"Ошибка: {e}")

st.markdown("---")
st.caption("Режим: Vibe Coding с телефона. Даниил, ты настраиваешь фильтры как профи!")
