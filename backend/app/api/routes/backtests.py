from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import Role, require_roles
from app.db.models.backtest_run import BacktestRun
from app.db.models.backtest_trade import BacktestTrade
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.backtest import BacktestCreateRequest, BacktestRunDetailOut, BacktestRunOut
from app.services.backtest.engine import BacktestEngine

router = APIRouter(prefix='/backtests', tags=['backtests'])


@router.get('', response_model=list[BacktestRunOut])
def list_backtests(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN, Role.TRADER_OPERATOR, Role.ANALYST, Role.VIEWER)),
) -> list[BacktestRunOut]:
    runs = db.query(BacktestRun).order_by(BacktestRun.created_at.desc()).limit(limit).all()
    return [BacktestRunOut.model_validate(run) for run in runs]


@router.post('', response_model=BacktestRunOut)
def create_backtest(
    payload: BacktestCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN, Role.TRADER_OPERATOR, Role.ANALYST)),
) -> BacktestRunOut:
    settings = get_settings()
    pair = payload.pair.upper()
    timeframe = payload.timeframe.upper()
    if pair not in settings.default_forex_pairs:
        raise HTTPException(status_code=400, detail=f'Unsupported pair {pair} for V1 scope')
    if timeframe not in settings.default_timeframes:
        raise HTTPException(status_code=400, detail=f'Unsupported timeframe {timeframe} for V1 scope')
    if payload.end_date <= payload.start_date:
        raise HTTPException(status_code=400, detail='end_date must be greater than start_date')

    run = BacktestRun(
        pair=pair,
        timeframe=timeframe,
        start_date=payload.start_date,
        end_date=payload.end_date,
        strategy=payload.strategy,
        status='running',
        metrics={},
        equity_curve=[],
        created_by_id=user.id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    engine = BacktestEngine()

    try:
        result = engine.run(pair, timeframe, payload.start_date.isoformat(), payload.end_date.isoformat())
        run.status = 'completed'
        run.metrics = result.metrics
        run.equity_curve = result.equity_curve
        db.query(BacktestTrade).filter(BacktestTrade.run_id == run.id).delete()
        for trade in result.trades:
            db.add(
                BacktestTrade(
                    run_id=run.id,
                    side=trade['side'],
                    entry_time=trade['entry_time'],
                    exit_time=trade['exit_time'],
                    entry_price=trade['entry_price'],
                    exit_price=trade['exit_price'],
                    pnl_pct=trade['pnl_pct'],
                    outcome=trade['outcome'],
                )
            )
        db.commit()
        db.refresh(run)
        return BacktestRunOut.model_validate(run)
    except Exception as exc:
        run.status = 'failed'
        run.error = str(exc)
        db.commit()
        db.refresh(run)
        return BacktestRunOut.model_validate(run)


@router.get('/{backtest_id}', response_model=BacktestRunDetailOut)
def get_backtest(
    backtest_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN, Role.TRADER_OPERATOR, Role.ANALYST, Role.VIEWER)),
) -> BacktestRunDetailOut:
    run = db.get(BacktestRun, backtest_id)
    if not run:
        raise HTTPException(status_code=404, detail='Backtest run not found')
    return BacktestRunDetailOut.model_validate(run)
