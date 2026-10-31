from pathlib import Path
import ast

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent


def test_legacy_oauth_router_is_not_mounted():
    source = (BACKEND / 'app' / 'main.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    mounted = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == 'app' and node.func.attr == 'include_router' and node.args:
                mounted.add(ast.unparse(node.args[0]))
    assert mounted == {'health.router', 'api_v1_router'}
    assert not (BACKEND / 'app' / 'api' / 'auth.py').exists()


def test_registration_has_unique_constraint_and_integrity_error_handling():
    models = (BACKEND / 'app' / 'models' / 'db_models.py').read_text(encoding='utf-8')
    auth = (BACKEND / 'app' / 'api' / 'v1' / 'auth.py').read_text(encoding='utf-8')
    assert 'email = Column(String(255), unique=True, nullable=False, index=True)' in models
    assert 'IntegrityError' in auth
    migration_dir = BACKEND / 'alembic' / 'versions'
    assert any('ix_users_email' in p.read_text(encoding='utf-8') and 'unique=True' in p.read_text(encoding='utf-8') for p in migration_dir.glob('*.py'))


def test_disconnect_cleanup_imports_account_model():
    source = (BACKEND / 'app' / 'api' / 'v1' / 'integrations.py').read_text(encoding='utf-8')
    assert '    AccountModel,' in source
    start = source.index('def disconnect_gmail')
    assert source.index('db.commit()', start) < source.index('os.remove(token_path)', start)


def test_bridge_is_authenticated_and_loopback_only():
    source = (REPO / 'whatsapp-bridge' / 'src' / 'index.js').read_text(encoding='utf-8')
    assert 'app.post("/api/configure", requireAuth' in source
    assert 'app.listen(PORT, "127.0.0.1"' in source
    assert 'savedConfig.verifyToken || "change-me-webhook"' not in source
    assert 'isStrongWebhookVerifyToken(metaConfig.verifyToken)' in source
