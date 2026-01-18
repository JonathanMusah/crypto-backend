from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from tutorials.models import Tutorial

User = get_user_model()


class Command(BaseCommand):
    help = 'Populate database with sample tutorials'

    def handle(self, *args, **options):
        # Get or create admin user for author
        admin_user, _ = User.objects.get_or_create(
            email='admin@cryptoplatform.com',
            defaults={
                'username': 'admin',
                'is_staff': True,
                'is_superuser': True,
            }
        )

        tutorials_data = [
            {
                'title': 'Getting Started with Cryptocurrency',
                'slug': 'getting-started-with-cryptocurrency',
                'content': '''
                    <h2>Welcome to the World of Cryptocurrency!</h2>
                    <p>Cryptocurrency is a digital or virtual currency that uses cryptography for security. Unlike traditional currencies issued by governments, cryptocurrencies operate on decentralized networks based on blockchain technology.</p>
                    
                    <h3>Key Concepts:</h3>
                    <ul>
                        <li><strong>Blockchain:</strong> A distributed ledger that records all transactions across a network of computers.</li>
                        <li><strong>Decentralization:</strong> No central authority controls the currency.</li>
                        <li><strong>Cryptography:</strong> Advanced encryption ensures security and prevents fraud.</li>
                        <li><strong>Digital Wallets:</strong> Software or hardware devices that store your cryptocurrency.</li>
                    </ul>
                    
                    <h3>Why Cryptocurrency?</h3>
                    <p>Cryptocurrencies offer several advantages:</p>
                    <ul>
                        <li>Fast and low-cost transactions</li>
                        <li>Global accessibility</li>
                        <li>Transparency and immutability</li>
                        <li>Financial inclusion for unbanked populations</li>
                    </ul>
                    
                    <p>Ready to start your journey? Continue with the next tutorials to learn about trading, wallets, and security!</p>
                ''',
                'excerpt': 'Learn the fundamentals of cryptocurrency, blockchain technology, and why digital currencies are revolutionizing finance.',
                'category': 'beginner',
                'order': 1,
                'is_published': True,
            },
            {
                'title': 'Understanding Bitcoin and Ethereum',
                'slug': 'understanding-bitcoin-ethereum',
                'content': '''
                    <h2>Bitcoin vs Ethereum: The Two Giants</h2>
                    
                    <h3>Bitcoin (BTC)</h3>
                    <p>Bitcoin, created in 2009, is the first and most valuable cryptocurrency. It's often called "digital gold" because:</p>
                    <ul>
                        <li>Limited supply: Only 21 million bitcoins will ever exist</li>
                        <li>Store of value: Many investors hold Bitcoin as a long-term investment</li>
                        <li>Pioneer status: First successful implementation of blockchain technology</li>
                    </ul>
                    
                    <h3>Ethereum (ETH)</h3>
                    <p>Ethereum, launched in 2015, is more than just a currency. It's a platform for:</p>
                    <ul>
                        <li>Smart contracts: Self-executing contracts with terms written in code</li>
                        <li>Decentralized applications (DApps): Applications running on blockchain</li>
                        <li>DeFi: Decentralized finance applications</li>
                        <li>NFTs: Non-fungible tokens for digital assets</li>
                    </ul>
                    
                    <h3>Key Differences</h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <th style="border: 1px solid #ddd; padding: 8px;">Feature</th>
                            <th style="border: 1px solid #ddd; padding: 8px;">Bitcoin</th>
                            <th style="border: 1px solid #ddd; padding: 8px;">Ethereum</th>
                        </tr>
                        <tr>
                            <td style="border: 1px solid #ddd; padding: 8px;">Primary Use</td>
                            <td style="border: 1px solid #ddd; padding: 8px;">Digital Currency</td>
                            <td style="border: 1px solid #ddd; padding: 8px;">Platform for DApps</td>
                        </tr>
                        <tr>
                            <td style="border: 1px solid #ddd; padding: 8px;">Transaction Speed</td>
                            <td style="border: 1px solid #ddd; padding: 8px;">~10 minutes</td>
                            <td style="border: 1px solid #ddd; padding: 8px;">~15 seconds</td>
                        </tr>
                        <tr>
                            <td style="border: 1px solid #ddd; padding: 8px;">Supply Limit</td>
                            <td style="border: 1px solid #ddd; padding: 8px;">21 million</td>
                            <td style="border: 1px solid #ddd; padding: 8px;">Unlimited</td>
                        </tr>
                    </table>
                ''',
                'excerpt': 'Discover the differences between Bitcoin and Ethereum, the two most popular cryptocurrencies in the market.',
                'category': 'beginner',
                'order': 2,
                'is_published': True,
            },
            {
                'title': 'How to Buy Your First Cryptocurrency',
                'slug': 'buy-first-cryptocurrency',
                'content': '''
                    <h2>Step-by-Step Guide to Buying Cryptocurrency</h2>
                    
                    <h3>Step 1: Choose a Platform</h3>
                    <p>Select a reputable cryptocurrency exchange. Consider:</p>
                    <ul>
                        <li>Security features and reputation</li>
                        <li>Supported cryptocurrencies</li>
                        <li>Fees and transaction costs</li>
                        <li>User interface and ease of use</li>
                        <li>Payment methods accepted</li>
                    </ul>
                    
                    <h3>Step 2: Create an Account</h3>
                    <ol>
                        <li>Sign up with your email address</li>
                        <li>Verify your email</li>
                        <li>Complete KYC (Know Your Customer) verification</li>
                        <li>Set up two-factor authentication (2FA)</li>
                    </ol>
                    
                    <h3>Step 3: Fund Your Account</h3>
                    <p>Deposit funds using:</p>
                    <ul>
                        <li>Bank transfer</li>
                        <li>Credit/debit card</li>
                        <li>Mobile money (in Ghana)</li>
                        <li>Other cryptocurrencies</li>
                    </ul>
                    
                    <h3>Step 4: Place Your Order</h3>
                    <p>Choose between:</p>
                    <ul>
                        <li><strong>Market Order:</strong> Buy immediately at current market price</li>
                        <li><strong>Limit Order:</strong> Set your desired price and wait for execution</li>
                    </ul>
                    
                    <h3>Step 5: Store Your Cryptocurrency</h3>
                    <p>After purchase, transfer your crypto to a secure wallet. Never leave large amounts on exchanges!</p>
                    
                    <div style="background: #f0f9ff; border-left: 4px solid #0ea5e9; padding: 16px; margin: 20px 0;">
                        <strong>💡 Pro Tip:</strong> Start with a small amount to get familiar with the process before making larger investments.
                    </div>
                ''',
                'excerpt': 'A comprehensive guide on how to buy your first cryptocurrency, from choosing a platform to making your first purchase.',
                'category': 'beginner',
                'order': 3,
                'is_published': True,
            },
            {
                'title': 'Cryptocurrency Trading Strategies',
                'slug': 'cryptocurrency-trading-strategies',
                'content': '''
                    <h2>Mastering Cryptocurrency Trading</h2>
                    
                    <h3>1. Day Trading</h3>
                    <p>Buy and sell cryptocurrencies within the same day to profit from short-term price movements.</p>
                    <ul>
                        <li><strong>Pros:</strong> Quick profits, active trading</li>
                        <li><strong>Cons:</strong> High risk, requires constant monitoring</li>
                        <li><strong>Best for:</strong> Experienced traders with time to monitor markets</li>
                    </ul>
                    
                    <h3>2. Swing Trading</h3>
                    <p>Hold positions for several days or weeks to capture medium-term trends.</p>
                    <ul>
                        <li><strong>Pros:</strong> Less time-intensive, captures larger moves</li>
                        <li><strong>Cons:</strong> Requires patience and market analysis</li>
                        <li><strong>Best for:</strong> Traders who can analyze market trends</li>
                    </ul>
                    
                    <h3>3. HODLing (Buy and Hold)</h3>
                    <p>Long-term investment strategy - buy and hold for months or years.</p>
                    <ul>
                        <li><strong>Pros:</strong> Less stressful, historically profitable</li>
                        <li><strong>Cons:</strong> Requires patience, may miss short-term opportunities</li>
                        <li><strong>Best for:</strong> Long-term investors</li>
                    </ul>
                    
                    <h3>4. Dollar-Cost Averaging (DCA)</h3>
                    <p>Invest a fixed amount regularly regardless of price, reducing impact of volatility.</p>
                    
                    <h3>Essential Trading Tools</h3>
                    <ul>
                        <li>Technical analysis charts (candlestick patterns, indicators)</li>
                        <li>Price alerts and notifications</li>
                        <li>Portfolio tracking apps</li>
                        <li>News aggregators for market updates</li>
                    </ul>
                    
                    <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 16px; margin: 20px 0;">
                        <strong>⚠️ Risk Warning:</strong> Cryptocurrency trading involves significant risk. Only invest what you can afford to lose and always do your own research.
                    </div>
                ''',
                'excerpt': 'Learn various trading strategies including day trading, swing trading, HODLing, and dollar-cost averaging.',
                'category': 'trading',
                'order': 1,
                'is_published': True,
            },
            {
                'title': 'Reading Cryptocurrency Charts',
                'slug': 'reading-cryptocurrency-charts',
                'content': '''
                    <h2>Understanding Cryptocurrency Price Charts</h2>
                    
                    <h3>Candlestick Charts</h3>
                    <p>The most popular chart type in cryptocurrency trading. Each candlestick shows:</p>
                    <ul>
                        <li><strong>Open:</strong> Price when the period started</li>
                        <li><strong>Close:</strong> Price when the period ended</li>
                        <li><strong>High:</strong> Highest price during the period</li>
                        <li><strong>Low:</strong> Lowest price during the period</li>
                    </ul>
                    
                    <h3>Common Patterns</h3>
                    <ul>
                        <li><strong>Bullish Engulfing:</strong> Indicates potential upward trend</li>
                        <li><strong>Bearish Engulfing:</strong> Suggests potential downward trend</li>
                        <li><strong>Doji:</strong> Market indecision, potential reversal</li>
                        <li><strong>Hammer:</strong> Potential bullish reversal</li>
                    </ul>
                    
                    <h3>Key Indicators</h3>
                    <ul>
                        <li><strong>Moving Averages (MA):</strong> Smooth out price data to identify trends</li>
                        <li><strong>RSI (Relative Strength Index):</strong> Measures momentum, identifies overbought/oversold conditions</li>
                        <li><strong>MACD:</strong> Shows relationship between two moving averages</li>
                        <li><strong>Bollinger Bands:</strong> Indicate volatility and potential price breakouts</li>
                    </ul>
                    
                    <h3>Support and Resistance Levels</h3>
                    <p>Key price levels where:</p>
                    <ul>
                        <li><strong>Support:</strong> Price tends to bounce back up</li>
                        <li><strong>Resistance:</strong> Price tends to fall back down</li>
                    </ul>
                    
                    <p>Understanding these concepts will help you make better trading decisions!</p>
                ''',
                'excerpt': 'Master the art of reading cryptocurrency charts, understanding candlestick patterns, and using technical indicators.',
                'category': 'trading',
                'order': 2,
                'is_published': True,
            },
            {
                'title': 'Types of Cryptocurrency Wallets',
                'slug': 'types-cryptocurrency-wallets',
                'content': '''
                    <h2>Choosing the Right Wallet for Your Cryptocurrency</h2>
                    
                    <h3>Hot Wallets (Connected to Internet)</h3>
                    <h4>1. Software Wallets</h4>
                    <ul>
                        <li><strong>Desktop Wallets:</strong> Installed on your computer</li>
                        <li><strong>Mobile Wallets:</strong> Apps on your smartphone</li>
                        <li><strong>Web Wallets:</strong> Accessible through browsers</li>
                    </ul>
                    <p><strong>Pros:</strong> Easy to use, convenient, free<br>
                    <strong>Cons:</strong> Vulnerable to malware and hacking</p>
                    
                    <h4>2. Exchange Wallets</h4>
                    <p>Wallets provided by cryptocurrency exchanges.</p>
                    <p><strong>Pros:</strong> Easy access for trading<br>
                    <strong>Cons:</strong> You don't control private keys, higher risk</p>
                    
                    <h3>Cold Wallets (Offline Storage)</h3>
                    <h4>1. Hardware Wallets</h4>
                    <p>Physical devices like Ledger or Trezor that store private keys offline.</p>
                    <p><strong>Pros:</strong> Highly secure, immune to online attacks<br>
                    <strong>Cons:</strong> Cost money, can be lost or damaged</p>
                    
                    <h4>2. Paper Wallets</h4>
                    <p>Private keys printed on paper.</p>
                    <p><strong>Pros:</strong> Completely offline, free<br>
                    <strong>Cons:</strong> Can be lost, damaged, or stolen</p>
                    
                    <h3>Best Practices</h3>
                    <ul>
                        <li>Use hardware wallets for large amounts</li>
                        <li>Keep only small amounts in hot wallets for daily use</li>
                        <li>Never share your private keys or seed phrase</li>
                        <li>Backup your wallet in multiple secure locations</li>
                        <li>Use wallets from reputable developers</li>
                    </ul>
                    
                    <div style="background: #dcfce7; border-left: 4px solid #22c55e; padding: 16px; margin: 20px 0;">
                        <strong>✅ Security Tip:</strong> For long-term storage, use a hardware wallet. For active trading, use a reputable exchange wallet.
                    </div>
                ''',
                'excerpt': 'Learn about different types of cryptocurrency wallets - hot wallets, cold wallets, hardware wallets, and how to choose the right one.',
                'category': 'wallets',
                'order': 1,
                'is_published': True,
            },
            {
                'title': 'How to Set Up a Crypto Wallet',
                'slug': 'setup-crypto-wallet',
                'content': '''
                    <h2>Setting Up Your First Cryptocurrency Wallet</h2>
                    
                    <h3>Step 1: Choose Your Wallet Type</h3>
                    <p>Based on your needs:</p>
                    <ul>
                        <li><strong>Active Trading:</strong> Exchange wallet or mobile wallet</li>
                        <li><strong>Long-term Storage:</strong> Hardware wallet</li>
                        <li><strong>Small Amounts:</strong> Mobile or desktop wallet</li>
                    </ul>
                    
                    <h3>Step 2: Download and Install</h3>
                    <ol>
                        <li>Visit the official website of your chosen wallet</li>
                        <li>Download from official sources only (avoid third-party sites)</li>
                        <li>Verify the download using checksums if available</li>
                        <li>Install following the official instructions</li>
                    </ol>
                    
                    <h3>Step 3: Create Your Wallet</h3>
                    <ol>
                        <li>Open the wallet application</li>
                        <li>Choose "Create New Wallet"</li>
                        <li>Set a strong password (use a password manager)</li>
                        <li>Write down your recovery seed phrase</li>
                    </ol>
                    
                    <h3>Step 4: Secure Your Seed Phrase</h3>
                    <p><strong>CRITICAL:</strong> Your seed phrase is the master key to your wallet!</p>
                    <ul>
                        <li>Write it down on paper (never store digitally)</li>
                        <li>Store in multiple secure locations</li>
                        <li>Never share with anyone</li>
                        <li>Consider using a metal backup for fire/water protection</li>
                    </ul>
                    
                    <h3>Step 5: Verify Your Wallet</h3>
                    <ol>
                        <li>Send a small test transaction</li>
                        <li>Verify you can receive funds</li>
                        <li>Test sending funds to another address</li>
                        <li>Verify you can restore from seed phrase (on a test wallet)</li>
                    </ol>
                    
                    <h3>Step 6: Enable Security Features</h3>
                    <ul>
                        <li>Enable two-factor authentication (2FA)</li>
                        <li>Set up biometric authentication if available</li>
                        <li>Enable transaction confirmations</li>
                        <li>Set up backup and recovery options</li>
                    </ul>
                    
                    <div style="background: #fee2e2; border-left: 4px solid #ef4444; padding: 16px; margin: 20px 0;">
                        <strong>🚨 Warning:</strong> If you lose your seed phrase, you will permanently lose access to your funds. There is no recovery option!
                    </div>
                ''',
                'excerpt': 'A detailed step-by-step guide on how to set up and secure your first cryptocurrency wallet.',
                'category': 'wallets',
                'order': 2,
                'is_published': True,
            },
            {
                'title': 'Cryptocurrency Security Best Practices',
                'slug': 'cryptocurrency-security-best-practices',
                'content': '''
                    <h2>Protecting Your Cryptocurrency Investments</h2>
                    
                    <h3>1. Secure Your Private Keys</h3>
                    <ul>
                        <li>Never share private keys or seed phrases</li>
                        <li>Store seed phrases offline in secure locations</li>
                        <li>Use hardware wallets for significant amounts</li>
                        <li>Consider multi-signature wallets for extra security</li>
                    </ul>
                    
                    <h3>2. Use Strong Passwords</h3>
                    <ul>
                        <li>Use unique, complex passwords for each account</li>
                        <li>Enable two-factor authentication (2FA) everywhere</li>
                        <li>Use authenticator apps instead of SMS when possible</li>
                        <li>Never reuse passwords across platforms</li>
                    </ul>
                    
                    <h3>3. Beware of Phishing</h3>
                    <ul>
                        <li>Always verify website URLs before entering credentials</li>
                        <li>Never click suspicious links in emails or messages</li>
                        <li>Double-check wallet addresses before sending funds</li>
                        <li>Be cautious of "too good to be true" offers</li>
                    </ul>
                    
                    <h3>4. Keep Software Updated</h3>
                    <ul>
                        <li>Regularly update wallet software</li>
                        <li>Keep operating systems and antivirus updated</li>
                        <li>Use reputable antivirus and anti-malware software</li>
                        <li>Avoid downloading software from untrusted sources</li>
                    </ul>
                    
                    <h3>5. Use Reputable Exchanges</h3>
                    <ul>
                        <li>Research exchange reputation and security history</li>
                        <li>Check if exchanges are regulated and licensed</li>
                        <li>Use exchanges with insurance coverage</li>
                        <li>Don't keep large amounts on exchanges</li>
                    </ul>
                    
                    <h3>6. Network Security</h3>
                    <ul>
                        <li>Never use public Wi-Fi for crypto transactions</li>
                        <li>Use VPN when accessing crypto accounts on public networks</li>
                        <li>Consider using a dedicated device for crypto activities</li>
                        <li>Enable firewall and network security features</li>
                    </ul>
                    
                    <h3>Common Scams to Avoid</h3>
                    <ul>
                        <li>Fake exchange websites</li>
                        <li>Ponzi schemes and "guaranteed returns"</li>
                        <li>Fake wallet apps</li>
                        <li>Social media impersonation</li>
                        <li>Fake airdrops and giveaways</li>
                    </ul>
                    
                    <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 16px; margin: 20px 0;">
                        <strong>🛡️ Remember:</strong> In cryptocurrency, you are your own bank. Security is your responsibility. When in doubt, verify everything twice!
                    </div>
                ''',
                'excerpt': 'Essential security practices to protect your cryptocurrency from hackers, scammers, and theft.',
                'category': 'security',
                'order': 1,
                'is_published': True,
            },
            {
                'title': 'Protecting Against Crypto Scams',
                'slug': 'protecting-against-crypto-scams',
                'content': '''
                    <h2>How to Identify and Avoid Cryptocurrency Scams</h2>
                    
                    <h3>Types of Common Scams</h3>
                    
                    <h4>1. Phishing Scams</h4>
                    <p>Fake websites or emails designed to steal your credentials.</p>
                    <ul>
                        <li>Check URLs carefully (look for HTTPS and correct domain)</li>
                        <li>Never enter credentials from email links</li>
                        <li>Use bookmarks for important sites</li>
                    </ul>
                    
                    <h4>2. Ponzi Schemes</h4>
                    <p>Investment scams promising unrealistic returns.</p>
                    <ul>
                        <li>Red flags: Guaranteed returns, pressure to invest quickly</li>
                        <li>Research the company and team thoroughly</li>
                        <li>If it sounds too good to be true, it probably is</li>
                    </ul>
                    
                    <h4>3. Fake ICOs and Tokens</h4>
                    <p>Fraudulent initial coin offerings with no real product.</p>
                    <ul>
                        <li>Verify the project has a real use case</li>
                        <li>Check if the team is doxxed (publicly identified)</li>
                        <li>Review the whitepaper and code repository</li>
                    </ul>
                    
                    <h4>4. Social Media Impersonation</h4>
                    <p>Scammers impersonate celebrities or influencers.</p>
                    <ul>
                        <li>Verify account authenticity (blue checkmarks, follower count)</li>
                        <li>Never send crypto to "giveaway" addresses</li>
                        <li>Legitimate giveaways never ask you to send crypto first</li>
                    </ul>
                    
                    <h4>5. Fake Wallet Apps</h4>
                    <p>Malicious apps designed to steal your funds.</p>
                    <ul>
                        <li>Only download from official app stores</li>
                        <li>Check developer information and reviews</li>
                        <li>Verify app permissions are reasonable</li>
                    </ul>
                    
                    <h3>Red Flags to Watch For</h3>
                    <ul>
                        <li>🚩 Promises of guaranteed returns</li>
                        <li>🚩 Pressure to act immediately</li>
                        <li>🚩 Requests for private keys or seed phrases</li>
                        <li>🚩 Unsolicited investment offers</li>
                        <li>🚩 Poor grammar and spelling in communications</li>
                        <li>🚩 Requests to send crypto to receive more</li>
                        <li>🚩 Anonymous or unverifiable team members</li>
                    </ul>
                    
                    <h3>What to Do If You're Scammed</h3>
                    <ol>
                        <li>Immediately transfer remaining funds to a new wallet</li>
                        <li>Report to local authorities and cybercrime units</li>
                        <li>Report to the exchange or platform involved</li>
                        <li>Document all communications and transactions</li>
                        <li>Warn others through social media and forums</li>
                    </ol>
                    
                    <div style="background: #fee2e2; border-left: 4px solid #ef4444; padding: 16px; margin: 20px 0;">
                        <strong>⚠️ Critical Rule:</strong> Never share your private keys, seed phrase, or send crypto to receive more. Legitimate platforms never ask for these!
                    </div>
                ''',
                'excerpt': 'Learn to identify common cryptocurrency scams and how to protect yourself from fraudsters and scammers.',
                'category': 'security',
                'order': 2,
                'is_published': True,
            },
        ]

        created_count = 0
        for tutorial_data in tutorials_data:
            tutorial, created = Tutorial.objects.get_or_create(
                slug=tutorial_data['slug'],
                defaults={
                    **tutorial_data,
                    'author': admin_user,
                }
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created tutorial: {tutorial.title}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Tutorial already exists: {tutorial.title}')
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\nSuccessfully populated {created_count} new tutorials!'
            )
        )

