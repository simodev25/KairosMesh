import logging
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.execution_order import ExecutionOrder
from app.services.trading.account_selector import MetaApiAccountSelector
from app.services.trading.metaapi_client import MetaApiClient

logger = logging.getLogger(__name__)


class ExecutionService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.metaapi = MetaApiClient()
        self.account_selector = MetaApiAccountSelector()

    async def execute(
        self,
        db: Session,
        run_id: int,
        mode: str,
        symbol: str,
        side: str,
        volume: float,
        stop_loss: float | None,
        take_profit: float | None,
        metaapi_account_ref: int | None = None,
    ) -> dict[str, Any]:
        if side == 'HOLD':
            return {'status': 'skipped', 'reason': 'No order executed for HOLD decision.'}

        request_payload = {
            'symbol': symbol,
            'side': side,
            'volume': volume,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'metaapi_account_ref': metaapi_account_ref,
        }

        order = ExecutionOrder(
            run_id=run_id,
            mode=mode,
            side=side,
            symbol=symbol,
            volume=volume,
            request_payload=request_payload,
            response_payload={},
            status='created',
        )
        db.add(order)
        db.flush()

        if mode == 'simulation':
            response = {'simulated': True, 'fill_price': None, 'message': 'Simulation order accepted'}
            order.status = 'simulated'
            order.response_payload = response
            db.commit()
            return response

        if mode == 'paper' and not self.settings.enable_paper_execution:
            order.status = 'blocked'
            order.error = 'Paper trading disabled by configuration.'
            db.commit()
            return {'executed': False, 'error': order.error}

        if mode == 'live' and not self.settings.allow_live_trading:
            order.status = 'blocked'
            order.error = 'Live trading is disabled by default.'
            db.commit()
            return {'executed': False, 'error': order.error}

        if mode in {'paper', 'live'}:
            selected_account = self.account_selector.resolve(db, metaapi_account_ref)
            metaapi_response = await self.metaapi.place_order(
                symbol=symbol,
                side=side,
                volume=volume,
                stop_loss=stop_loss,
                take_profit=take_profit,
                account_id=selected_account.account_id if selected_account else None,
                region=selected_account.region if selected_account else None,
            )
            if metaapi_response.get('executed'):
                metaapi_response['account_label'] = selected_account.label if selected_account else 'default'
                order.status = 'submitted'
                order.response_payload = metaapi_response
                db.commit()
                return metaapi_response

            # Degraded fallback: emulate paper execution without external broker.
            if mode == 'paper':
                fallback = {'simulated': True, 'paper_fallback': True, 'reason': metaapi_response.get('reason', 'MetaApi unavailable')}
                order.status = 'paper-simulated'
                order.response_payload = fallback
                db.commit()
                return fallback

            order.status = 'failed'
            order.error = metaapi_response.get('reason', 'MetaApi execution failed')
            order.response_payload = metaapi_response
            db.commit()
            return {'executed': False, 'error': order.error, 'details': metaapi_response}

        order.status = 'failed'
        order.error = f'Unsupported execution mode: {mode}'
        db.commit()
        return {'executed': False, 'error': order.error}
