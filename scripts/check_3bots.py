# -*- coding: utf-8 -*-
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
os.chdir(r'D:\NOTEBOOK\TradingView-Analyzer')
sys.path.insert(0, os.getcwd())
import httpx
BASE = 'http://127.0.0.1:8502'

# Check config
r = httpx.get(f'{BASE}/api/telegram/config', timeout=30)
d = r.json()
print('=== CONFIG ===')
for k in ['signal_bot', 'price_feed_bot', 'market_news_bot']:
    bot = d.get(k, {})
    tok = bot.get('bot_token', '')
    masked = tok[:8] + '...' if tok else 'NONE'
    print(k, 'enabled=', bot.get('enabled'), 'has_token=', bool(tok), 'token=', masked, 'chat_id=', repr(bot.get('chat_id')))

# Check if polling is active - test each token directly
print()
print('=== TOKEN TEST ===')
for k in ['signal_bot', 'price_feed_bot', 'market_news_bot']:
    bot = d.get(k, {})
    token = bot.get('bot_token', '')
    if not token:
        print(k, ': NO TOKEN')
        continue
    try:
        r = httpx.get(f'https://api.telegram.org/bot{token}/getMe', timeout=10)
        info = r.json()
        if info.get('ok'):
            user = info['result']
            print(k, ': OK - @' + str(user.get('username')) + ' (' + str(user.get('first_name')) + ')')
        else:
            print(k, ': FAILED - ' + str(info.get('description')))
    except Exception as e:
        print(k, ': ERROR - ' + str(e)[:80])

# Check getUpdates to see if polling works
print()
print('=== POLLING TEST ===')
for k in ['signal_bot', 'price_feed_bot', 'market_news_bot']:
    bot = d.get(k, {})
    token = bot.get('bot_token', '')
    if not token:
        continue
    try:
        r = httpx.get(f'https://api.telegram.org/bot{token}/getUpdates', params={'timeout': 1, 'limit': 1}, timeout=5)
        info = r.json()
        if info.get('ok'):
            n = len(info.get('result', []))
            print(k, ': polling OK, pending updates =', n)
        else:
            print(k, ': polling FAILED -', info.get('description'))
    except Exception as e:
        print(k, ': polling ERROR -', str(e)[:80])
