"""
Create Polymarket CLOB client
Note: This is a simplified wrapper. For full functionality, you may need to use
the JavaScript SDK via subprocess or implement the full Python API client.
"""
import asyncio
import json
import os
import shutil
from pathlib import Path
from typing import Optional, Dict, Any
from web3 import Web3
from eth_account import Account
from ..config.env import ENV
from ..utils.logger import info, error


async def is_contract_wallet(address: str) -> bool:
    """Check if a wallet is a contract address by checking if it has code"""
    try:
        w3 = Web3(Web3.HTTPProvider(ENV.RPC_URL))
        # Convert address to checksum format for web3.py
        checksum_address = Web3.to_checksum_address(address)
        code = w3.eth.get_code(checksum_address)
        # If code is not "0x", then it's a contract
        return code != b'0x'
    except Exception as e:
        error(f'Error checking wallet type: {e}')
        return False


async def run_clob_bridge(action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run the Node-based CLOB bridge script and return its JSON response."""
    node_path = shutil.which('node')
    if not node_path:
        return {'success': False, 'error': 'Node.js is required for CLOB execution. Install Node.js >=18.'}

    script_path = Path(__file__).resolve().parents[2] / 'scripts' / 'clob_bridge.mjs'
    if not script_path.exists():
        return {'success': False, 'error': f'CLOB bridge script not found at {script_path}'}

    request = {'action': action, 'payload': payload}
    process = await asyncio.create_subprocess_exec(
        node_path,
        str(script_path),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate(json.dumps(request).encode())
    if process.returncode != 0:
        error_output = (stderr.decode() or stdout.decode()).strip()
        return {'success': False, 'error': error_output or 'CLOB bridge failed'}

    try:
        return json.loads(stdout.decode() or '{}')
    except json.JSONDecodeError:
        return {'success': False, 'error': 'Invalid response from CLOB bridge'}


class ClobClient:
    """Simplified Polymarket CLOB client wrapper"""
    
    def __init__(
        self,
        host: str,
        chain_id: int,
        wallet: Any,
        api_creds: Optional[Dict[str, Any]] = None,
        signature_type: str = 'EOA',
        proxy_wallet: Optional[str] = None
    ):
        self.host = host.rstrip('/')
        self.chain_id = chain_id
        self.wallet = wallet
        self.api_creds = api_creds or {}
        self.signature_type = signature_type
        self.proxy_wallet = proxy_wallet
        self.api_key = api_creds.get('key') if api_creds else None
        self.api_secret = api_creds.get('secret') if api_creds else None
        self.api_passphrase = api_creds.get('passphrase') if api_creds else None
    
    async def create_api_key(self) -> Dict[str, Any]:
        """Create API key - placeholder, needs implementation"""
        # This would need to call the Polymarket API to create keys
        # For now, return empty dict
        return {}
    
    async def derive_api_key(self) -> Dict[str, Any]:
        """Derive API key - placeholder, needs implementation"""
        # This would need to call the Polymarket API to derive keys
        # For now, return empty dict
        return {}
    
    async def get_order_book(self, token_id: str) -> Dict[str, Any]:
        """Get order book for a token"""
        import httpx
        url = f'{self.host}/book?token_id={token_id}'
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
    
    async def create_market_order(self, order_args: Dict[str, Any]) -> Dict[str, Any]:
        """Create a market order - placeholder, needs full implementation"""
        # This needs to create and sign an order according to Polymarket's format
        # For now, return a placeholder
        return {
            'side': order_args.get('side'),
            'tokenID': order_args.get('tokenID'),
            'amount': order_args.get('amount'),
            'price': order_args.get('price'),
        }
    
    async def post_order(self, signed_order: Dict[str, Any], order_type: str) -> Dict[str, Any]:
        """Post order to Polymarket via the Node CLOB bridge"""
        order = signed_order or {}
        order_args = {
            'side': order.get('side'),
            'tokenID': order.get('tokenID') or order.get('tokenId'),
            'amount': order.get('amount'),
            'price': order.get('price'),
        }

        payload = {
            'host': self.host,
            'chainId': self.chain_id,
            'signatureType': self.signature_type,
            'funderAddress': self.proxy_wallet,
            'privateKey': ENV.PRIVATE_KEY,
            'orderType': order_type,
            'order': order_args,
        }

        return await run_clob_bridge('post_order', payload)


async def create_clob_client() -> ClobClient:
    """Create and initialize CLOB client"""
    chain_id = 137  # Polygon
    host = ENV.CLOB_HTTP_URL
    
    # Create wallet from private key
    account = Account.from_key(ENV.PRIVATE_KEY)
    
    # Detect wallet type for signing (allow explicit override)
    signature_override = os.getenv('CLOB_SIGNATURE_TYPE')
    is_proxy_contract = await is_contract_wallet(ENV.PROXY_WALLET)
    if signature_override:
        signature_type = signature_override
        info(f'Using CLOB_SIGNATURE_TYPE override: {signature_type}')
    else:
        signature_type = 'POLY_PROXY' if is_proxy_contract else 'EOA'
        info(
            f'Wallet type detected: {"Contract (POLY_PROXY)" if is_proxy_contract else "EOA (Externally Owned Account)"}'
        )
    
    # Create initial client
    clob_client = ClobClient(
        host=host,
        chain_id=chain_id,
        wallet=account,
        signature_type=signature_type,
        proxy_wallet=ENV.PROXY_WALLET if is_proxy_contract else None
    )
    
    # Try to create or derive API key
    try:
        creds = await clob_client.create_api_key()
        if not creds.get('key'):
            creds = await clob_client.derive_api_key()
    except Exception as e:
        error(f'Failed to create/derive API key: {e}')
        creds = {}
    
    # Create client with credentials
    clob_client = ClobClient(
        host=host,
        chain_id=chain_id,
        wallet=account,
        api_creds=creds,
        signature_type=signature_type,
        proxy_wallet=ENV.PROXY_WALLET if is_proxy_contract else None
    )
    
    return clob_client

