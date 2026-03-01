export interface Player {
  id: number;
  externalId: string;
  firstName: string;
  lastName: string;
  position: string;
  teamName: string;
  teamAbbreviation: string;
}

export interface PlayerSeason {
  id: number;
  playerId: number;
  seasonId: number;
  teamId: number;
  tier: "superstar" | "starter" | "rotation" | "bench";
  floatShares: number;
  status: "ipo" | "active" | "injured_out" | "delisting" | "delisted";
  player: Player;
}

export interface PricePoint {
  tradeDate: string;
  price: number;
  changePct: number | null;
  marketCap: number;
  perfScore: number;
  ageMult: number;
  winPctMult: number;
  salaryEffMult: number;
}

export interface PlayerWithPrice extends PlayerSeason {
  currentPrice: number;
  prevPrice: number | null;
  changePct: number | null;
  marketCap: number;
}

export interface Position {
  playerSeasonId: number;
  player: Player;
  quantity: number;
  avgCost: number;
  currentPrice: number;
  marketValue: number;
  unrealizedPnl: number;
  unrealizedPnlPct: number;
}

export interface Portfolio {
  cashBalance: number;
  positions: Position[];
  totalPositionValue: number;
  totalValue: number;
}

export interface Order {
  id: string;
  playerSeasonId: number;
  player: Player;
  side: "buy" | "sell";
  quantity: number;
  price: number;
  total: number;
  status: "pending" | "filled" | "rejected" | "cancelled";
  createdAt: string;
}

export interface Trade {
  id: string;
  playerSeasonId: number;
  player: Player;
  side: "buy" | "sell";
  quantity: number;
  price: number;
  total: number;
  executedAt: string;
}

export interface StockIndex {
  id: number;
  name: string;
  indexType: "league" | "team" | "position" | "momentum";
  description: string;
  teamId: number | null;
}

export interface IndexLevel {
  tradeDate: string;
  level: number;
  changePct: number | null;
}

export interface IndexConstituent {
  playerSeasonId: number;
  player: Player;
  weight: number;
  price: number;
}

export interface LeaderboardEntry {
  userId: string;
  username: string;
  totalValue: number;
  portfolioValue: number;
  cashBalance: number;
  rank: number;
}

export interface AuthResponse {
  token: string;
  user: {
    id: string;
    email: string;
    username: string;
  };
}

export interface MarketStatus {
  isOpen: boolean;
  nextOpen: string | null;
  nextClose: string | null;
}
