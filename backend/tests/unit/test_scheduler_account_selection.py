from types import SimpleNamespace
from app.services import scheduler
class FakeCollection:
    def __init__(self, rows=None): self.rows=rows or []; self.updated=[]; self.inserted=[]
    def find(self, filters=None):
        filters=filters or {}
        return [row for row in self.rows if all(row.get(k)==v for k,v in filters.items())]
    def find_one(self, filters=None): return None
    def insert_one(self, document): self.inserted.append(document)
    def update_one(self, filters, update, upsert=False): self.updated.append((filters,update,upsert))
def test_poll_all_accounts_processes_only_requested_user_and_oauth_connection(monkeypatch,tmp_path):
    token_file=tmp_path/"gmail-token.json"; token_file.write_text("test token",encoding="utf-8")
    connections=FakeCollection([
        {"id":"one","user_id":"user-1","email":"one@example.com","token_path":str(token_file),"active":True},
        {"id":"two","user_id":"user-2","email":"two@example.com","token_path":str(token_file),"active":True},
        {"id":"cross-tenant","user_id":"user-2","email":"one@example.com","token_path":str(token_file),"active":True},
    ])
    db=SimpleNamespace(accounts=FakeCollection(),gmail_connections=connections,sync_states=FakeCollection())
    calls=[]
    monkeypatch.setattr(scheduler,"sync_messages_incremental",lambda path,history_id:(calls.append(path) or [],"history-1"))
    monkeypatch.setattr(scheduler,"publish_event",lambda *args,**kwargs:None)
    scheduler._shutdown_event.clear()
    scheduler._poll_all_accounts(db,"user-1","one@example.com")
    assert calls==[str(token_file)]
    assert any(filters.get("user_id")=="user-1" for filters,_update,_upsert in connections.updated)
