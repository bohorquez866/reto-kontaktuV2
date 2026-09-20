from __future__ import annotations

from src.store import Store


def test_order_idempotency(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    first = store.save_order("lk-1:cerrar_llamada", "ord_a", "evt_a", "cerrar_llamada")
    second = store.save_order("lk-1:cerrar_llamada", "ord_b", "evt_a", "cerrar_llamada")
    assert first is True
    assert second is False
    assert store.order_exists("lk-1:cerrar_llamada")
    store.close()


def test_processed_event_and_redelivery(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    store.save_processed("lk-out-0311", "evt_09", "callback")
    row = store.get_processed("lk-out-0311")
    assert row["etiqueta"] == "callback"
    assert store.get_processed("missing") is None
    store.close()


def test_reminders_are_pending_until_cancelled(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    store.save_reminder("rem_1", "c_302")
    store.save_reminder("rem_2", "c_302")
    pending = store.get_pending_reminders("c_302")
    assert {item["reminder_id"] for item in pending} == {"rem_1", "rem_2"}
    store.cancel_reminder("rem_1")
    left = store.get_pending_reminders("c_302")
    assert [item["reminder_id"] for item in left] == ["rem_2"]
    store.close()


def test_lead_state_defaults_and_upsert(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    empty = store.get_lead("c_new")
    assert empty == {
        "contact_id": "c_new",
        "attempts": 0,
        "cut_count": 0,
        "dnc": False,
        "whatsapp_rechazado": False,
    }
    store.upsert_lead("c_new", 3, 2, True, True)
    lead = store.get_lead("c_new")
    assert lead["attempts"] == 3
    assert lead["cut_count"] == 2
    assert lead["dnc"] is True
    assert lead["whatsapp_rechazado"] is True
    store.close()
