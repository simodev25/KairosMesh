from sqlalchemy.orm import Session

from app.db.models.metaapi_account import MetaApiAccount


class MetaApiAccountSelector:
    def resolve(self, db: Session, account_ref: int | None) -> MetaApiAccount | None:
        if account_ref is not None:
            selected = db.query(MetaApiAccount).filter(MetaApiAccount.id == account_ref, MetaApiAccount.enabled.is_(True)).first()
            if selected:
                return selected

        default = (
            db.query(MetaApiAccount)
            .filter(MetaApiAccount.enabled.is_(True), MetaApiAccount.is_default.is_(True))
            .order_by(MetaApiAccount.id.asc())
            .first()
        )
        if default:
            return default

        return (
            db.query(MetaApiAccount)
            .filter(MetaApiAccount.enabled.is_(True))
            .order_by(MetaApiAccount.id.asc())
            .first()
        )
