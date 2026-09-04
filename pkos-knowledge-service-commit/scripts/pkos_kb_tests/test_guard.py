"""H-pre-edit 守卫（第 ④ 条）"""
import os
import sys

import pytest

from pkos_kb.guard import (VaultWriteAttempt, assert_not_vault,
                           guarded_unlink, guarded_write_text, is_vault_path,
                           vault_root_override)


@pytest.fixture
def env(tmp_path):
    v = tmp_path / "vault"
    (v / "sub").mkdir(parents=True)
    (v / "a.md").write_text("x", encoding="utf-8")
    (v / ".obsidian").mkdir()
    (v / ".trash").mkdir()
    work = tmp_path / "work"
    work.mkdir()
    sibling = tmp_path / "vault2"      # 前缀陷阱
    sibling.mkdir()
    with vault_root_override(v):
        yield v, work, sibling


@pytest.mark.parametrize("rel", ["", "a.md", "sub/b.md", ".obsidian/c.json", ".trash/d.md"])
def test_blocks_everything_inside(env, rel):
    v, _, _ = env
    with pytest.raises(VaultWriteAttempt):
        assert_not_vault(v / rel if rel else v)


def test_blocks_dotdot_escape(env):
    v, _, _ = env
    with pytest.raises(VaultWriteAttempt):
        assert_not_vault(str(v) + "/../vault/a.md")


def test_blocks_mixed_dots(env):
    v, _, _ = env
    with pytest.raises(VaultWriteAttempt):
        assert_not_vault(str(v) + "/./sub/../a.md")


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="no symlink")
def test_blocks_symlink_to_vault(env):
    v, work, _ = env
    link = work / "link"
    try:
        link.symlink_to(v, target_is_directory=True)
    except OSError:
        pytest.skip("symlink not permitted")
    with pytest.raises(VaultWriteAttempt):
        assert_not_vault(link / "a.md")


def test_sibling_prefix_not_blocked(env):
    """★ /v/vault2 不应被 /v/vault 误判（禁止 startswith）"""
    _, _, sib = env
    assert not is_vault_path(sib / "x.md")
    p = guarded_write_text(sib / "x.md", "ok")
    assert p.read_text(encoding="utf-8") == "ok"


def test_atomic_write_and_mkdir(env):
    _, work, _ = env
    p = guarded_write_text(work / "deep" / "n.md", "hello")
    assert p.read_text(encoding="utf-8") == "hello"
    assert not list((work / "deep").glob("*.pkostmp"))


def test_unlink_outside_ok(env):
    _, work, _ = env
    p = guarded_write_text(work / "n.md", "x")
    guarded_unlink(p)
    assert not p.exists()


def test_unlink_inside_blocked(env):
    v, _, _ = env
    with pytest.raises(VaultWriteAttempt):
        guarded_unlink(v / "a.md")


def test_error_message_actionable(env):
    v, _, _ = env
    with pytest.raises(VaultWriteAttempt) as ei:
        assert_not_vault(v / "a.md")
    m = str(ei.value)
    assert "a.md" in m and str(v) in m and "终止全部任务" in m


def test_env_override(tmp_path, monkeypatch):
    v = tmp_path / "myvault"
    v.mkdir()
    monkeypatch.setenv("PKOS_VAULT_ROOTS", str(v))
    assert is_vault_path(v / "x.md")
    assert not is_vault_path(tmp_path / "other" / "y.md")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows 专项：生产默认根")
def test_default_windows_root():
    assert is_vault_path(r"D:\obsidian知识库\obsidian知识库\x.md")
    assert is_vault_path(r"D:\obsidian知识库\obsidian知识库\.trash\y.md")
    assert not is_vault_path(r"D:\other\z.md")
