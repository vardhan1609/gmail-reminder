"""
Unified database access layer.
Provides SQLAlchemy session management alongside a lightweight collection-like
adapter interface to preserve compatibility with existing code and tests,
while backed by PostgreSQL / SQLite.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from bson import ObjectId
from sqlalchemy import or_, and_, desc, asc
from sqlalchemy.orm import Session

from app.database.session import (
    SessionLocal,
    init_db as session_init_db,
    close_db as session_close_db,
    engine,
    get_db_session,
)
from app.models.db_models import (
    AccountModel,
    AuditEventModel,
    CalendarEventModel,
    DestinationModel,
    EmailModel,
    EmailVerificationTokenModel,
    GmailConnectionModel,
    MFAConfigurationModel,
    NotificationDeliveryModel,
    NotificationIntegrationModel,
    NotificationPreferencesModel,
    PasswordResetTokenModel,
    RecoveryCodeModel,
    ReminderModel,
    RoutingRuleModel,
    SyncStateModel,
    UserModel,
    UserSessionModel,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _to_clean_id(val: Any) -> str:
    if isinstance(val, ObjectId):
        return str(val)
    return str(val) if val is not None else ""


class TableAdapter:
    """Provides familiar find, find_one, insert_one, update_one, delete_one, count_documents methods."""

    def __init__(self, model_class):
        self.model = model_class

    def _apply_filter(self, query, filter_dict: Dict[str, Any]):
        for k, v in filter_dict.items():
            col_name = k
            if k == "_id":
                col_name = "id"
            elif k == "gmail_id":
                col_name = "gmail_message_id"

            if not hasattr(self.model, col_name):
                continue
            col = getattr(self.model, col_name)

            if isinstance(v, dict):
                for op, val in v.items():
                    if op == "$gte":
                        query = query.filter(col >= val)
                    elif op == "$lte":
                        query = query.filter(col <= val)
                    elif op == "$gt":
                        query = query.filter(col > val)
                    elif op == "$lt":
                        query = query.filter(col < val)
                    elif op == "$in":
                        query = query.filter(col.in_(val))
                    elif op == "$nin":
                        query = query.filter(~col.in_(val))
                    elif op == "$ne":
                        query = query.filter(col != val)
            else:
                if v is None:
                    query = query.filter(or_(col == None, col == ""))
                elif isinstance(v, bool):
                    query = query.filter(col == v)
                elif isinstance(v, (int, float)):
                    query = query.filter(col == v)
                else:
                    query = query.filter(col == _to_clean_id(v))
        return query

    def find_one(self, filter_dict: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        with SessionLocal() as session:
            query = session.query(self.model)
            if filter_dict:
                query = self._apply_filter(query, filter_dict)
            item = query.first()
            if not item:
                return None
            data = item.to_dict()
            data["_id"] = data["id"]
            return data

    def find(self, filter_dict: Optional[Dict[str, Any]] = None):
        return QueryCursor(self.model, filter_dict)

    def insert_one(self, doc: Dict[str, Any]):
        clean_doc = dict(doc)
        if "_id" in clean_doc:
            clean_doc["id"] = _to_clean_id(clean_doc.pop("_id"))
        if "gmail_id" in clean_doc and "gmail_message_id" not in clean_doc:
            clean_doc["gmail_message_id"] = clean_doc.pop("gmail_id")
        if "body" in clean_doc and "plain_body" not in clean_doc:
            clean_doc["plain_body"] = clean_doc.pop("body")
        if "deadline" in clean_doc and "extracted_deadline" not in clean_doc:
            clean_doc["extracted_deadline"] = clean_doc.pop("deadline")
        if "reminder_time" in clean_doc and "scheduled_at" not in clean_doc:
            clean_doc["scheduled_at"] = clean_doc.pop("reminder_time")
        if "retries" in clean_doc and "retry_count" not in clean_doc:
            clean_doc["retry_count"] = clean_doc.pop("retries")

        # Strip unmapped keys and convert date strings
        valid_cols = {c.name for c in self.model.__table__.columns}
        filtered = {}
        for k, v in clean_doc.items():
            if k in valid_cols:
                if k in ("scheduled_at", "extracted_deadline", "received_at", "created_at", "updated_at", "sent_at", "last_successful_sync") and isinstance(v, str):
                    try:
                        v = datetime.fromisoformat(v)
                    except Exception:
                        pass
                filtered[k] = v

        with SessionLocal() as session:
            obj = self.model(**filtered)
            session.add(obj)
            session.commit()
            session.refresh(obj)
            doc["_id"] = obj.id
            doc["id"] = obj.id
            return doc

    def update_one(self, filter_dict: Dict[str, Any], update_dict: Dict[str, Any], upsert: bool = False):
        with SessionLocal() as session:
            query = session.query(self.model)
            query = self._apply_filter(query, filter_dict)
            obj = query.first()

            set_fields = update_dict.get("$set", {})
            set_on_insert = update_dict.get("$setOnInsert", {})

            if not obj:
                if upsert:
                    merged = dict(filter_dict)
                    merged.update(set_on_insert)
                    merged.update(set_fields)
                    return self.insert_one(merged)
                class Result:
                    matched_count = 0
                return Result()

            for k, v in set_fields.items():
                col_name = "id" if k == "_id" else k
                if col_name == "gmail_id":
                    col_name = "gmail_message_id"
                elif col_name == "body":
                    col_name = "plain_body"
                elif col_name == "deadline":
                    col_name = "extracted_deadline"
                elif col_name == "reminder_time":
                    col_name = "scheduled_at"
                elif col_name == "retries":
                    col_name = "retry_count"

                # Convert ISO strings to datetime for DateTime columns
                if col_name in ("scheduled_at", "extracted_deadline", "received_at", "created_at", "updated_at", "sent_at", "last_successful_sync") and isinstance(v, str):
                    try:
                        v = datetime.fromisoformat(v)
                    except Exception:
                        pass

                if hasattr(obj, col_name):
                    setattr(obj, col_name, v)

            session.commit()
            class Result:
                matched_count = 1
            return Result()

    def update_many(self, filter_dict: Dict[str, Any], update_dict: Dict[str, Any]):
        with SessionLocal() as session:
            query = session.query(self.model)
            query = self._apply_filter(query, filter_dict)
            objs = query.all()
            set_fields = update_dict.get("$set", {})
            for obj in objs:
                for k, v in set_fields.items():
                    if hasattr(obj, k):
                        setattr(obj, k, v)
            session.commit()

    def delete_one(self, filter_dict: Dict[str, Any]):
        with SessionLocal() as session:
            query = session.query(self.model)
            query = self._apply_filter(query, filter_dict)
            obj = query.first()
            if obj:
                session.delete(obj)
                session.commit()
                class Result:
                    deleted_count = 1
                return Result()
            class Result:
                deleted_count = 0
            return Result()

    def delete_many(self, filter_dict: Dict[str, Any]):
        with SessionLocal() as session:
            query = session.query(self.model)
            query = self._apply_filter(query, filter_dict)
            objs = query.all()
            count = len(objs)
            for obj in objs:
                session.delete(obj)
            session.commit()
            class Result:
                deleted_count = count
            return Result()

    def count_documents(self, filter_dict: Optional[Dict[str, Any]] = None) -> int:
        with SessionLocal() as session:
            query = session.query(self.model)
            if filter_dict:
                query = self._apply_filter(query, filter_dict)
            return query.count()

    def create_index(self, *args, **kwargs):
        # Indexes are already defined in SQLAlchemy models
        pass


class QueryCursor:
    def __init__(self, model_class, filter_dict: Optional[Dict[str, Any]] = None):
        self.model = model_class
        self.filter_dict = filter_dict or {}
        self._sort_field = None
        self._sort_dir = -1
        self._limit = None
        self._skip = 0

    def sort(self, field, direction=-1):
        if isinstance(field, list):
            self._sort_field, self._sort_dir = field[0]
        else:
            self._sort_field = field
            self._sort_dir = direction
        return self

    def limit(self, n: int):
        self._limit = n
        return self

    def skip(self, n: int):
        self._skip = n
        return self

    def _execute(self) -> List[Dict[str, Any]]:
        with SessionLocal() as session:
            query = session.query(self.model)
            adapter = TableAdapter(self.model)
            query = adapter._apply_filter(query, self.filter_dict)

            if self._sort_field:
                field_name = "id" if self._sort_field == "_id" else self._sort_field
                if field_name == "reminder_time":
                    field_name = "scheduled_at"
                if hasattr(self.model, field_name):
                    col = getattr(self.model, field_name)
                    query = query.order_by(desc(col) if self._sort_dir == -1 else asc(col))

            if self._skip:
                query = query.offset(self._skip)
            if self._limit:
                query = query.limit(self._limit)

            results = []
            for item in query.all():
                d = item.to_dict()
                d["_id"] = d["id"]
                results.append(d)
            return results

    def __iter__(self):
        return iter(self._execute())

    def __list__(self):
        return self._execute()


class DatabaseAdapter:
    def __init__(self):
        self.accounts = TableAdapter(AccountModel)
        self.emails = TableAdapter(EmailModel)
        self.reminders = TableAdapter(ReminderModel)
        self.destinations = TableAdapter(DestinationModel)
        self.routing_rules = TableAdapter(RoutingRuleModel)
        self.calendar_events = TableAdapter(CalendarEventModel)
        self.notification_deliveries = TableAdapter(NotificationDeliveryModel)
        self.sync_states = TableAdapter(SyncStateModel)
        self.users = TableAdapter(UserModel)
        self.user_sessions = TableAdapter(UserSessionModel)
        self.gmail_connections = TableAdapter(GmailConnectionModel)
        self.notification_integrations = TableAdapter(NotificationIntegrationModel)
        self.notification_preferences = TableAdapter(NotificationPreferencesModel)
        self.audit_events = TableAdapter(AuditEventModel)

    @property
    def admin(self):
        class Admin:
            def command(self, cmd):
                return {"ok": 1}
        return Admin()


_db_instance: Optional[DatabaseAdapter] = None


def get_db() -> DatabaseAdapter:
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseAdapter()
    return _db_instance


def init_db():
    session_init_db()


def close_db():
    session_close_db()
