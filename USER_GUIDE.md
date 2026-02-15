# CRPA User Guide
**Crypto Risk Portfolio Analyzer**

## Getting Started

### Access the App
Visit: `https://YOUR-APP-NAME.onrender.com`

**Note:** First load may take 30-60 seconds (the app wakes up from sleep mode)

### Create an Account
1. Click **"Register"** in the top-right
2. Enter your email and password
3. Click "Register"
4. You'll be redirected to login
5. Login with your credentials

## Using the App

### 1. Create Your First Portfolio

After logging in:
1. Click **"Portfolio"** tab in navigation
2. Click **"Create New Portfolio"** button
3. Enter a name (e.g., "My Crypto Portfolio")
4. Click "Create Portfolio"

### 2. Add Cryptocurrency Holdings

1. In the **Portfolio** tab, find your portfolio
2. Click **"Add Holding"** button
3. Select a cryptocurrency from the dropdown
4. Enter the amount you own
5. Click "Add"
6. Repeat for all your holdings

**Supported Cryptocurrencies:**
- Bitcoin (BTC)
- Ethereum (ETH)
- Cardano (ADA)
- Solana (SOL)
- Polkadot (DOT)
- And many more...

### 3. View Dashboard Analytics

Click **"Dashboard"** tab to see:

**Portfolio Overview:**
- Total value in USD
- Current prices of your holdings
- Portfolio allocation (pie chart)
- Sector breakdown

**Risk Metrics:**
- **Volatility:** How much your portfolio value fluctuates (lower is more stable)
- **Sharpe Ratio:** Risk-adjusted returns (higher is better)
- **Beta vs BTC:** How your portfolio moves relative to Bitcoin
  - Beta < 1: Less volatile than BTC
  - Beta = 1: Moves with BTC
  - Beta > 1: More volatile than BTC

**Performance Chart:**
- Interactive price chart with multiple timeframes:
  - 7D (7 days)
  - 30D (30 days)
  - 90D (90 days)
- Indexed to 100 for easy comparison
- Hover to see exact values
- Shows your portfolio vs individual assets

### 4. Portfolio Analysis

In the **Portfolio** tab:
- View detailed breakdown of each holding
- See current prices and values
- Adjust weights (what percentage of portfolio each asset should be)
- Click **"Analyze"** to see risk metrics for this specific portfolio

### 5. Historical Tracking

Click **"History"** tab to:
- View past portfolio snapshots
- Track how your portfolio has changed over time
- See historical performance

### 6. Generate Reports

Click **"Reports"** tab to:
- Generate PDF reports of your portfolio
- Download detailed analytics
- Share portfolio performance

## Tips & Tricks

### Dark Mode
- Click the **moon icon** (🌙) in the header to toggle dark mode
- Your preference is saved automatically
- Great for nighttime browsing

### Multiple Portfolios
- You can create multiple portfolios to:
  - Compare different strategies
  - Track separate investment accounts
  - Test "what-if" scenarios

### Understanding Metrics

**Volatility:**
- Low (< 20%): Stable, conservative portfolio
- Medium (20-40%): Moderate risk
- High (> 40%): High risk, high potential reward

**Sharpe Ratio:**
- < 1: Poor risk-adjusted returns
- 1-2: Good returns for the risk
- > 2: Excellent risk-adjusted returns

**Beta vs BTC:**
- Useful to understand if your portfolio is more or less risky than Bitcoin
- Diversification can lower beta (reduce correlation with BTC)

### Rebalancing
- Use the weight adjustment feature to rebalance your portfolio
- The app shows you how many coins to buy/sell to reach target weights

## Troubleshooting

### App is slow to load
- This is normal on first access (cold start)
- The app "wakes up" from sleep mode
- Subsequent loads are much faster
- Usually takes 30-60 seconds max

### Charts not showing
- Wait a moment for data to load from CoinGecko API
- Refresh the page if data doesn't appear after 10 seconds
- Check your internet connection

### Can't find a cryptocurrency
- Not all cryptocurrencies are available
- The app uses top cryptocurrencies by market cap
- Contact the admin if you need a specific coin added

### Forgot password
- Contact the admin to reset your password
- Future versions will have self-service password reset

## Privacy & Security

- Your portfolio data is private and only visible to you
- Passwords are securely hashed (bcrypt)
- Connection is encrypted (HTTPS)
- No cryptocurrency is actually stored or transacted - this is a **tracking tool only**
- The app only tracks amounts and calculates metrics

## Support

If you encounter issues:
1. Try refreshing the page
2. Clear browser cache and cookies
3. Try a different browser
4. Contact the app administrator

## Keyboard Shortcuts

- **Shift + D** - Toggle dark mode (same as moon icon)
- **Tab** - Navigate between form fields
- **Enter** - Submit forms

## Best Practices

1. **Keep holdings updated** - Update amounts when you buy/sell
2. **Check regularly** - Monitor risk metrics weekly
3. **Diversify** - Don't put all holdings in one coin
4. **Understand metrics** - Learn what volatility and Sharpe ratio mean
5. **Use multiple timeframes** - Check 7D, 30D, and 90D charts for different perspectives

## FAQ

**Q: Does this app actually trade cryptocurrency?**
A: No, this is a tracking and analysis tool only. It doesn't connect to exchanges or execute trades.

**Q: Is my data safe?**
A: Yes, data is stored securely and only you can access your portfolios.

**Q: Can I export my data?**
A: Yes, use the Reports tab to generate PDF reports.

**Q: How often do prices update?**
A: Prices are fetched from CoinGecko API and update when you load the page. Free tier has rate limits.

**Q: Can I delete a portfolio?**
A: Yes, in the Portfolio tab, select a portfolio and click the delete option.

**Q: What if I make a mistake entering amounts?**
A: You can edit or delete holdings at any time in the Portfolio tab.

**Q: Why is my beta value "N/A"?**
A: Beta requires at least 30 days of price history. New portfolios or coins may not have enough data yet.

---

**Version:** 1.0
**Last Updated:** 2026
**Questions?** Contact your app administrator
