const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

class ApiClient {
  private token: string | null = null;

  setToken(token: string | null) {
    this.token = token;
    if (token) {
      localStorage.setItem("token", token);
    } else {
      localStorage.removeItem("token");
    }
  }

  getToken(): string | null {
    if (!this.token && typeof window !== "undefined") {
      this.token = localStorage.getItem("token");
    }
    return this.token;
  }

  private async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...((options.headers as Record<string, string>) || {}),
    };

    const token = this.getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.error || `Request failed: ${res.status}`);
    }

    return res.json();
  }

  // Auth
  getMe() {
    return this.request<{ id: string; email: string; username: string }>("/api/auth/me");
  }

  updateUsername(username: string) {
    return this.request<{ username: string }>("/api/auth/me", {
      method: "PATCH",
      body: JSON.stringify({ username }),
    });
  }

  // Players
  getPlayers() {
    return this.request<{ players: any[] }>("/api/players");
  }

  getPlayer(id: number, range?: "all" | "season" | "month" | "week" | "day") {
    const params = range ? `?range=${range}` : "";
    return this.request<{ player: any; prices: any[] }>(`/api/players/${id}${params}`);
  }

  // Trading
  placeOrder(playerSeasonId: number, side: "buy" | "sell", quantity: number) {
    return this.request<{ trade: any }>("/api/orders", {
      method: "POST",
      body: JSON.stringify({
        player_season_id: playerSeasonId,
        side,
        quantity,
      }),
    });
  }

  placeIndexOrder(indexId: number, side: "buy" | "sell", quantity: number) {
    return this.request<{ trade: any }>("/api/orders", {
      method: "POST",
      body: JSON.stringify({
        index_id: indexId,
        side,
        quantity,
      }),
    });
  }

  // Portfolio
  getPortfolio() {
    return this.request<any>("/api/portfolio");
  }

  getOrders() {
    return this.request<{ orders: any[] }>("/api/orders");
  }

  getTrades() {
    return this.request<{ trades: any[] }>("/api/trades");
  }

  // Indexes
  getIndexes() {
    return this.request<{ indexes: any[] }>("/api/indexes");
  }

  getIndex(id: number, range?: "all" | "season" | "month" | "week" | "day") {
    const params = range ? `?range=${range}` : "";
    return this.request<{ index: any; constituents: any[]; history: any[] }>(
      `/api/indexes/${id}${params}`
    );
  }

  // Leaderboard
  getLeaderboard() {
    return this.request<{ entries: any[] }>("/api/leaderboard");
  }
}

export const api = new ApiClient();
