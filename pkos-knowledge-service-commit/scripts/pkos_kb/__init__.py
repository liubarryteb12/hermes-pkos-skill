"""pkos_kb — PKOS 知识库常驻索引引擎 v5.4"""
from .catalog import Catalog, IndexWriteError, PhysicalWriteError
from .guard import (VaultWriteAttempt, assert_not_vault, guarded_write_text,
                    is_vault_path, vault_root_override)
from .migrate import MigrationHalt, assert_schema, migrate, precheck_all
from .parser import cjk_bigram, extract_links, fts_query, make_snippet
from .governance import (EvidenceStale, RenameBlocked, assert_rename_allowed,
                         backlinks, dead_links, health_metrics, issue_ticket,
                         orphans, published_without_ticket, render_topic_report,
                         search, verify_ticket_evidence)
from .thread import (DEFAULT_THRESHOLD, HALT_THRESHOLD, TERMINAL_STATES,
                     ZERO_TOLERANCE, ThreadState, append_event, ensure_tables,
                     get_thread, last_event, load_thread, mark_completed, new_thread,
                     record_error, record_event, resumable, run_steps_with_resume,
                     set_status)
__version__ = "5.4.0"
