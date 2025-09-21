import requests
import hmac
import hashlib
import time
from urllib.parse import urlencode
import os
import json

def load_env_file():
    """Charge les variables depuis un fichier .env manuellement"""
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    env_vars = {}
    
    try:
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip().strip('"').strip("'")
        return env_vars
    except FileNotFoundError:
        return {}

# Charger les variables d'environnement
env_vars = load_env_file()

# Configuration API Binance
BINANCE_API_KEY = env_vars.get('BINANCE_API_KEY') or os.getenv('BINANCE_API_KEY')
BINANCE_SECRET_KEY = env_vars.get('BINANCE_SECRET_KEY') or os.getenv('BINANCE_SECRET_KEY')

# Vérification des clés
if not BINANCE_API_KEY or not BINANCE_SECRET_KEY:
    raise ValueError("Les clés API Binance ne sont pas configurées dans les variables d'environnement ou le fichier .env")

class BinanceAPI:
    def __init__(self, api_key, secret_key):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = "https://api.binance.com"
    
    def _generate_signature(self, query_string):
        """Génère la signature HMAC SHA256 pour l'authentification"""
        return hmac.new(
            self.secret_key.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def _make_request(self, endpoint, params=None):
        """Effectue une requête authentifiée à l'API Binance"""
        if params is None:
            params = {}
        
        # Ajouter le timestamp
        params['timestamp'] = int(time.time() * 1000)
        
        # Créer la query string
        query_string = urlencode(params)
        
        # Générer la signature
        signature = self._generate_signature(query_string)
        
        # Ajouter la signature aux paramètres
        params['signature'] = signature
        
        # Headers avec la clé API
        headers = {
            'X-MBX-APIKEY': self.api_key
        }
        
        # Effectuer la requête
        url = f"{self.base_url}{endpoint}"
        response = requests.get(url, params=params, headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Erreur API: {response.status_code}")
            print(f"Message: {response.text}")
            return None
    
    def get_last_trade(self, symbol=None, limit=1):
        """Récupère le dernier trade de l'utilisateur"""
        endpoint = "/api/v3/myTrades"
        params = {
            'limit': limit
        }
        
        if symbol:
            params['symbol'] = symbol
            
        trades = self._make_request(endpoint, params)
        return trades
    
    def get_account_info(self):
        """Récupère les informations du compte"""
        endpoint = "/api/v3/account"
        return self._make_request(endpoint)
    
    def get_open_orders(self):
        """Récupère tous les ordres ouverts"""
        endpoint = "/api/v3/openOrders"
        return self._make_request(endpoint)
    
    def get_all_orders(self, symbol=None, limit=10):
        """Récupère les derniers ordres"""
        endpoint = "/api/v3/allOrders"
        params = {
            'limit': limit
        }
        
        if symbol:
            params['symbol'] = symbol
            
        orders = self._make_request(endpoint, params)
        return orders
    
    def get_recent_filled_orders(self, limit=3):
        """Récupère les ordres fermés récents pour tous les symboles ayant des balances"""
        account_info = self.get_account_info()
        if not account_info:
            return []
        
        all_filled_orders = []
        
        # Récupérer les symboles qui ont des balances non nulles
        symbols_with_balance = []
        for balance in account_info['balances']:
            if float(balance['free']) > 0 or float(balance['locked']) > 0:
                asset = balance['asset']
                # Créer des paires communes avec cet asset
                common_pairs = [f"{asset}USDT", f"{asset}BTC", f"{asset}ETH", f"BTC{asset}", f"ETH{asset}"]
                symbols_with_balance.extend(common_pairs)
        
        # Ajouter quelques paires populaires
        popular_symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "SOLUSDT"]
        symbols_with_balance.extend(popular_symbols)
        
        # Supprimer les doublons
        symbols_with_balance = list(set(symbols_with_balance))
        
        # Récupérer les ordres pour chaque symbole et filtrer les FILLED
        for symbol in symbols_with_balance[:15]:  # Augmenter à 15 symboles pour avoir plus de chances
            try:
                orders = self.get_all_orders(symbol, limit=20)  # Récupérer plus d'ordres pour filtrer
                if orders:
                    # Filtrer uniquement les ordres FILLED
                    filled_orders = [order for order in orders if order['status'] == 'FILLED']
                    all_filled_orders.extend(filled_orders)
            except:
                continue
        
        # Trier par timestamp et retourner les plus récents
        if all_filled_orders:
            all_filled_orders.sort(key=lambda x: x['time'], reverse=True)
            return all_filled_orders[:limit]
        
        return []

def format_trade_info(trade):
    """Formate les informations du trade pour un affichage lisible"""
    if not trade:
        return "Aucun trade trouvé"
    
    return f"""
    ═══════════════════════════════════════
    📊 DERNIER TRADE
    ═══════════════════════════════════════
    🔸 Symbole: {trade['symbol']}
    🔸 ID Trade: {trade['id']}
    🔸 ID Ordre: {trade['orderId']}
    🔸 Prix: {trade['price']} 
    🔸 Quantité: {trade['qty']}
    🔸 Commission: {trade['commission']} {trade['commissionAsset']}
    🔸 Côté: {'🟢 ACHAT' if trade['isBuyer'] else '🔴 VENTE'}
    🔸 Maker: {'✅ Oui' if trade['isMaker'] else '❌ Non'}
    🔸 Date: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(trade['time']/1000))}
    ═══════════════════════════════════════
    """

def format_order_info(order):
    """Formate les informations de l'ordre pour un affichage lisible"""
    if not order:
        return "Aucun ordre trouvé"
    
    status_emoji = "✅" if order['status'] == 'FILLED' else "⏳" if order['status'] == 'NEW' else "❌"
    side_emoji = "🟢" if order['side'] == 'BUY' else "🔴"
    
    return f"""
    ═══════════════════════════════════════
    📊 ORDRE #{order['orderId']}
    ═══════════════════════════════════════
    🔸 Symbole: {order['symbol']}
    🔸 Côté: {side_emoji} {order['side']}
    🔸 Type: {order['type']}
    🔸 Quantité: {order['origQty']}
    🔸 Prix: {order['price']}
    🔸 Statut: {status_emoji} {order['status']}
    🔸 Date: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(order['time']/1000))}
    ═══════════════════════════════════════
    """

def main():
    # Initialiser l'API Binance avec les clés depuis les variables d'environnement
    binance = BinanceAPI(BINANCE_API_KEY, BINANCE_SECRET_KEY)
    
    print("🔍 Récupération de vos 3 derniers ordres fermés...")
    
    # Récupérer les ordres fermés récents
    filled_orders = binance.get_recent_filled_orders(limit=3)
    
    if filled_orders and len(filled_orders) > 0:
        print(f"✅ {len(filled_orders)} derniers ordres fermés trouvés:\n")
        
        # Afficher la réponse JSON brute
        print("📋 RÉPONSE JSON BRUTE:")
        print("=" * 80)
        print(json.dumps(filled_orders, indent=2))
        print("=" * 80)
        
    else:
        print("❌ Aucun ordre fermé trouvé")

if __name__ == "__main__":
    main()