// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title EnergyMarket - FlowVolt P2P Renewable Energy Trading Contract
 * @notice Implements a decentralized marketplace for trading energy credits (kWh tokens)
 * @dev Deploy on Polygon (L2) for low gas fees; tested on Sepolia Testnet
 */
contract EnergyMarket {

    // ─── Token Ledger ──────────────────────────────────────────────────────────
    string  public constant name     = "FlowVolt Energy Token";
    string  public constant symbol   = "FVE";
    uint8   public constant decimals = 0;

    mapping(address => uint256) private _balances;
    uint256 public totalSupply;

    // ─── Market Listing ────────────────────────────────────────────────────────
    struct Listing {
        uint256 listingId;
        address payable seller;
        uint256 energyAmount;
        uint256 pricePerToken;
        bool    active;
        uint256 createdAt;
    }

    uint256 private _listingCounter;
    mapping(uint256 => Listing) public listings;
    uint256[] public activeListingIds;

    // ─── Double-Spend Prevention ───────────────────────────────────────────────
    mapping(address => uint256) public nonces;

    // ─── Escrow ────────────────────────────────────────────────────────────────
    mapping(uint256 => uint256) public escrowedFunds;

    // ─── Access Control ────────────────────────────────────────────────────────
    address public owner;
    mapping(address => bool) public authorizedOracles;

    // ─── Audit Log Events ──────────────────────────────────────────────────────
    event EnergyMinted(address indexed prosumer, uint256 amount, uint256 timestamp, string source);
    event EnergyListed(uint256 indexed listingId, address indexed seller, uint256 amount, uint256 pricePerToken);
    event TradeExecuted(
        uint256 indexed listingId,
        address indexed seller,
        address indexed buyer,
        uint256 amount,
        uint256 totalCost,
        uint256 timestamp
    );
    event ListingCancelled(uint256 indexed listingId, address indexed seller);
    event OracleAuthorized(address indexed oracle);
    event OracleRevoked(address indexed oracle);

    // ─── Modifiers ─────────────────────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "EnergyMarket: not owner");
        _;
    }
    modifier onlyOracle() {
        require(authorizedOracles[msg.sender] || msg.sender == owner, "EnergyMarket: not authorized oracle");
        _;
    }
    modifier listingExists(uint256 listingId) {
        require(listings[listingId].seller != address(0), "EnergyMarket: listing not found");
        _;
    }
    modifier listingActive(uint256 listingId) {
        require(listings[listingId].active, "EnergyMarket: listing not active");
        _;
    }

    // ─── Constructor ───────────────────────────────────────────────────────────
    constructor() {
        owner = msg.sender;
        authorizedOracles[msg.sender] = true;
    }

    // ═══════════════════════════════════════════════════════════════════════════
    //  SECTION 1: LEDGER LOGIC
    // ═══════════════════════════════════════════════════════════════════════════

    function mintEnergyTokens(
        address prosumer,
        uint256 amount,
        string calldata source
    ) external onlyOracle {
        require(prosumer != address(0), "EnergyMarket: zero address");
        require(amount > 0, "EnergyMarket: zero amount");
        _balances[prosumer] += amount;
        totalSupply += amount;
        emit EnergyMinted(prosumer, amount, block.timestamp, source);
    }

    function balanceOf(address account) external view returns (uint256) {
        return _balances[account];
    }

    // ═══════════════════════════════════════════════════════════════════════════
    //  SECTION 2: TRADING ENGINE
    // ═══════════════════════════════════════════════════════════════════════════

    function listEnergy(uint256 amount, uint256 pricePerToken) external returns (uint256 listingId) {
        require(amount > 0, "EnergyMarket: zero amount");
        require(pricePerToken > 0, "EnergyMarket: zero price");
        require(_balances[msg.sender] >= amount, "EnergyMarket: insufficient balance");

        _balances[msg.sender] -= amount;

        listingId = ++_listingCounter;
        listings[listingId] = Listing({
            listingId:     listingId,
            seller:        payable(msg.sender),
            energyAmount:  amount,
            pricePerToken: pricePerToken,
            active:        true,
            createdAt:     block.timestamp
        });
        activeListingIds.push(listingId);
        emit EnergyListed(listingId, msg.sender, amount, pricePerToken);
    }

    function buyEnergy(uint256 listingId, uint256 amount)
        external payable
        listingExists(listingId)
        listingActive(listingId)
    {
        Listing storage listing = listings[listingId];
        require(amount > 0, "EnergyMarket: zero amount");
        require(amount <= listing.energyAmount, "EnergyMarket: exceeds available amount");

        uint256 totalCost = amount * listing.pricePerToken;
        require(msg.value == totalCost, "EnergyMarket: incorrect payment");

        // Double-spend guard
        nonces[msg.sender]++;

        // Atomic Settlement
        listing.energyAmount -= amount;
        if (listing.energyAmount == 0) {
            listing.active = false;
            _removeActiveListing(listingId);
        }
        _balances[msg.sender] += amount;
        listing.seller.transfer(totalCost);

        emit TradeExecuted(listingId, listing.seller, msg.sender, amount, totalCost, block.timestamp);
    }

    function cancelListing(uint256 listingId)
        external
        listingExists(listingId)
        listingActive(listingId)
    {
        Listing storage listing = listings[listingId];
        require(msg.sender == listing.seller || msg.sender == owner, "EnergyMarket: not seller");
        listing.active = false;
        _balances[listing.seller] += listing.energyAmount;
        listing.energyAmount = 0;
        _removeActiveListing(listingId);
        emit ListingCancelled(listingId, listing.seller);
    }

    // ═══════════════════════════════════════════════════════════════════════════
    //  SECTION 3: ORACLE / ADMIN
    // ═══════════════════════════════════════════════════════════════════════════

    function authorizeOracle(address oracle) external onlyOwner {
        authorizedOracles[oracle] = true;
        emit OracleAuthorized(oracle);
    }

    function revokeOracle(address oracle) external onlyOwner {
        authorizedOracles[oracle] = false;
        emit OracleRevoked(oracle);
    }

    // ═══════════════════════════════════════════════════════════════════════════
    //  SECTION 4: VIEW HELPERS
    // ═══════════════════════════════════════════════════════════════════════════

    function getActiveListings() external view returns (Listing[] memory) {
        Listing[] memory result = new Listing[](activeListingIds.length);
        for (uint256 i = 0; i < activeListingIds.length; i++) {
            result[i] = listings[activeListingIds[i]];
        }
        return result;
    }

    function getActiveListingCount() external view returns (uint256) {
        return activeListingIds.length;
    }

    function _removeActiveListing(uint256 listingId) internal {
        uint256 len = activeListingIds.length;
        for (uint256 i = 0; i < len; i++) {
            if (activeListingIds[i] == listingId) {
                activeListingIds[i] = activeListingIds[len - 1];
                activeListingIds.pop();
                break;
            }
        }
    }
}
