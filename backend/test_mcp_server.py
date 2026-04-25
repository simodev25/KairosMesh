"""
Mini MCP server for testing external MCP integration.
Run with: python3 test_mcp_server.py
Exposes a streamable-HTTP endpoint at http://localhost:8001/mcp
"""
from fastmcp import FastMCP

mcp = FastMCP("Test Finance MCP")


@mcp.tool()
def get_earnings(symbol: str, quarters: int = 4) -> dict:
    """Fetch earnings data for a stock symbol.

    Args:
        symbol: The stock ticker symbol (e.g. AAPL, MSFT)
        quarters: Number of quarters to return (default 4)

    Returns:
        Dict with earnings per quarter
    """
    # Fake data for testing
    return {
        "symbol": symbol.upper(),
        "quarters": [
            {"quarter": f"Q{i+1}", "eps": round(1.5 + i * 0.2, 2), "beat": True}
            for i in range(quarters)
        ],
        "source": "test-mcp-server",
    }


@mcp.tool()
def get_analyst_rating(symbol: str) -> dict:
    """Get analyst consensus rating for a stock.

    Args:
        symbol: The stock ticker symbol

    Returns:
        Dict with rating and price target
    """
    return {
        "symbol": symbol.upper(),
        "rating": "BUY",
        "consensus_score": 4.2,
        "price_target": 195.0,
        "analysts": 18,
        "source": "test-mcp-server",
    }


@mcp.tool()
def get_insider_transactions(symbol: str, days: int = 30) -> dict:
    """Get recent insider transactions for a stock.

    Args:
        symbol: The stock ticker symbol
        days: Lookback period in days (default 30)

    Returns:
        Dict with list of insider transactions
    """
    return {
        "symbol": symbol.upper(),
        "transactions": [
            {"name": "John CEO", "type": "BUY", "shares": 5000, "price": 182.5},
            {"name": "Jane CFO", "type": "SELL", "shares": 2000, "price": 185.0},
        ],
        "days": days,
        "source": "test-mcp-server",
    }


if __name__ == "__main__":
    print("Starting Test Finance MCP server on http://localhost:8001/mcp")
    print("Tools available: get_earnings, get_analyst_rating, get_insider_transactions")
    print("Press Ctrl+C to stop")
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8001, path="/mcp")
