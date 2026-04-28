# ⚡ FlowVolt - P2P Decentralized Energy Marketplace

FlowVolt is a full-stack decentralized application (dApp) that enables peer-to-peer renewable energy trading using blockchain technology (Ethereum/Sepolia).

## 🚀 Quick Start Guide

Follow these steps in order to get the full system running.

### 1. Smart Contract Deployment (Blockchain)
1. Open [Remix IDE](https://remix.ethereum.org/).
2. Create a new file named `EnergyMarket.sol` and paste the contract code from this project.
3. Compile the contract using version `0.8.20`.
4. Deploy to **Sepolia Test Network** using MetaMask (Injected Provider).
5. **Copy the Deployed Contract Address.** You will need this for the next steps.

---

### 2. Backend Server Setup (Node.js)
The backend handles user registration, authentication, and email OTP verification.

1. Open a terminal in the project root.
2. Install dependencies:
   ```powershell
   npm install
   ```
3. Create or update the `.env` file with your credentials:
   ```env
   PORT=5000
   EMAIL_USER=your-gmail@gmail.com
   EMAIL_PASS=your-google-app-password
   ```
4. Start the server:
   ```powershell
   npm run dev
   ```
   The backend and dashboard will be available at `http://localhost:5000`.

---

### 3. IoT Energy Simulation (Python)
The simulation script acts as an IoT device generating energy and an Oracle bridging data to the blockchain.

1. Install Python dependencies:
   ```powershell
   pip install web3 python-dotenv
   ```
2. Configure the simulation `.env` (optional but recommended for auto-minting):
   * Set your `ORACLE_PRIVATE_KEY` and the `CONTRACT_ADDRESS`.
3. Run the simulation:
   ```powershell
   python energy_sim.py
   ```

---

### 4. Using the Dashboard
1. Open your browser to [http://localhost:5000/](http://localhost:5000/).
2. **Register/Login:** Use your email to enter the grid.
3. **Connect MetaMask:** Click the "Connect Wallet" button in the sidebar.
4. **Configure Contract:** 
   * Go to the **Wallet** tab.
   * Paste your **Contract Address** from Step 1 into the "Active Contract Address" field.
5. **Trade:** You can now "Sync" energy from the dashboard or "Buy/List" energy in the Marketplace.

---

## 🛠 Tech Stack
- **Frontend:** React (via CDN), Ethers.js v6, Vanilla CSS.
- **Backend:** Node.js, Express, Nodemailer.
- **Blockchain:** Solidity, Sepolia Testnet.
- **Simulation:** Python, Web3.py.

## 📄 License
MIT License - FlowVolt Open Source Project
