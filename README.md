# FlowVolt — Decentralized P2P Energy Marketplace

FlowVolt is a platform for trading renewable energy credits directly between prosumers and consumers using blockchain technology.

## What's Included

1. **FlowVolt_Dashboard.html** (in `frontend/index.html`) — Full React Frontend
   - Open directly in browser, zero setup needed.
   - Includes: Dashboard, Marketplace, Wallet, Analytics, and Audit Log.
   - Works immediately with mock data.

2. **EnergyMarket.sol** — Smart Contract
   - Ledger Logic: `mintEnergyTokens`, `balanceOf`.
   - Trading Engine: `listEnergy`, `buyEnergy`, `cancelListing`.
   - Double-Spend Prevention & Escrow logic.
   - Audit Logging via events.

3. **energy_sim.py** — Python Oracle + Simulation
   - Simulates solar/wind generation and residential consumption.
   - Battery state-of-charge tracking.
   - Oracle bridge to mint tokens on-chain when surplus accumulates.
   - Dry-run mode available for testing without a blockchain connection.

## 🚀 3-Step Deployment

1. **Frontend**: Open `frontend/index.html` in your browser.
2. **Contract**: Deploy `EnergyMarket.sol` on Remix IDE (recommended: Sepolia Testnet). Copy the deployed contract address.
3. **Simulation**: 
   - Install dependencies: `pip install web3 python-dotenv`
   - Create a `.env` file with your `RPC_URL`, `ORACLE_PRIVATE_KEY`, and `CONTRACT_ADDRESS`.
   - Run the simulation: `python energy_sim.py`
