"""
FlowVolt Energy Simulation & Oracle Bridge
==========================================
Simulates IoT smart meter data and mints EnergyMarket tokens via oracle.

Usage:
    pip install web3 python-dotenv
    python energy_sim.py

Environment (.env):
    RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/YOUR_KEY
    ORACLE_PRIVATE_KEY=0x...
    CONTRACT_ADDRESS=0x...
"""

import os
import time
import math
import random
import logging
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional

try:
    from web3 import Web3
    from eth_account import Account
    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False
    print("[WARN] web3 not installed — running in simulation-only mode")

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("FlowVolt")

CONTRACT_ABI = [
    {
        "inputs": [
            {"name": "prosumer", "type": "address"},
            {"name": "amount",   "type": "uint256"},
            {"name": "source",   "type": "string"}
        ],
        "name": "mintEnergyTokens",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]

@dataclass
class EnergyReading:
    timestamp:        str
    hour:             int
    solar_generation: float
    wind_generation:  float
    consumption:      float
    surplus:          float
    battery_soc:      float
    irradiance:       float

    def to_dict(self):
        return asdict(self)


class SolarSimulator:
    """
    Simulates a residential solar prosumer node.
    Solar output follows a bell-curve peaking at solar noon (~13:00).
    Consumption follows real residential patterns (morning & evening peaks).
    """
    PANEL_CAPACITY_KW  = 5.0
    BATTERY_CAPACITY_KWH = 10.0
    SAMPLING_INTERVAL_S  = 30

    def __init__(self, node_id: str, prosumer_address: str):
        self.node_id = node_id
        self.prosumer_address = prosumer_address
        self.battery_soc = 50.0
        self.accumulated_kwh = 0.0
        self.mint_threshold  = 1.0
        self.total_minted    = 0

    def _solar_irradiance(self, hour: float) -> float:
        if hour < 6 or hour > 20:
            return 0.0
        sigma = 3.5
        mu    = 13.0
        base  = 900 * math.exp(-0.5 * ((hour - mu) / sigma) ** 2)
        noise = random.uniform(0.85, 1.05)
        return round(max(0, base * noise), 1)

    def _wind_generation(self, hour: float) -> float:
        base_wind = 0.3 + 0.2 * math.sin(hour * 0.5)
        gust      = random.uniform(0, 0.5) if random.random() > 0.7 else 0
        return round(max(0, base_wind + gust), 3)

    def _consumption(self, hour: float) -> float:
        if 7 <= hour < 9:
            base = 1.8 + random.uniform(-0.3, 0.3)
        elif 18 <= hour < 22:
            base = 2.5 + random.uniform(-0.5, 0.5)
        elif 23 <= hour or hour < 6:
            base = 0.4 + random.uniform(-0.1, 0.1)
        else:
            base = 0.9 + random.uniform(-0.2, 0.2)
        return round(max(0.1, base), 3)

    def read(self, hour: Optional[float] = None) -> EnergyReading:
        if hour is None:
            hour = datetime.now().hour + datetime.now().minute / 60.0

        irradiance  = self._solar_irradiance(hour)
        solar_gen   = round((irradiance / 1000) * self.PANEL_CAPACITY_KW, 3)
        wind_gen    = self._wind_generation(hour)
        total_gen   = solar_gen + wind_gen
        consumption = self._consumption(hour)
        surplus     = round(max(0, total_gen - consumption), 3)

        if surplus > 0:
            charge = min(surplus * 0.8,
                         (self.BATTERY_CAPACITY_KWH - self.battery_soc / 100 * self.BATTERY_CAPACITY_KWH))
            self.battery_soc = min(100, self.battery_soc + (charge / self.BATTERY_CAPACITY_KWH) * 100)
        else:
            deficit   = abs(total_gen - consumption)
            discharge = min(deficit, self.battery_soc / 100 * self.BATTERY_CAPACITY_KWH)
            self.battery_soc = max(0, self.battery_soc - (discharge / self.BATTERY_CAPACITY_KWH) * 100)

        self.accumulated_kwh += surplus

        return EnergyReading(
            timestamp        = datetime.now().isoformat(),
            hour             = int(hour),
            solar_generation = solar_gen,
            wind_generation  = wind_gen,
            consumption      = consumption,
            surplus          = surplus,
            battery_soc      = round(self.battery_soc, 1),
            irradiance       = irradiance
        )

    def check_mint_threshold(self) -> int:
        tokens = int(self.accumulated_kwh // self.mint_threshold)
        if tokens > 0:
            self.accumulated_kwh -= tokens * self.mint_threshold
            self.total_minted += tokens
        return tokens


class OracleBridge:
    def __init__(self):
        self.enabled = WEB3_AVAILABLE and os.getenv("RPC_URL")
        if self.enabled:
            self.w3       = Web3(Web3.HTTPProvider(os.getenv("RPC_URL")))
            self.account  = Account.from_key(os.getenv("ORACLE_PRIVATE_KEY"))
            self.contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(os.getenv("CONTRACT_ADDRESS")),
                abi=CONTRACT_ABI
            )
            log.info(f"Oracle connected | Chain ID: {self.w3.eth.chain_id}")
        else:
            log.warning("Oracle running in DRY-RUN mode")

    def mint(self, prosumer_address: str, amount: int, source: str = "solar"):
        if not self.enabled:
            log.info(f"[DRY-RUN] Would mint {amount} FVE to {prosumer_address}")
            return "0xDRYRUN"
        try:
            tx = self.contract.functions.mintEnergyTokens(
                Web3.to_checksum_address(prosumer_address), amount, source
            ).build_transaction({
                "from":     self.account.address,
                "nonce":    self.w3.eth.get_transaction_count(self.account.address),
                "gas":      100_000,
                "gasPrice": self.w3.eth.gas_price,
            })
            signed  = self.account.sign_transaction(tx, private_key=self.account.key)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
            log.info(f"Minted {amount} FVE to {prosumer_address} | TX: {tx_hash.hex()[:20]}...")
            return tx_hash.hex()
        except Exception as e:
            log.error(f"Mint failed: {e}")
            return None


def run_simulation(nodes, oracle, cycles=0):
    log.info(f"Starting FlowVolt simulation | Nodes: {len(nodes)}")
    reading_count = 0
    try:
        while True:
            for node in nodes:
                reading = node.read()
                reading_count += 1
                print(
                    f"[{node.node_id}] {reading.timestamp[11:19]} | "
                    f"Solar: {reading.solar_generation:.2f} kWh | "
                    f"Wind: {reading.wind_generation:.2f} kWh | "
                    f"Consumed: {reading.consumption:.2f} kWh | "
                    f"Surplus: {reading.surplus:.2f} kWh | "
                    f"Battery: {reading.battery_soc:.0f}%"
                )
                tokens = node.check_mint_threshold()
                if tokens > 0:
                    source = "solar" if reading.solar_generation > reading.wind_generation else "wind"
                    oracle.mint(node.prosumer_address, tokens, source)

            if cycles and reading_count >= cycles * len(nodes):
                break
            time.sleep(SolarSimulator.SAMPLING_INTERVAL_S)
    except KeyboardInterrupt:
        print("\nSimulation stopped.")


if __name__ == "__main__":
    nodes = [
        SolarSimulator("Node-A (Rooftop Solar)", "0x8002b019B8F4329799C0b33eEaee861004a4F017"),
        SolarSimulator("Node-B (Balcony Array)", "0x8002b019B8F4329799C0b33eEaee861004a4F017"),
    ]
    oracle = OracleBridge()

    # Fast-forward 24h demo
    log.info("Running 24-hour fast-forward simulation...")
    for hour in range(0, 24):
        for node in nodes:
            node.read(hour=float(hour) + random.uniform(0, 0.5))
            tokens = node.check_mint_threshold()
            if tokens > 0:
                oracle.mint(node.prosumer_address, tokens, "solar")
                log.info(f"Hour {hour:02d}:00 -> Minted {tokens} FVE for {node.node_id}")

    for node in nodes:
        print(f"  {node.node_id}: {node.total_minted} tokens minted")
